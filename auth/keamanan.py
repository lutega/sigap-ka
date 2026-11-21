"""
Tujuan      : Hash dan verifikasi password pengguna dashboard dengan bcrypt.
Lapis       : Infrastruktur (login dan manajemen pengguna, spesifikasi 15).
Sumber      : Pustaka bcrypt.
Masukan     : Password teks.
Keluaran    : Hash bcrypt (string) atau hasil verifikasi (bool).
Keterbatasan: bcrypt hanya memakai 72 byte pertama password; password lebih panjang dipotong.
"""

from __future__ import annotations

import bcrypt

BATAS_BYTE = 72


def hash_password(password: str) -> str:
    """Membuat hash bcrypt (dengan salt acak) dari password."""
    return bcrypt.hashpw(password.encode("utf-8")[:BATAS_BYTE], bcrypt.gensalt()).decode("ascii")


def verifikasi_password(password: str, hash_tersimpan: str) -> bool:
    """True bila password cocok dengan hash bcrypt tersimpan."""
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:BATAS_BYTE], hash_tersimpan.encode("ascii"))
    except ValueError:
        return False
