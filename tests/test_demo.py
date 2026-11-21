"""
Tujuan      : Menguji mode demo (spesifikasi 16): mesin status sesi (mulai, langkah, jeda, reset),
              endpoint /demo, keputusan demo bertanda mode=demo, tanpa intip masa depan, ringkasan
              di T-0, reset yang hanya menghapus log demo sesi itu, hak akses, dan keterulangan
              skenario cadangan presentasi.
Lapis       : QA, simulasi demo + API.
Sumber      : Aplikasi dengan SQLite di memori (offline), episode cadangan dan episode nyata.
Masukan     : -
Keluaran    : -
Keterbatasan: Laju putar otomatis diatur klien; yang diuji adalah langkah server.
"""

import pytest
from fastapi.testclient import TestClient

from db.koneksi import sesi_dari
from simulation import demo, skenario_cadangan
from simulation.episode import bangun_episode_nyata, episode_cadangan, simpan_ke_db


# ---------------------------------------------------------------- mesin status

def test_mesin_status_demo(engine_sqlite, params_base):
    """Mulai di T-72, 12 langkah sampai T-0 (selesai), jeda bolak-balik, langkah sesudah selesai ditolak."""
    from db.koneksi import pabrik_sesi
    sesi = pabrik_sesi(engine_sqlite)()
    simpan_ke_db(sesi, episode_cadangan(params_base))
    s = demo.mulai(sesi, "DEMO-CADANGAN", "op", 1.0, params_base)
    assert (s.jam_sebelum_t0, s.status) == (72, demo.BERJALAN)
    assert demo.jeda(sesi, s.id).status == demo.JEDA
    assert demo.jeda(sesi, s.id).status == demo.BERJALAN
    for _ in range(12):
        demo.langkah(sesi, s.id, params_base)
    assert (s.jam_sebelum_t0, s.status) == (0, demo.SELESAI)
    with pytest.raises(demo.GalatDemo):
        demo.langkah(sesi, s.id, params_base)
    assert demo.jeda(sesi, s.id).status == demo.SELESAI
    s2, n = demo.reset(sesi, s.id, params_base)
    assert (s2.jam_sebelum_t0, s2.status, n) == (72, demo.BERJALAN, 0)
    with pytest.raises(demo.GalatDemo):
        demo.mulai(sesi, "TIDAK-ADA", "op")
    sesi.close()


# ---------------------------------------------------------------- API

@pytest.fixture(scope="module")
def klien():
    """Aplikasi offline (SQLite) berisi episode cadangan dan episode nyata."""
    from api.main import buat_aplikasi
    app = buat_aplikasi("sqlite://")
    with TestClient(app) as c:
        with sesi_dari(app.state.konteks.engine) as s:
            simpan_ke_db(s, episode_cadangan())
            simpan_ke_db(s, bangun_episode_nyata())
        tok = c.post("/auth/login", json={"username": "admin", "password": "admin"}).json()["access_token"]
        c.admin = {"Authorization": f"Bearer {tok}"}
        for nama in ("penguji", "penguji2"):
            c.post("/pengguna", json={"username": nama, "password": "rahasia1"}, headers=c.admin)
        c.op = {"Authorization": "Bearer " + c.post("/auth/login", json={"username": "penguji", "password": "rahasia1"}).json()["access_token"]}
        c.op2 = {"Authorization": "Bearer " + c.post("/auth/login", json={"username": "penguji2", "password": "rahasia1"}).json()["access_token"]}
        yield c


def test_alur_demo_lengkap_sampai_ringkasan(klien):
    """Penguji: mulai -> langkah -> setujui (mode demo) -> sampai T-0 -> ringkasan muncul."""
    r = klien.post("/demo/mulai", json={"episode_id": "DEMO-CADANGAN", "kecepatan_detik_per_jam": 0.5}, headers=klien.op)
    assert r.status_code == 201, r.text
    d = r.json()
    sid = d["sesi"]["id"]
    assert d["sesi"]["jam_sebelum_t0"] == 72 and d["sesi"]["mode"] == "demo"
    assert d["sesi"]["detik_per_langkah"] == pytest.approx(3.0)
    assert len(d["papan"]["tindakan"]) == 9 and d["episode"]["label_seri"]["hujan"] == "dummy"
    d = klien.post(f"/demo/{sid}/langkah", headers=klien.op).json()
    assert d["sesi"]["jam_sebelum_t0"] == 66
    assert [x["jam_sebelum_t0"] for x in d["lintasan"]] == [72, 66]  # tanpa intip masa depan
    k = klien.post("/episode/DEMO-CADANGAN/keputusan", headers=klien.op,
                   json={"tindakan": "T1", "jam_sebelum_t0": 66, "keputusan": "setujui", "sesi_demo_id": sid})
    assert k.status_code == 201 and k.json()["mode"] == "demo" and k.json()["username"] == "penguji"
    salah_jam = klien.post("/episode/DEMO-CADANGAN/keputusan", headers=klien.op,
                           json={"tindakan": "T2", "jam_sebelum_t0": 72, "keputusan": "setujui", "sesi_demo_id": sid})
    assert salah_jam.status_code == 409
    st = klien.get(f"/demo/{sid}/status", headers=klien.op).json()
    assert next(b for b in st["papan"]["tindakan"] if b["tindakan"] == "T1")["status"] == "Sudah disetujui"
    assert st["ringkasan"] is None
    for _ in range(11):
        d = klien.post(f"/demo/{sid}/langkah", headers=klien.op).json()
    assert d["sesi"]["status"] == "selesai" and d["ringkasan"] is not None
    t1 = next(b for b in d["ringkasan"]["skenario"][0]["tindakan"] if b["tindakan"] == "T1")
    assert t1["operator"]["jam_sebelum_t0"] == 66
    assert klien.post(f"/demo/{sid}/langkah", headers=klien.op).status_code == 409


def test_jeda_dan_kecepatan(klien):
    """Jeda/lanjut dan ubah kecepatan."""
    sid = klien.post("/demo/mulai", json={"episode_id": "NYATA-20250124"}, headers=klien.op).json()["sesi"]["id"]
    assert klien.post(f"/demo/{sid}/jeda", headers=klien.op).json()["sesi"]["status"] == "jeda"
    assert klien.post(f"/demo/{sid}/jeda", headers=klien.op).json()["sesi"]["status"] == "berjalan"
    r = klien.post(f"/demo/{sid}/kecepatan", json={"kecepatan_detik_per_jam": 2}, headers=klien.op).json()
    assert r["sesi"]["detik_per_langkah"] == pytest.approx(12.0)


def test_reset_hanya_log_demo_sesi_itu_dan_khusus_admin(klien):
    """Reset oleh operator ditolak; admin menghapus log demo sesi itu saja, log normal dan sesi lain tetap."""
    a = klien.post("/demo/mulai", json={"episode_id": "DEMO-CADANGAN"}, headers=klien.op).json()["sesi"]["id"]
    b = klien.post("/demo/mulai", json={"episode_id": "DEMO-CADANGAN"}, headers=klien.op).json()["sesi"]["id"]
    for sid in (a, b):
        klien.post("/episode/DEMO-CADANGAN/keputusan", headers=klien.op,
                   json={"tindakan": "T1", "jam_sebelum_t0": 72, "keputusan": "setujui", "sesi_demo_id": sid})
    klien.post("/episode/DEMO-CADANGAN/keputusan", headers=klien.op,
               json={"tindakan": "T2", "jam_sebelum_t0": 72, "keputusan": "tolak", "alasan": "log normal"})
    assert klien.post(f"/demo/{a}/reset", headers=klien.op).status_code == 403
    r = klien.post(f"/demo/{a}/reset", headers=klien.admin).json()
    assert r["log_demo_dihapus"] == 1 and r["sesi"]["jam_sebelum_t0"] == 72
    assert klien.get(f"/episode/DEMO-CADANGAN/log?sesi_demo_id={a}", headers=klien.op).json() == []
    assert len(klien.get(f"/episode/DEMO-CADANGAN/log?sesi_demo_id={b}", headers=klien.op).json()) == 1
    normal = klien.get("/episode/DEMO-CADANGAN/log", headers=klien.op).json()
    assert [x["keputusan"] for x in normal] == ["tolak"]


def test_hak_akses_sesi_demo(klien):
    """Pengguna lain tidak dapat mengendalikan sesi; admin dapat; sesi/episode tak dikenal 404."""
    sid = klien.post("/demo/mulai", json={"episode_id": "DEMO-CADANGAN"}, headers=klien.op).json()["sesi"]["id"]
    assert klien.post(f"/demo/{sid}/langkah", headers=klien.op2).status_code == 403
    assert klien.get(f"/demo/{sid}/status", headers=klien.admin).status_code == 200
    assert klien.get("/demo/tidak-ada/status", headers=klien.op).status_code == 404
    assert klien.post("/demo/mulai", json={"episode_id": "TIDAK-ADA"}, headers=klien.op).status_code == 404
    assert klien.post("/demo/mulai", json={"episode_id": "DEMO-CADANGAN"}).status_code == 401


def test_episode_nyata_demo_dua_kemungkinan(klien):
    """Demo episode nyata 24 Jan 2025 menampilkan label campuran dan ringkasan dua kemungkinan di T-0."""
    sid = klien.post("/demo/mulai", json={"episode_id": "NYATA-20250124"}, headers=klien.op).json()["sesi"]["id"]
    for _ in range(12):
        d = klien.post(f"/demo/{sid}/langkah", headers=klien.op).json()
    assert d["episode"]["jenis"] == "nyata" and d["episode"]["label_seri"]["muka_air"] == "campuran"
    assert d["ringkasan"]["status_hasil"] == "belum terkonfirmasi" and len(d["ringkasan"]["skenario"]) == 2


# ---------------------------------------------------------------- cadangan tanpa Docker

def test_cadangan_sqlite_berkas_untuk_demo(tmp_path):
    """Berkas SQLite cadangan memuat data nyata, episode demo, dan simulasi; API berjalan di atasnya."""
    from concurrent.futures import ThreadPoolExecutor

    from api.main import buat_aplikasi
    from simulation.cadangan_sqlite import bangun
    berkas = tmp_path / "cadangan.sqlite"
    hasil = bangun(berkas, n=5)
    assert hasil["data"]["obs_hujan"] > 3000 and "DEMO-CADANGAN" in hasil["episode"] and len(hasil["simulasi"]) == 3
    app = buat_aplikasi(f"sqlite:///{berkas.as_posix()}")
    with TestClient(app) as c:
        tok = c.post("/auth/login", json={"username": "admin", "password": "admin"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        urls = ["/episode/DEMO-CADANGAN/papan?jam=36", "/episode/DEMO-CADANGAN/lintasan?sampai_jam=36",
                "/simulasi", "/data/sumber", "/tindakan"]
        with ThreadPoolExecutor(5) as ex:  # permintaan paralel seperti konsol
            assert list(ex.map(lambda u: c.get(u, headers=h).status_code, urls)) == [200] * 5
        sid = c.post("/demo/mulai", json={"episode_id": "DEMO-CADANGAN"}, headers=h).json()["sesi"]["id"]
        for _ in range(12):
            d = c.post(f"/demo/{sid}/langkah", headers=h).json()
        assert d["sesi"]["status"] == "selesai" and d["ringkasan"] is not None
    app.state.konteks.engine.dispose()


# ---------------------------------------------------------------- skenario cadangan

def test_skenario_cadangan_selalu_sama():
    """Dua kali dibangun memberi sidik identik dan sama dengan cuplikan tersimpan di repo."""
    a = skenario_cadangan.bangun_cuplikan()
    b = skenario_cadangan.bangun_cuplikan()
    assert a["sidik_sha256"] == b["sidik_sha256"]
    sama, baru, lama = skenario_cadangan.periksa()
    assert sama, f"cuplikan berubah ({baru} vs {lama}); jalankan python -m simulation.skenario_cadangan bila disengaja"
    assert len(a["per_jam"]) == 13 and a["episode"]["kebenaran"]["terganggu"] is True
