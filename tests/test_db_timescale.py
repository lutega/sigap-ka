"""
Tujuan      : Menguji fitur TimescaleDB: hypertable, continuous aggregate, akumulasi 1/3/5 hari.
Lapis       : QA, infrastruktur data (tes integrasi, marker db).
Sumber      : Database uji sigap_test dari docker compose.
Masukan     : Data uji buatan (bukan data nyata).
Keluaran    : -
Keterbatasan: Dilewati bila database uji tidak terjangkau.
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy import text

from db import repositori as repo
from db.inisialisasi import inisialisasi
from db.koneksi import sesi_dari

pytestmark = pytest.mark.db


@pytest.fixture
def bersih(engine_pg):
    """Mengosongkan tabel time series sebelum tiap tes."""
    with engine_pg.begin() as kon:
        kon.execute(text("TRUNCATE obs_hujan, prakiraan_hujan, obs_muka_air"))
    return engine_pg


def test_tiga_hypertable_terdaftar(engine_pg):
    """obs_hujan, prakiraan_hujan, obs_muka_air terdaftar sebagai hypertable."""
    with engine_pg.connect() as kon:
        nama = {r[0] for r in kon.execute(text(
            "SELECT hypertable_name FROM timescaledb_information.hypertables"))}
    assert {"obs_hujan", "prakiraan_hujan", "obs_muka_air"} <= nama


def test_continuous_aggregate_terbentuk(engine_pg):
    """Continuous aggregate hujan_harian terbentuk."""
    with engine_pg.connect() as kon:
        nama = {r[0] for r in kon.execute(text(
            "SELECT view_name FROM timescaledb_information.continuous_aggregates"))}
    assert "hujan_harian" in nama


def test_inisialisasi_ulang_idempoten(engine_pg):
    """Inisialisasi dijalankan lagi tanpa galat."""
    hasil = inisialisasi(engine_pg)
    assert hasil["timescale"] is True


def test_akumulasi_1_3_5_hari(bersih):
    """View hujan_akumulasi menjumlah 1, 3, dan 5 hari dengan benar (1 mm/jam = 24 mm/hari)."""
    awal = datetime(2025, 1, 1)
    df = pd.DataFrame({
        "waktu": [awal + timedelta(hours=i) for i in range(24 * 6)],
        "lokasi": "lokal", "nilai": 1.0, "satuan": "mm", "sumber": "uji",
        "is_simulated": True, "resolusi_jam": 1,
    })
    with sesi_dari(bersih) as sesi:
        repo.simpan_obs_hujan(sesi, df)
    sql = ("SELECT hari, akumulasi_1h, akumulasi_3h, akumulasi_5h FROM hujan_akumulasi "
           "WHERE lokasi = :lok AND sumber = :sumber ORDER BY hari")
    with bersih.connect() as kon:
        baris = kon.execute(text(sql), {"lok": "lokal", "sumber": "uji"}).all()
    assert len(baris) == 6
    assert baris[0].akumulasi_1h == pytest.approx(24)
    assert baris[2].akumulasi_3h == pytest.approx(72)
    assert baris[4].akumulasi_5h == pytest.approx(120)
    assert baris[5].akumulasi_3h == pytest.approx(72)


def test_upsert_postgres_tidak_menggandakan(bersih):
    """Upsert di PostgreSQL memperbarui baris berkunci sama."""
    df = pd.DataFrame({"waktu": [datetime(2025, 1, 2)], "lokasi": ["hulu"], "nilai": [5.0],
                       "satuan": ["mm"], "sumber": ["uji"], "is_simulated": [True]})
    with sesi_dari(bersih) as sesi:
        repo.simpan_obs_hujan(sesi, df)
        repo.simpan_obs_hujan(sesi, df.assign(nilai=7.0))
    with sesi_dari(bersih) as sesi:
        hasil = repo.ambil_obs_hujan(sesi, lokasi="hulu")
    assert len(hasil) == 1 and hasil.loc[0, "nilai"] == 7.0


def test_prakiraan_tersedia_postgres(bersih):
    """Filter waktu terbit bekerja di PostgreSQL."""
    baris = [{"waktu_terbit": datetime(2025, 1, 24, h), "waktu": datetime(2025, 1, 24, h + 1),
              "lokasi": "lokal", "nilai": float(h), "satuan": "mm", "sumber": "uji",
              "is_simulated": True} for h in (0, 6, 12)]
    with sesi_dari(bersih) as sesi:
        repo.simpan_prakiraan(sesi, pd.DataFrame(baris))
        hasil = repo.ambil_prakiraan_tersedia(sesi, datetime(2025, 1, 24, 11), "lokal")
    assert list(hasil["nilai"]) == [6.0]
