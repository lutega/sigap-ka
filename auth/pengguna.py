"""
Tujuan      : Layanan pengguna dashboard: akun awal admin, tambah, daftar, nonaktifkan, atur ulang
              password, ubah level, dan autentikasi login.
Lapis       : Infrastruktur (spesifikasi 15).
Sumber      : Tabel pengguna (db/model.py); ADMIN_USER dan ADMIN_PASSWORD di .env.
Masukan     : Sesi database, data pengguna.
Keluaran    : Objek Pengguna atau dict ringkas tanpa hash password.
Keterbatasan: Level hanya admin dan operator. Akun awal dibuat hanya bila tabel pengguna kosong.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth.keamanan import hash_password, verifikasi_password
from config import muat_pengaturan
from db.model import Pengguna

LEVEL_VALID = ("admin", "operator")


class GalatPengguna(ValueError):
    """Operasi pengguna tidak valid (username ganda, level salah, dsb.)."""


def ke_dict(p: Pengguna) -> dict:
    """Pengguna tanpa hash password."""
    return {"id": p.id, "username": p.username, "level": p.level, "aktif": p.aktif,
            "dibuat": p.dibuat, "diperbarui": p.diperbarui}


def cari(sesi: Session, username: str) -> Pengguna | None:
    """Mencari pengguna menurut username."""
    return sesi.scalar(select(Pengguna).where(Pengguna.username == username))


def buat(sesi: Session, username: str, password: str, level: str = "operator") -> Pengguna:
    """Menambah pengguna baru (password di-hash bcrypt)."""
    username = username.strip()
    if not username or not password:
        raise GalatPengguna("username dan password wajib diisi")
    if level not in LEVEL_VALID:
        raise GalatPengguna(f"level harus salah satu dari {LEVEL_VALID}")
    if cari(sesi, username):
        raise GalatPengguna(f"username {username!r} sudah dipakai")
    p = Pengguna(username=username, hash_password=hash_password(password), level=level, aktif=True,
                 dibuat=datetime.now().replace(microsecond=0))
    sesi.add(p)
    sesi.flush()
    return p


def daftar(sesi: Session) -> list[dict]:
    """Semua pengguna (tanpa hash)."""
    return [ke_dict(p) for p in sesi.scalars(select(Pengguna).order_by(Pengguna.id))]


def ubah(sesi: Session, pengguna_id: int, aktif: bool | None = None, level: str | None = None) -> Pengguna:
    """Mengaktifkan/menonaktifkan atau mengubah level pengguna."""
    p = sesi.get(Pengguna, pengguna_id)
    if p is None:
        raise GalatPengguna("pengguna tidak ditemukan")
    if level is not None:
        if level not in LEVEL_VALID:
            raise GalatPengguna(f"level harus salah satu dari {LEVEL_VALID}")
        p.level = level
    if aktif is not None:
        p.aktif = aktif
    _jaga_admin_tersisa(sesi)
    p.diperbarui = datetime.now().replace(microsecond=0)
    sesi.flush()
    return p


def atur_ulang_password(sesi: Session, pengguna_id: int, password_baru: str) -> Pengguna:
    """Mengatur ulang password pengguna (oleh admin)."""
    p = sesi.get(Pengguna, pengguna_id)
    if p is None:
        raise GalatPengguna("pengguna tidak ditemukan")
    if not password_baru:
        raise GalatPengguna("password baru wajib diisi")
    p.hash_password = hash_password(password_baru)
    p.diperbarui = datetime.now().replace(microsecond=0)
    sesi.flush()
    return p


def _jaga_admin_tersisa(sesi: Session) -> None:
    """Mencegah sistem kehilangan admin aktif terakhir."""
    sesi.flush()
    n = sesi.scalar(select(func.count()).select_from(Pengguna).where(
        Pengguna.level == "admin", Pengguna.aktif.is_(True)))
    if not n:
        raise GalatPengguna("harus tersisa minimal satu admin aktif")


def autentikasi(sesi: Session, username: str, password: str) -> Pengguna | None:
    """Pengguna aktif yang cocok dengan username dan password, atau None."""
    p = cari(sesi, username)
    if p is None or not p.aktif or not verifikasi_password(password, p.hash_password):
        return None
    return p


def pastikan_admin_awal(sesi: Session) -> Pengguna | None:
    """Membuat akun awal admin dari ADMIN_USER/ADMIN_PASSWORD bila belum ada pengguna sama sekali."""
    if sesi.scalar(select(func.count()).select_from(Pengguna)):
        return None
    peng = muat_pengaturan()
    return buat(sesi, peng.admin_user, peng.admin_password, "admin")
