"""
Tujuan      : Fixture bersama untuk seluruh tes SIGAP-KA.
Lapis       : QA (lintas lapis).
Sumber      : config/params.json, .env (bila ada).
Masukan     : -
Keluaran    : fixture params per preset, engine database uji, dan pembersih cache.
Keterbatasan: Tes bertanda db butuh TimescaleDB dari docker compose; dilewati bila tidak terjangkau.
"""

import pytest

from config import muat_params, reset_cache


@pytest.fixture(autouse=True)
def _bersihkan_cache_pengaturan():
    """Memastikan setiap tes membaca konfigurasi segar."""
    reset_cache()
    yield
    reset_cache()


@pytest.fixture(params=["low", "base", "high"])
def params_semua_preset(request):
    """ParamsAktif untuk tiap preset (tes berparameter)."""
    return muat_params(request.param)


@pytest.fixture
def params_base():
    """ParamsAktif preset base."""
    return muat_params("base")


@pytest.fixture
def engine_sqlite():
    """Engine SQLite di memori dengan skema SIGAP-KA (tanpa fitur TimescaleDB)."""
    from db.inisialisasi import inisialisasi
    from db.koneksi import buat_engine
    eng = buat_engine("sqlite://")
    inisialisasi(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def sesi_sqlite(engine_sqlite):
    """Sesi pada database SQLite di memori."""
    from db.koneksi import pabrik_sesi
    sesi = pabrik_sesi(engine_sqlite)()
    yield sesi
    sesi.close()


@pytest.fixture(scope="session")
def engine_pg():
    """Engine ke database uji TimescaleDB (DATABASE_URL_TEST); tes dilewati bila tidak terjangkau."""
    from sqlalchemy import text

    from config import muat_pengaturan
    from db.inisialisasi import hapus_semua, inisialisasi
    from db.koneksi import buat_engine
    eng = buat_engine(muat_pengaturan().database_url_test)
    try:
        with eng.connect() as kon:
            kon.execute(text("SELECT 1"))
    except Exception as galat:  # pragma: no cover - bergantung lingkungan
        pytest.skip(f"TimescaleDB uji tidak terjangkau: {galat.__class__.__name__}")
    hapus_semua(eng)
    inisialisasi(eng)
    yield eng
    eng.dispose()
