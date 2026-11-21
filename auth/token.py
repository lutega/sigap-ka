"""
Tujuan      : Membuat dan membaca token JWT untuk sesi login dashboard.
Lapis       : Infrastruktur (spesifikasi 15).
Sumber      : PyJWT, algoritma HS256; rahasia JWT_SECRET dan masa berlaku JWT_MENIT_KEDALUWARSA di .env.
Masukan     : Username dan level pengguna; token dari header Authorization.
Keluaran    : Token string; payload {sub, level, exp, iat}.
Keterbatasan: Rahasia bawaan hanya untuk pengembangan/demo; wajib diganti di luar demo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from config import muat_pengaturan

ALGORITMA = "HS256"


class TokenTidakValid(Exception):
    """Token kedaluwarsa, rusak, atau ditandatangani rahasia lain."""


def buat_token(username: str, level: str, menit: int | None = None) -> str:
    """Membuat token JWT bertanda tangan untuk pengguna."""
    peng = muat_pengaturan()
    sekarang = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "level": level,
        "iat": sekarang,
        "exp": sekarang + timedelta(minutes=menit or peng.jwt_menit_kedaluwarsa),
    }
    return jwt.encode(payload, peng.jwt_secret, algorithm=ALGORITMA)


def baca_token(token: str) -> dict:
    """Memverifikasi token dan mengembalikan payload.

    Galat:
        TokenTidakValid bila tanda tangan salah, kedaluwarsa, atau format rusak.
    """
    try:
        return jwt.decode(token, muat_pengaturan().jwt_secret, algorithms=[ALGORITMA])
    except jwt.PyJWTError as galat:
        raise TokenTidakValid(str(galat)) from galat
