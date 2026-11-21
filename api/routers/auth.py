"""
Tujuan      : Endpoint login (POST /auth/login) dan identitas pengguna (GET /auth/saya).
Lapis       : API (spesifikasi 15).
Sumber      : auth/pengguna.py, auth/token.py.
Masukan     : Username dan password.
Keluaran    : Token JWT dan level pengguna.
Keterbatasan: Akun awal admin/admin hanya untuk prototipe dan demo; ganti lewat .env di luar demo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import ambil_sesi
from api.schemas import LoginMasuk, PenggunaKeluar, TokenKeluar
from auth.dependensi import pengguna_aktif
from auth.pengguna import autentikasi
from auth.token import buat_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenKeluar)
def login(masuk: LoginMasuk, sesi: Session = Depends(ambil_sesi)) -> TokenKeluar:
    """Login dengan username dan password; mengembalikan token JWT."""
    p = autentikasi(sesi, masuk.username, masuk.password)
    if p is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "username atau password salah")
    return TokenKeluar(access_token=buat_token(p.username, p.level), username=p.username, level=p.level)


@router.get("/saya", response_model=PenggunaKeluar)
def saya(pengguna: dict = Depends(pengguna_aktif)) -> PenggunaKeluar:
    """Identitas pengguna dari token."""
    return PenggunaKeluar(id=pengguna["id"], username=pengguna["username"], level=pengguna["level"], aktif=True)
