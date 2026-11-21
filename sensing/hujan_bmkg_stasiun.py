"""
Tujuan      : Membaca data pos hujan, AWS, atau radar BMKG sekitar Semarang untuk koreksi data
              satelit (data tambahan, opsional).
Lapis       : S (Sensing), data tambahan (bersurat).
Sumber      : Surat permohonan ke BMKG; setelah diterima, data disalin ke
              data/manual/bmkg_stasiun.csv dengan kolom waktu, lokasi, nilai, satuan, resolusi_jam.
Masukan     : Berkas CSV (bila sudah ada).
Keluaran    : Tabel standar (sumber 'bmkg_stasiun', is_simulated = False).
Keterbatasan: Data belum tersedia; tanpa berkas, modul memberi SumberTidakTersedia (NFR-5).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sensing.standar import DIR_MANUAL, SumberTidakTersedia, batas_kualitas, tandai_kualitas, validasi_standar

NAMA_SUMBER = "bmkg_stasiun"
BERKAS = "bmkg_stasiun.csv"


def ambil(path: Path | None = None) -> pd.DataFrame:
    """Membaca CSV stasiun BMKG. Galat SumberTidakTersedia bila data bersurat belum diterima."""
    path = path or DIR_MANUAL / BERKAS
    if not path.exists():
        raise SumberTidakTersedia("data stasiun BMKG (bersurat) belum tersedia")
    return pd.read_csv(path, encoding="utf-8")


def ke_format_standar(mentah: pd.DataFrame) -> pd.DataFrame:
    """Mengubah CSV stasiun menjadi tabel standar hujan."""
    df = pd.DataFrame({
        "waktu": pd.to_datetime(mentah["waktu"]),
        "lokasi": mentah["lokasi"].astype(str),
        "nilai": pd.to_numeric(mentah["nilai"], errors="coerce"),
        "satuan": mentah.get("satuan", "mm"),
        "sumber": NAMA_SUMBER,
        "is_simulated": False,
        "resolusi_jam": pd.to_numeric(mentah.get("resolusi_jam", 1), errors="coerce"),
    })
    return validasi_standar(df)


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai nilai kosong atau di luar 0..hujan_harian_maks_mm."""
    return tandai_kualitas(df, 0.0, batas_kualitas()["hujan_harian_maks_mm"])


def jalankan(path: Path | None = None) -> pd.DataFrame:
    """Pipeline ambil -> ke_format_standar -> cek_kualitas."""
    return cek_kualitas(ke_format_standar(ambil(path)))
