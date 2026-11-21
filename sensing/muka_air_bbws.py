"""
Tujuan      : Membaca seri waktu muka air dan pos hujan BBWS Pemali Juana untuk kalibrasi model
              muka air (data tambahan, opsional).
Lapis       : S (Sensing), data tambahan (bersurat).
Sumber      : Surat permohonan ke BBWS Pemali Juana; setelah diterima, data disalin ke
              data/manual/bbws.csv dengan kolom standar (waktu, lokasi, nilai, satuan).
Masukan     : Berkas CSV (bila sudah ada).
Keluaran    : Tabel standar (sumber 'bbws', is_simulated = False).
Keterbatasan: Data belum tersedia; tanpa berkas, modul memberi SumberTidakTersedia dan sistem
              tetap berjalan dengan muka air sintetis berlabel (NFR-5).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sensing.standar import DIR_MANUAL, SumberTidakTersedia, batas_kualitas, tandai_kualitas, validasi_standar

NAMA_SUMBER = "bbws"
BERKAS = "bbws.csv"


def ambil(path: Path | None = None) -> pd.DataFrame:
    """Membaca CSV BBWS. Galat SumberTidakTersedia bila data bersurat belum diterima."""
    path = path or DIR_MANUAL / BERKAS
    if not path.exists():
        raise SumberTidakTersedia("data BBWS (bersurat) belum tersedia")
    return pd.read_csv(path, encoding="utf-8")


def ke_format_standar(mentah: pd.DataFrame) -> pd.DataFrame:
    """Mengubah CSV BBWS (waktu, lokasi, nilai, satuan) menjadi tabel standar."""
    df = pd.DataFrame({
        "waktu": pd.to_datetime(mentah["waktu"]),
        "lokasi": mentah["lokasi"].astype(str),
        "nilai": pd.to_numeric(mentah["nilai"], errors="coerce"),
        "satuan": mentah["satuan"].astype(str),
        "sumber": NAMA_SUMBER,
        "is_simulated": False,
    })
    return validasi_standar(df)


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai elevasi kosong atau di luar rentang wajar."""
    b = batas_kualitas()
    return tandai_kualitas(df, b["muka_air_min"], b["muka_air_maks"])


def jalankan(path: Path | None = None) -> pd.DataFrame:
    """Pipeline ambil -> ke_format_standar -> cek_kualitas."""
    return cek_kualitas(ke_format_standar(ambil(path)))
