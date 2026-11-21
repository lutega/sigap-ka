"""
Tujuan      : Membuat aplikasi FastAPI SIGAP-KA: mendaftarkan router, CORS, inisialisasi database
              dan akun awal admin saat start, serta menyajikan dashboard hasil build (bila ada).
Lapis       : API (lapisan tipis di atas modul S, I, G, A, simulasi).
Sumber      : api/routers/*, db/inisialisasi.py, auth/pengguna.py.
Masukan     : DATABASE_URL dan pengaturan .env.
Keluaran    : Objek aplikasi ASGI. Jalankan: uvicorn api.main:app --port 8000
Keterbatasan: Tidak ada endpoint yang menetapkan atau mengembalikan status jalur aman.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from action.penjaga_klaim import KlaimAmanTerlarang
from api.deps import Konteks
from api.routers import auth, data, info, kurva, pengguna, prediksi, simulasi, tindakan
from auth.pengguna import pastikan_admin_awal
from config import AKAR_REPO, muat_pengaturan
from db.inisialisasi import inisialisasi
from db.koneksi import buat_engine

DIR_DASHBOARD = AKAR_REPO / "dashboard" / "dist"


def buat_aplikasi(database_url: str | None = None, siapkan_db: bool = True) -> FastAPI:
    """Membuat aplikasi FastAPI.

    Parameter:
        database_url: URL database (bawaan DATABASE_URL); 'sqlite://' untuk tes.
        siapkan_db: buat skema dan akun awal admin saat start.
    """
    engine = buat_engine(database_url)

    @asynccontextmanager
    async def siklus(app: FastAPI):
        if siapkan_db:
            inisialisasi(engine)
            with app.state.konteks.pabrik() as sesi:
                pastikan_admin_awal(sesi)
                sesi.commit()
        yield
        engine.dispose()

    app = FastAPI(
        title="SIGAP-KA API",
        version="0.1.0",
        description=("Sistem pendukung keputusan kontinjensi banjir koridor Brumbung-Karangjati. "
                     "Usulan bersifat saran; keputusan pada operator dan status jalur ditetapkan KAI. "
                     "Parameter biaya masih dummy."),
        lifespan=siklus,
    )
    app.state.konteks = Konteks(engine)
    app.add_middleware(CORSMiddleware, allow_origins=muat_pengaturan().daftar_cors,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    for r in (auth, pengguna, data, info, prediksi, kurva, tindakan, simulasi):
        app.include_router(r.router)
    try:
        from api.routers import demo
        app.include_router(demo.router)
    except ImportError:  # pragma: no cover - router demo ditambahkan di tahap 9
        pass

    @app.exception_handler(KlaimAmanTerlarang)
    async def _tahan_klaim(request: Request, galat: KlaimAmanTerlarang):
        return JSONResponse(status_code=500, content={"detail": "keluaran ditahan penjaga klaim status jalur"})

    @app.get("/kesehatan", tags=["sistem"])
    def kesehatan():
        """Pemeriksaan hidup layanan (tanpa token)."""
        return {"status": "berjalan", "layanan": "SIGAP-KA API"}

    if (DIR_DASHBOARD / "assets").exists():  # dashboard hasil build disajikan dari server yang sama
        app.mount("/assets", StaticFiles(directory=DIR_DASHBOARD / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        def beranda():
            return FileResponse(DIR_DASHBOARD / "index.html")

    return app


app = buat_aplikasi()
