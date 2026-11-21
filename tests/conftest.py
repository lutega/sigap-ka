"""
Tujuan      : Fixture bersama untuk seluruh tes SIGAP-KA.
Lapis       : QA (lintas lapis).
Sumber      : config/params.json, .env (bila ada).
Masukan     : -
Keluaran    : fixture params per preset dan pembersih cache.
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
