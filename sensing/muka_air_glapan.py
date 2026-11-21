"""
Tujuan      : Membaca elevasi muka air Bendung Glapan dari rilis BNPB (bukti hulu untuk tindakan
              memutar dan siaga Dapsus/AMUS).
Lapis       : S (Sensing), data inti (sebagian nyata).
Sumber      : Rilis BNPB, dicatat manual di data/manual/muka_air_glapan.csv (kolom waktu,
              jam_diketahui, nilai, satuan, sumber, catatan). Saat ini satu titik nyata:
              1970 pada 24 Jan 2025 (ambang Awas 1905).
Masukan     : Berkas CSV manual.
Keluaran    : Tabel standar (lokasi = 'glapan', is_simulated = False).
Keterbatasan: Hanya satu titik; jam pembacaan tidak diketahui sehingga diletakkan di akhir hari
              agar tidak dipakai model sebelum waktunya. Satuan mengikuti rilis (A-007).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sensing.standar import (
    DIR_MANUAL,
    SumberTidakTersedia,
    batas_kualitas,
    ke_bool,
    tandai_kualitas,
    validasi_standar,
)

NAMA_SUMBER = "glapan_bnpb"
BERKAS = "muka_air_glapan.csv"


def ambil(path: Path | None = None) -> pd.DataFrame:
    """Membaca CSV manual muka air Glapan.

    Galat:
        SumberTidakTersedia bila berkas belum ada.
    """
    path = path or DIR_MANUAL / BERKAS
    if not path.exists():
        raise SumberTidakTersedia(f"berkas manual {path.name} belum ada")
    return pd.read_csv(path, encoding="utf-8")


def ke_format_standar(mentah: pd.DataFrame) -> pd.DataFrame:
    """Mengubah CSV manual menjadi tabel standar (catatan dan jam_diketahui dipertahankan)."""
    df = pd.DataFrame({
        "waktu": pd.to_datetime(mentah["waktu"]),
        "lokasi": "glapan",
        "nilai": pd.to_numeric(mentah["nilai"], errors="coerce"),
        "satuan": mentah.get("satuan", "cm").fillna("cm") if "satuan" in mentah else "cm",
        "sumber": NAMA_SUMBER,
        "is_simulated": False,
        "jam_diketahui": mentah["jam_diketahui"].map(ke_bool) if "jam_diketahui" in mentah else True,
        "tautan": mentah.get("sumber", ""),
        "catatan": mentah.get("catatan", ""),
    })
    return validasi_standar(df)


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai elevasi kosong atau di luar rentang wajar params.json."""
    b = batas_kualitas()
    return tandai_kualitas(df, b["muka_air_min"], b["muka_air_maks"])


def jalankan(path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pipeline ambil -> ke_format_standar -> cek_kualitas."""
    mentah = ambil(path)
    return cek_kualitas(ke_format_standar(mentah)), mentah
