"""
Tujuan      : Model Pydantic untuk request dan response API SIGAP-KA (dokumentasi otomatis /docs).
Lapis       : API.
Sumber      : Spesifikasi 14.2, 15, 16.
Masukan     : Badan permintaan JSON.
Keluaran    : Objek tervalidasi.
Keterbatasan: Respons bertingkat (papan, ringkasan) dikembalikan sebagai dict agar mengikuti struktur
              modul lapis A tanpa duplikasi definisi.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginMasuk(BaseModel):
    """Kredensial login."""

    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class TokenKeluar(BaseModel):
    """Token akses JWT."""

    access_token: str
    token_type: str = "bearer"
    username: str
    level: str


class PenggunaKeluar(BaseModel):
    """Data pengguna tanpa hash password."""

    id: int
    username: str
    level: str
    aktif: bool


class PenggunaBaru(BaseModel):
    """Permintaan menambah pengguna (khusus admin)."""

    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=4, max_length=200)
    level: Literal["admin", "operator"] = "operator"


class PenggunaUbah(BaseModel):
    """Mengaktifkan/menonaktifkan atau mengubah level pengguna."""

    aktif: bool | None = None
    level: Literal["admin", "operator"] | None = None


class PasswordBaru(BaseModel):
    """Atur ulang password oleh admin."""

    password_baru: str = Field(min_length=4, max_length=200)


class KeputusanMasuk(BaseModel):
    """Keputusan operator atas satu tindakan pada jam keputusan."""

    tindakan: str = Field(pattern=r"^T[1-9]$")
    jam_sebelum_t0: int = Field(ge=0)
    keputusan: Literal["setujui", "tolak", "batalkan"]
    alasan: str | None = Field(default=None, max_length=500)
    sesi_demo_id: str | None = None


class KurvaHitungMasuk(BaseModel):
    """Hitung ulang kurva dengan parameter slider (tidak disimpan ke params.json, FR-G4)."""

    tindakan: str = Field(pattern=r"^T[1-9]$")
    preset: Literal["low", "base", "high"] | None = None
    C: float | None = Field(default=None, gt=0)
    L: float | None = Field(default=None, gt=0)
    P: float | None = Field(default=None, ge=0)
    waktu_siap_jam: int | None = Field(default=None, ge=0)
    faktor_L: float = Field(default=1.0, gt=0)


class SimulasiMasuk(BaseModel):
    """Permintaan menjalankan simulasi (khusus admin)."""

    preset: Literal["low", "base", "high"] | None = None
    n: int = Field(default=300, ge=1, le=2000)
    seed: int | None = None


class DemoMulai(BaseModel):
    """Memulai sesi demo."""

    episode_id: str
    kecepatan_detik_per_jam: float | None = Field(default=None, gt=0, le=60)
