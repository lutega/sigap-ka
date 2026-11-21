"""
Tujuan      : Menguji pendukung konsol: kesesuaian angka konsol (API) dengan model (FR-E3, NFR-3),
              endpoint /info berisi empat batas klaim, dan penyajian dashboard hasil build.
Lapis       : QA, konsol.
Sumber      : dashboard/export_dashboard.py, api/routers/info.py, dashboard/dist (bila sudah dibangun).
Masukan     : -
Keluaran    : -
Keterbatasan: Tes penyajian dashboard dilewati bila dashboard belum dibangun (npm run build).
"""

import pytest
from fastapi.testclient import TestClient

from config import AKAR_REPO


def test_angka_konsol_sama_dengan_model_preset_base():
    """Ambang, kurva, prediksi, dan simulasi lewat API identik dengan keluaran model (base)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("export_dashboard", AKAR_REPO / "dashboard" / "export_dashboard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    laporan = mod.cek_kesesuaian(["base"], n_simulasi=5)
    beda = [r for r in laporan if not r["sesuai"]]
    assert not beda, beda
    assert len(laporan) == 9 * 2 + 1 + 6


@pytest.fixture(scope="module")
def klien_info():
    from api.main import buat_aplikasi
    app = buat_aplikasi("sqlite://")
    with TestClient(app) as c:
        tok = c.post("/auth/login", json={"username": "admin", "password": "admin"}).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {tok}"})
        yield c


def test_info_empat_batas_klaim(klien_info):
    """Konsol menampilkan empat batas klaim spesifikasi 6 dengan angka dari params dan model."""
    d = klien_info.get("/info").json()
    assert len(d["batas_klaim"]) == 4
    teks = " ".join(d["batas_klaim"])
    assert "1970" in teks and "1768" in teks and "E3, E6" in teks
    assert any("KAI" in c for c in d["catatan_kewenangan"])
    assert d["status_parameter"] == "dummy"


@pytest.mark.skipif(not (AKAR_REPO / "dashboard" / "dist" / "index.html").exists(), reason="dashboard belum dibangun")
def test_dashboard_disajikan_di_akar(klien_info):
    """Hasil build dashboard disajikan FastAPI di / sehingga demo cukup satu server."""
    r = klien_info.get("/")
    assert r.status_code == 200 and "SIGAP-KA" in r.text
