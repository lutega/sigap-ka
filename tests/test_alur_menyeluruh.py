"""
Tujuan      : Uji menyeluruh tahap 10 terhadap TimescaleDB sungguhan (docker compose): muat data
              olahan nyata -> siapkan episode demo -> API (login, data, prediksi, papan, keputusan)
              -> mode demo sampai ringkasan T-0, serta agregat akumulasi hujan pada data nyata.
Lapis       : QA, seluruh lapis (S-I-G-A, API, demo).
Sumber      : Database uji sigap_test, data/processed (NASA POWER, Glapan, kejadian, jadwal).
Masukan     : -
Keluaran    : -
Keterbatasan: Dilewati bila database uji tidak terjangkau; lambat (latensi Docker Desktop).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from action.penjaga_klaim import periksa_teks
from config import muat_pengaturan

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def klien_pg(engine_pg):
    """API terhadap TimescaleDB uji yang sudah diisi data olahan dan episode demo."""
    from api.main import buat_aplikasi
    from sensing.jalankan import muat_ke_db
    from simulation.episode import siapkan_episode_demo

    with engine_pg.begin() as kon:
        kon.execute(text("TRUNCATE obs_hujan, prakiraan_hujan, obs_muka_air, keputusan_operator, sesi_demo, "
                         "laporan_lapangan, episode, pengguna"))
    jumlah = muat_ke_db(engine_pg)
    assert jumlah["obs_hujan"] > 3000
    id_episode = siapkan_episode_demo(engine_pg)
    assert "NYATA-20250124" in id_episode and "DEMO-CADANGAN" in id_episode
    app = buat_aplikasi(muat_pengaturan().database_url_test, tanpa_pool=True)
    with TestClient(app) as c:
        tok = c.post("/auth/login", json={"username": "admin", "password": "admin"}).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {tok}"})
        yield c


def test_akumulasi_hujan_nyata_di_timescale(engine_pg, klien_pg):
    """Continuous aggregate dan view akumulasi bekerja pada hujan NASA POWER nyata (24 Jan 2025)."""
    with engine_pg.connect() as kon:
        r = kon.execute(text(
            "SELECT akumulasi_1h, akumulasi_3h FROM hujan_akumulasi "
            "WHERE lokasi = 'lokal' AND sumber = 'nasa_power' AND episode_id = '' AND hari = '2025-01-24'")).one()
    assert r.akumulasi_1h == pytest.approx(5.92, abs=0.01)
    assert r.akumulasi_3h > r.akumulasi_1h


def test_alur_api_dan_demo_menyeluruh(klien_pg):
    """Data -> prediksi -> papan -> keputusan -> demo sampai T-0 dengan ringkasan; tanpa klaim jalur aman."""
    c = klien_pg
    teks = []
    for url in ("/data/sumber", "/data/hujan?lokasi=hulu&dari=2025-01-20&sampai=2025-01-24&sumber=nasa_power", "/data/kejadian",
                "/episode", "/episode/NYATA-20250124/prediksi?jam=24", "/episode/DEMO-CADANGAN/papan?jam=36",
                "/tindakan", "/kurva/T9", "/info"):
        r = c.get(url)
        assert r.status_code == 200, (url, r.text[:200])
        teks.append(r.text)
    assert len(c.get("/data/hujan?lokasi=hulu&dari=2025-01-20&sampai=2025-01-24&sumber=nasa_power").json()) == 5
    k = c.post("/episode/DEMO-CADANGAN/keputusan",
               json={"tindakan": "T1", "jam_sebelum_t0": 36, "keputusan": "setujui", "alasan": "uji menyeluruh"})
    assert k.status_code == 201 and k.json()["username"] == "admin"

    sid = c.post("/demo/mulai", json={"episode_id": "DEMO-CADANGAN"}).json()["sesi"]["id"]
    for _ in range(12):
        d = c.post(f"/demo/{sid}/langkah").json()
        teks.append(str(d))
    assert d["sesi"]["status"] == "selesai" and d["ringkasan"]["status_hasil"] == "diketahui"
    r = c.post(f"/demo/{sid}/reset").json()
    assert r["sesi"]["jam_sebelum_t0"] == 72
    assert [x["keputusan"] for x in c.get("/episode/DEMO-CADANGAN/log").json()] == ["setujui"]
    for t in teks:
        assert not periksa_teks(t)
