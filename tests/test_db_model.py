"""
Tujuan      : Menguji skema dan repositori database pada SQLite (tahap 1).
Lapis       : QA, infrastruktur data.
Sumber      : db/model.py, db/inisialisasi.py, db/repositori.py.
Masukan     : Data uji buatan (bukan data nyata).
Keluaran    : -
Keterbatasan: Fitur TimescaleDB diuji terpisah di test_db_timescale.py (marker db).
"""

from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import func, inspect, select

from db import repositori as repo
from db.inisialisasi import inisialisasi
from db.koneksi import normalisasi_url
from db.model import HYPERTABLE, Base, ObsHujan, SumberData, TindakanDB

TABEL_SPESIFIKASI_14_5 = {
    "obs_hujan", "prakiraan_hujan", "obs_muka_air", "sumber_data", "log_pengambilan",
    "kejadian", "jadwal_ka", "tindakan", "keputusan_operator", "hasil_simulasi",
}
TABEL_TAMBAHAN = {"pengguna", "episode", "laporan_lapangan", "simulasi_run", "sesi_demo"}


def _hujan(nilai: float, n: int = 3) -> pd.DataFrame:
    """Tabel standar hujan uji: n baris per jam di lokasi lokal."""
    t0 = datetime(2025, 1, 20)
    return pd.DataFrame({
        "waktu": [t0 + timedelta(hours=i) for i in range(n)],
        "lokasi": "lokal", "nilai": nilai, "satuan": "mm",
        "sumber": "uji", "is_simulated": True, "resolusi_jam": 1,
    })


def test_semua_tabel_terbentuk(engine_sqlite):
    """Tabel 14.5 dan tabel tambahan (bagian 15-16) terbentuk."""
    nama = set(inspect(engine_sqlite).get_table_names())
    assert TABEL_SPESIFIKASI_14_5 <= nama
    assert TABEL_TAMBAHAN <= nama


def test_inisialisasi_idempoten(engine_sqlite):
    """Inisialisasi dua kali tidak galat dan tidak menggandakan isi acuan."""
    inisialisasi(engine_sqlite)
    with engine_sqlite.connect() as kon:
        assert kon.execute(select(func.count()).select_from(TindakanDB)).scalar() == 9


def test_tabel_tindakan_tanpa_parameter_biaya():
    """C, L, P tidak disimpan di DB (satu sumber parameter: params.json)."""
    kolom = {c.name for c in Base.metadata.tables["tindakan"].columns}
    assert not kolom & {"C", "L", "P", "c", "l", "p"}
    assert kolom == {"id", "nama", "batas_waktu_siap", "terkonfirmasi"}


def test_isi_acuan_sumber_data(sesi_sqlite, params_base):
    """Tabel sumber_data terisi dari params.json."""
    n = sesi_sqlite.scalar(select(func.count()).select_from(SumberData))
    assert n == len(params_base.sumber_data)


def test_hypertable_punya_waktu_di_kunci_primer():
    """Kunci primer hypertable memuat kolom waktunya (syarat TimescaleDB)."""
    for tabel, kolom in HYPERTABLE.items():
        pk = {c.name for c in Base.metadata.tables[tabel].primary_key.columns}
        assert kolom in pk


def test_upsert_tidak_menggandakan(sesi_sqlite):
    """Menyimpan ulang baris dengan kunci sama memperbarui nilai, bukan menambah baris."""
    repo.simpan_obs_hujan(sesi_sqlite, _hujan(1.0))
    repo.simpan_obs_hujan(sesi_sqlite, _hujan(2.5))
    sesi_sqlite.commit()
    assert sesi_sqlite.scalar(select(func.count()).select_from(ObsHujan)) == 3
    df = repo.ambil_obs_hujan(sesi_sqlite, lokasi="lokal")
    assert (df["nilai"] == 2.5).all()
    assert list(df.columns[:6]) == repo.KOLOM_STANDAR


def test_filter_episode(sesi_sqlite):
    """Observasi umum (episode_id '') terpisah dari data milik episode."""
    repo.simpan_obs_hujan(sesi_sqlite, _hujan(1.0))
    repo.simpan_obs_hujan(sesi_sqlite, _hujan(9.0), episode_id="SIN-0001")
    assert len(repo.ambil_obs_hujan(sesi_sqlite)) == 3
    assert (repo.ambil_obs_hujan(sesi_sqlite, episode_id="SIN-0001")["nilai"] == 9.0).all()
    assert len(repo.ambil_obs_hujan(sesi_sqlite, episode_id=["", "SIN-0001"])) == 6


def test_prakiraan_hanya_yang_sudah_terbit(sesi_sqlite):
    """Pada jam keputusan hanya prakiraan terbitan terakhir yang sudah terbit yang diambil."""
    baris = []
    for jam_terbit in (0, 6, 12):
        terbit = datetime(2025, 1, 24, jam_terbit)
        for j in range(3):
            baris.append({"waktu_terbit": terbit, "waktu": terbit + timedelta(hours=3 * j),
                          "lokasi": "lokal", "nilai": float(jam_terbit), "satuan": "mm",
                          "sumber": "uji", "is_simulated": True})
    repo.simpan_prakiraan(sesi_sqlite, pd.DataFrame(baris))
    hasil = repo.ambil_prakiraan_tersedia(sesi_sqlite, datetime(2025, 1, 24, 7), "lokal")
    assert set(hasil["waktu_terbit"]) == {datetime(2025, 1, 24, 6)}
    assert len(hasil) == 3
    assert repo.ambil_prakiraan_tersedia(sesi_sqlite, datetime(2025, 1, 23), "lokal").empty


def test_muka_air_format_standar(sesi_sqlite):
    """Muka air disimpan sebagai titik/elevasi dan dibaca kembali sebagai lokasi/nilai."""
    df = pd.DataFrame({"waktu": [datetime(2025, 1, 24, 12)], "lokasi": ["glapan"],
                       "nilai": [1970.0], "satuan": ["cm"], "sumber": ["glapan_bnpb"],
                       "is_simulated": [False]})
    repo.simpan_muka_air(sesi_sqlite, df)
    hasil = repo.ambil_muka_air(sesi_sqlite, titik="glapan")
    assert hasil.loc[0, "nilai"] == 1970.0
    assert not hasil.loc[0, "is_simulated"]


def test_hapus_muka_air_umum_dan_seri_episode(sesi_sqlite):
    """Hapus observasi umum satu sumber tidak menyentuh seri episode; hapus seri episode menolak id kosong."""
    import pytest
    df = pd.DataFrame({"waktu": [datetime(2025, 1, 24, 23), datetime(2025, 1, 25, 0)], "lokasi": ["glapan", "glapan"],
                       "nilai": [1970.0, 1970.0], "satuan": ["cm", "cm"], "sumber": ["glapan_bnpb", "glapan_bnpb"],
                       "is_simulated": [False, False]})
    repo.simpan_muka_air(sesi_sqlite, df)
    repo.simpan_muka_air(sesi_sqlite, df.iloc[:1], episode_id="EP-X")
    repo.hapus_muka_air_umum(sesi_sqlite, "glapan_bnpb")
    assert repo.ambil_muka_air(sesi_sqlite, titik="glapan").empty
    assert len(repo.ambil_muka_air(sesi_sqlite, titik="glapan", episode_id="EP-X")) == 1
    repo.hapus_seri_episode(sesi_sqlite, "EP-X")
    assert repo.ambil_muka_air(sesi_sqlite, titik="glapan", episode_id="EP-X").empty
    with pytest.raises(ValueError):
        repo.hapus_seri_episode(sesi_sqlite, "")


def test_catat_pengambilan_memperbarui_status(sesi_sqlite):
    """Catatan asal data memperbarui status sumber."""
    repo.catat_pengambilan(sesi_sqlite, "nasa_power", "sukses", jumlah_baris=10,
                           versi_atau_tautan="https://contoh")
    sd = sesi_sqlite.get(SumberData, "nasa_power")
    assert sd.status_terakhir == "sukses"
    assert sd.waktu_ambil_terakhir is not None


def test_laporan_tanpa_intip_masa_depan(sesi_sqlite):
    """Laporan lapangan setelah jam keputusan tidak ikut terambil."""
    repo.simpan_laporan(sesi_sqlite, [
        {"episode_id": "E", "waktu": datetime(2025, 1, 24, 10), "jenis": "air_badan_rel",
         "is_simulated": True},
        {"episode_id": "E", "waktu": datetime(2025, 1, 24, 20), "jenis": "air_badan_rel",
         "is_simulated": True},
    ])
    assert len(repo.ambil_laporan(sesi_sqlite, "E", sampai=datetime(2025, 1, 24, 12))) == 1


def test_episode_simpan_dan_daftar(sesi_sqlite):
    """Episode dapat disimpan, diperbarui, dan didaftar."""
    data = dict(id="SIN-0001", nama="uji", jenis="sintetis", t0=datetime(2025, 1, 1),
                horizon_jam=72, interval_jam=6, status_hasil="sintetis", is_simulated=True)
    repo.simpan_episode(sesi_sqlite, data)
    repo.simpan_episode(sesi_sqlite, {**data, "nama": "uji-2"})
    daftar = repo.daftar_episode(sesi_sqlite)
    assert len(daftar) == 1 and daftar[0].nama == "uji-2"


def test_normalisasi_url():
    """URL postgresql:// diarahkan ke driver psycopg 3."""
    assert normalisasi_url("postgresql://a:b@h/d") == "postgresql+psycopg://a:b@h/d"
    assert normalisasi_url("sqlite://") == "sqlite://"
