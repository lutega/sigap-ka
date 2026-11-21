"""
Tujuan      : Dependensi FastAPI untuk otorisasi: wajib token JWT yang valid untuk semua endpoint
              (kecuali login), dan wajib level admin untuk pengelolaan pengguna, simulasi, serta
              reset demo.
Lapis       : Infrastruktur (spesifikasi 15).
Sumber      : auth/token.py, auth/pengguna.py, api/deps.py (sesi database).
Masukan     : Header Authorization: Bearer <token>.
Keluaran    : dict pengguna aktif {id, username, level}; HTTP 401/403 bila gagal.
Keterbatasan: Token tidak dicabut saat pengguna dinonaktifkan, tetapi status aktif diperiksa ulang
              di database pada setiap permintaan.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.deps import ambil_sesi
from auth.pengguna import cari
from auth.token import TokenTidakValid, baca_token

skema_bearer = HTTPBearer(auto_error=False)


def pengguna_aktif(kredensial: HTTPAuthorizationCredentials | None = Depends(skema_bearer),
                   sesi: Session = Depends(ambil_sesi)) -> dict:
    """Pengguna dari token; 401 bila token tidak ada/tidak valid atau akun nonaktif."""
    if kredensial is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token diperlukan",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = baca_token(kredensial.credentials)
    except TokenTidakValid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token tidak valid atau kedaluwarsa",
                            headers={"WWW-Authenticate": "Bearer"})
    p = cari(sesi, payload.get("sub", ""))
    if p is None or not p.aktif:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "akun tidak aktif")
    return {"id": p.id, "username": p.username, "level": p.level}


def wajib_admin(pengguna: dict = Depends(pengguna_aktif)) -> dict:
    """Hanya admin; 403 untuk operator."""
    if pengguna["level"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "khusus admin")
    return pengguna
