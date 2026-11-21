"""
Tujuan      : Endpoint pengelolaan pengguna khusus admin: daftar, tambah, nonaktifkan/ubah level,
              atur ulang password.
Lapis       : API (spesifikasi 15).
Sumber      : auth/pengguna.py.
Masukan     : Data pengguna dari dashboard admin.
Keluaran    : Data pengguna tanpa hash password.
Keterbatasan: Sistem menolak perubahan yang menghapus admin aktif terakhir.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import ambil_sesi
from api.schemas import PasswordBaru, PenggunaBaru, PenggunaKeluar, PenggunaUbah
from auth import pengguna as layanan
from auth.dependensi import wajib_admin

router = APIRouter(prefix="/pengguna", tags=["pengguna"], dependencies=[Depends(wajib_admin)])


def _keluar(p) -> PenggunaKeluar:
    """Objek ORM pengguna menjadi skema keluaran."""
    return PenggunaKeluar(id=p.id, username=p.username, level=p.level, aktif=p.aktif)


@router.get("", response_model=list[PenggunaKeluar])
def daftar(sesi: Session = Depends(ambil_sesi)) -> list[PenggunaKeluar]:
    """Daftar semua pengguna."""
    return [PenggunaKeluar(**{k: v for k, v in d.items() if k in PenggunaKeluar.model_fields})
            for d in layanan.daftar(sesi)]


@router.post("", response_model=PenggunaKeluar, status_code=status.HTTP_201_CREATED)
def tambah(masuk: PenggunaBaru, sesi: Session = Depends(ambil_sesi)) -> PenggunaKeluar:
    """Menambah pengguna baru."""
    try:
        return _keluar(layanan.buat(sesi, masuk.username, masuk.password, masuk.level))
    except layanan.GalatPengguna as galat:
        raise HTTPException(status.HTTP_409_CONFLICT, str(galat))


@router.patch("/{pengguna_id}", response_model=PenggunaKeluar)
def ubah(pengguna_id: int, masuk: PenggunaUbah, sesi: Session = Depends(ambil_sesi)) -> PenggunaKeluar:
    """Menonaktifkan/mengaktifkan atau mengubah level pengguna."""
    try:
        return _keluar(layanan.ubah(sesi, pengguna_id, aktif=masuk.aktif, level=masuk.level))
    except layanan.GalatPengguna as galat:
        kode = status.HTTP_404_NOT_FOUND if "tidak ditemukan" in str(galat) else status.HTTP_409_CONFLICT
        raise HTTPException(kode, str(galat))


@router.post("/{pengguna_id}/atur-ulang-password", response_model=PenggunaKeluar)
def atur_ulang(pengguna_id: int, masuk: PasswordBaru, sesi: Session = Depends(ambil_sesi)) -> PenggunaKeluar:
    """Mengatur ulang password pengguna."""
    try:
        return _keluar(layanan.atur_ulang_password(sesi, pengguna_id, masuk.password_baru))
    except layanan.GalatPengguna as galat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(galat))
