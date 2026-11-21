"""
Tujuan      : Menguji REST API dan auth: semua endpoint spesifikasi 14.2, login JWT, akun awal
              admin/admin, kelola pengguna, otorisasi (401/403), keputusan dengan username, simulasi
              latar belakang, potongan data tanpa intip masa depan, dan tidak adanya klaim jalur aman.
Lapis       : QA, API.
Sumber      : Aplikasi dengan SQLite di memori, diisi episode demo dan data olahan repo.
Masukan     : -
Keluaran    : -
Keterbatasan: Tes integrasi TimescaleDB untuk API dicakup uji menyeluruh tahap 10.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from action.penjaga_klaim import periksa_teks
from db.koneksi import sesi_dari
from simulation.episode import bangun_episode_nyata, episode_cadangan, episode_sintetis, simpan_ke_db

RESPON = []  # semua respons JSON dikumpulkan untuk pemeriksaan klaim jalur aman


@pytest.fixture(scope="module")
def klien():
    """TestClient dengan database SQLite berisi episode demo dan data olahan nyata."""
    from api.main import buat_aplikasi
    from sensing.jalankan import muat_ke_db
    app = buat_aplikasi("sqlite://")
    with TestClient(app) as c:
        eng = app.state.konteks.engine
        muat_ke_db(eng)
        with sesi_dari(eng) as s:
            for ep in (bangun_episode_nyata(), episode_cadangan(), episode_sintetis(1, 3, "base")[0]):
                simpan_ke_db(s, ep)
        c.app_ref = app
        yield c


def _token(c, user="admin", pw="admin"):
    r = c.post("/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _get(c, url, hdr, kode=200):
    r = c.get(url, headers=hdr)
    assert r.status_code == kode, (url, r.status_code, r.text[:300])
    RESPON.append(r.text)
    return r.json()


@pytest.fixture(scope="module")
def admin(klien):
    return _token(klien)


@pytest.fixture(scope="module")
def operator(klien, admin):
    r = klien.post("/pengguna", json={"username": "op1", "password": "rahasia1", "level": "operator"}, headers=admin)
    assert r.status_code == 201
    return _token(klien, "op1", "rahasia1")


# ---------------------------------------------------------------- auth dan pengguna

def test_kesehatan_tanpa_token(klien):
    """Pemeriksaan hidup tidak butuh token."""
    assert klien.get("/kesehatan").json()["status"] == "berjalan"


@pytest.mark.parametrize("url", [
    "/data/sumber", "/data/hujan", "/data/muka-air", "/data/kejadian", "/episode",
    "/episode/DEMO-CADANGAN/prediksi?jam=24", "/tindakan", "/kurva/T1",
    "/episode/DEMO-CADANGAN/papan?jam=24", "/episode/DEMO-CADANGAN/ringkasan", "/simulasi", "/pengguna",
])
def test_tanpa_token_401(klien, url):
    """Endpoint selain login wajib token."""
    assert klien.get(url).status_code == 401


def test_login_admin_awal_dan_password_salah(klien):
    """Akun awal admin/admin dari .env; password salah ditolak; password tersimpan sebagai hash bcrypt."""
    r = klien.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200 and r.json()["level"] == "admin"
    assert klien.post("/auth/login", json={"username": "admin", "password": "salah"}).status_code == 401
    from auth.pengguna import cari
    with sesi_dari(klien.app_ref.state.konteks.engine) as s:
        assert cari(s, "admin").hash_password.startswith("$2")


def test_token_rusak_401(klien):
    """Token palsu ditolak."""
    assert klien.get("/episode", headers={"Authorization": "Bearer palsu"}).status_code == 401


def test_operator_tidak_boleh_kelola_pengguna_dan_simulasi(klien, operator):
    """Operator: 403 untuk /pengguna dan POST /simulasi; boleh melihat dashboard."""
    assert klien.get("/pengguna", headers=operator).status_code == 403
    assert klien.post("/simulasi", json={"n": 2}, headers=operator).status_code == 403
    assert klien.get("/auth/saya", headers=operator).json()["level"] == "operator"
    assert klien.get("/episode", headers=operator).status_code == 200


def test_admin_kelola_pengguna(klien, admin):
    """Admin menambah, menonaktifkan, mengaktifkan, dan mengatur ulang password pengguna."""
    r = klien.post("/pengguna", json={"username": "op2", "password": "awal1234"}, headers=admin)
    pid = r.json()["id"]
    assert klien.post("/pengguna", json={"username": "op2", "password": "awal1234"}, headers=admin).status_code == 409
    tok = _token(klien, "op2", "awal1234")
    assert klien.patch(f"/pengguna/{pid}", json={"aktif": False}, headers=admin).json()["aktif"] is False
    assert klien.post("/auth/login", json={"username": "op2", "password": "awal1234"}).status_code == 401
    assert klien.get("/episode", headers=tok).status_code == 401  # token lama ikut ditolak
    klien.patch(f"/pengguna/{pid}", json={"aktif": True}, headers=admin)
    klien.post(f"/pengguna/{pid}/atur-ulang-password", json={"password_baru": "baru5678"}, headers=admin)
    assert klien.post("/auth/login", json={"username": "op2", "password": "baru5678"}).status_code == 200
    daftar = _get(klien, "/pengguna", admin)
    assert all("hash_password" not in d for d in daftar)


def test_admin_terakhir_tidak_bisa_dinonaktifkan(klien, admin):
    """Sistem menjaga minimal satu admin aktif."""
    pid = next(d["id"] for d in _get(klien, "/pengguna", admin) if d["username"] == "admin")
    assert klien.patch(f"/pengguna/{pid}", json={"aktif": False}, headers=admin).status_code == 409


# ---------------------------------------------------------------- data dan episode

def test_data_sumber_hujan_muka_air_kejadian(klien, admin):
    """Endpoint lapis S mengembalikan data berlabel dari database lokal."""
    sumber = _get(klien, "/data/sumber", admin)
    assert len(sumber) == 12 and {s["kelompok"] for s in sumber} == {"inti", "tambahan"}
    hujan = _get(klien, "/data/hujan?lokasi=lokal&dari=2025-01-20&sampai=2025-01-24", admin)
    assert len(hujan) == 5 and all(h["is_simulated"] is False for h in hujan)
    ma = _get(klien, "/data/muka-air?titik=glapan", admin)
    assert any(s["nilai"] == 1970 for s in ma["seri"]) and ma["ambang_awas"] == 1905
    assert len(_get(klien, "/data/kejadian", admin)) == 6
    assert all(j["is_simulated"] for j in _get(klien, "/data/jadwal", admin))


def test_daftar_dan_detail_episode_tanpa_intip(klien, admin):
    """Episode nyata tampil lebih dulu; detail dipotong pada jam yang diminta."""
    eps = _get(klien, "/episode", admin)
    assert eps[0]["id"] == "NYATA-20250124" and eps[0]["jenis"] == "nyata"
    d = _get(klien, "/episode/DEMO-CADANGAN?sampai_jam=24", admin)
    batas = datetime.fromisoformat(d["t0"]) - timedelta(hours=24)
    assert max(datetime.fromisoformat(h["waktu"]) for h in d["hujan"]) <= batas
    assert all(datetime.fromisoformat(p["waktu_terbit"]) <= batas for p in d["prakiraan_terakhir"])
    assert d["label_seri"]["hujan"] == "dummy"
    nyata = _get(klien, "/episode/NYATA-20250124", admin)
    assert nyata["label_seri"] == {"hujan": "nyata", "prakiraan": "dummy", "muka_air": "campuran", "laporan": "kosong"}


def test_prediksi_dan_lintasan(klien, admin):
    """Prediksi pada jam keputusan; jam tidak valid 422; episode tidak ada 404."""
    p = _get(klien, "/episode/DEMO-CADANGAN/prediksi?jam=24", admin)
    assert p["peluang"] == pytest.approx(p["peluang_genangan"] + p["peluang_gerusan"])
    assert set(p["lama_tutup"]["sebaran"]) == {"pendek", "sedang", "panjang"}
    _get(klien, "/episode/DEMO-CADANGAN/prediksi?jam=25", admin, kode=422)
    _get(klien, "/episode/TIDAK-ADA/prediksi?jam=24", admin, kode=404)
    lin = _get(klien, "/episode/DEMO-CADANGAN/lintasan?sampai_jam=24", admin)
    assert [x["jam_sebelum_t0"] for x in lin] == list(range(72, 23, -6))


# ---------------------------------------------------------------- tindakan dan kurva

def test_tindakan_dan_kurva(klien, admin):
    """Daftar T1-T9 dengan C, L, P; kurva berakhir di ambang statis; slider tidak mengubah params."""
    t = _get(klien, "/tindakan?preset=base", admin)
    assert [x["id"] for x in t["tindakan"]] == [f"T{i}" for i in range(1, 10)]
    k = _get(klien, "/kurva/T1", admin)
    assert k["ambang"][-1] == pytest.approx(k["ambang_statis"], abs=1e-6)
    _get(klien, "/kurva/T10", admin, kode=404)
    r = klien.post("/kurva/hitung", json={"tindakan": "T3", "P": 300}, headers=admin)
    assert r.status_code == 200
    assert r.json()["kurva"]["ambang"][-1] > r.json()["kurva_bawaan"]["ambang"][-1]
    assert klien.post("/kurva/hitung", json={"tindakan": "T3", "C": 999, "L": 100}, headers=admin).status_code == 422
    assert _get(klien, "/tindakan?preset=base", admin) == t


def test_papan_keputusan_log_ringkasan(klien, operator):
    """Papan 9 tindakan; keputusan tercatat dengan username; persetujuan ganda 409; ringkasan T-0."""
    papan = _get(klien, "/episode/DEMO-CADANGAN/papan?jam=36", operator)
    assert len(papan["tindakan"]) == 9
    r = klien.post("/episode/DEMO-CADANGAN/keputusan", headers=operator,
                   json={"tindakan": "T1", "jam_sebelum_t0": 36, "keputusan": "setujui", "alasan": "uji"})
    assert r.status_code == 201, r.text
    assert r.json()["username"] == "op1" and r.json()["status_sigap"] in ("Putuskan sekarang", "Tunggu prakiraan berikutnya")
    assert klien.post("/episode/DEMO-CADANGAN/keputusan", headers=operator,
                      json={"tindakan": "T1", "jam_sebelum_t0": 30, "keputusan": "setujui"}).status_code == 409
    klien.post("/episode/DEMO-CADANGAN/keputusan", headers=operator,
               json={"tindakan": "T2", "jam_sebelum_t0": 30, "keputusan": "tolak", "alasan": "tunggu laporan"})
    log = _get(klien, "/episode/DEMO-CADANGAN/log", operator)
    assert [x["keputusan"] for x in log] == ["setujui", "tolak"] and all(x["username"] == "op1" for x in log)
    papan2 = _get(klien, "/episode/DEMO-CADANGAN/papan?jam=30", operator)
    assert next(b for b in papan2["tindakan"] if b["tindakan"] == "T1")["status"] == "Sudah disetujui"
    rk = _get(klien, "/episode/DEMO-CADANGAN/ringkasan", operator)
    t1 = next(b for b in rk["skenario"][0]["tindakan"] if b["tindakan"] == "T1")
    assert t1["operator"]["jam_sebelum_t0"] == 36
    assert klien.post("/episode/DEMO-CADANGAN/keputusan", headers=operator,
                      json={"tindakan": "T1", "jam_sebelum_t0": 37, "keputusan": "setujui"}).status_code == 422


def test_ringkasan_episode_nyata_dua_kemungkinan(klien, admin):
    """Episode nyata tanpa hasil terkonfirmasi: ringkasan dua kemungkinan."""
    rk = _get(klien, "/episode/NYATA-20250124/ringkasan", admin)
    assert rk["status_hasil"] == "belum terkonfirmasi" and len(rk["skenario"]) == 2


# ---------------------------------------------------------------- simulasi

def test_simulasi_latar_belakang(klien, admin):
    """Admin menjalankan simulasi; tugas latar selesai dan hasil per kebijakan dapat diambil."""
    r = klien.post("/simulasi", json={"preset": "base", "n": 4, "seed": 3}, headers=admin)
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    h = _get(klien, f"/simulasi/{run_id}", admin)
    assert h["status"] == "selesai", h
    assert len(h["per_kebijakan"]) == 6 and h["ringkasan"]["pembanding_terbaik"]
    assert any(x["run_id"] == run_id for x in _get(klien, "/simulasi", admin))
    _get(klien, "/simulasi/tidak-ada", admin, kode=404)


# ---------------------------------------------------------------- dokumentasi dan klaim

def test_openapi_memuat_endpoint_spesifikasi(klien):
    """Dokumentasi /docs tersedia dan memuat endpoint spesifikasi 14.2."""
    jalur = set(klien.get("/openapi.json").json()["paths"])
    wajib = {"/data/sumber", "/data/hujan", "/data/muka-air", "/data/kejadian", "/episode",
             "/episode/{episode_id}/prediksi", "/tindakan", "/kurva/{tindakan}", "/kurva/hitung",
             "/episode/{episode_id}/papan", "/episode/{episode_id}/keputusan",
             "/episode/{episode_id}/ringkasan", "/simulasi", "/simulasi/{run_id}", "/auth/login", "/pengguna"}
    assert wajib <= jalur
    assert klien.get("/docs").status_code == 200


def test_tidak_ada_respons_yang_menyatakan_jalur_aman():
    """Semua respons yang terkumpul selama tes bebas kata 'aman'/'safe' (FR-A5)."""
    assert RESPON, "tes lain harus berjalan lebih dulu"
    for teks in RESPON:
        assert not periksa_teks(teks), teks[:200]
