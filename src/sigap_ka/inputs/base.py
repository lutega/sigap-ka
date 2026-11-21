"""
Tujuan      : Kontrak bersama modul input: skema keluaran standar (tanggal, zona, nilai, sumber,
              status_data), validator, dan adapter ke tabel standar lapis S lama
              (waktu, lokasi, nilai, satuan, sumber, is_simulated).
Lapis       : S (Sensing).
Sumber      : -
Masukan     : DataFrame keluaran modul input.
Keluaran    : DataFrame tervalidasi; galat GalatSkema bila kontrak dilanggar.
Keterbatasan: Validator memeriksa struktur dan tipe, bukan kebenaran fisik nilai. Kolom tambahan
              (mis. stasiun, catatan_qc) diizinkan.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from config import AKAR_REPO

KOLOM_WAJIB = ["tanggal", "zona", "nilai", "sumber", "status_data"]
STATUS_VALID = ("nyata", "sintetis", "dummy")
ZONA_HUJAN = ("lokal_gubug_karangjati", "hulu_tuntang", "gundih")


class GalatSkema(ValueError):
    """Tabel tidak memenuhi kontrak keluaran modul input."""


def path_data(*bagian: str) -> Path:
    """Path di bawah folder data/ repo, mis. path_data('interim', 'bmkg_clean.csv')."""
    return AKAR_REPO.joinpath("data", *bagian)


def tabel_kosong(kolom_tambahan: Iterable[str] = ()) -> pd.DataFrame:
    """DataFrame kosong berkolom wajib (+ kolom tambahan) dengan tipe yang benar."""
    df = pd.DataFrame({k: pd.Series(dtype="object") for k in list(KOLOM_WAJIB) + list(kolom_tambahan)})
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    df["nilai"] = df["nilai"].astype(float)
    return df


def validasi(df: pd.DataFrame, zona_valid: Iterable[str] | None = None) -> pd.DataFrame:
    """Memeriksa kontrak keluaran modul input.

    Aturan: semua kolom wajib ada; tanggal bertipe datetime; nilai numerik (NaN boleh, berarti
    data kosong/anomali); sumber terisi; status_data salah satu STATUS_VALID; zona termasuk
    zona_valid bila diberikan.
    Parameter:
        df: tabel keluaran.
        zona_valid: daftar zona yang diizinkan (opsional).
    Kembali:
        df yang sama bila valid.
    Galat:
        GalatSkema.
    """
    hilang = [k for k in KOLOM_WAJIB if k not in df.columns]
    if hilang:
        raise GalatSkema(f"kolom wajib hilang: {hilang}")
    if df.empty:
        return df
    if not pd.api.types.is_datetime64_any_dtype(df["tanggal"]):
        raise GalatSkema("kolom tanggal harus bertipe datetime")
    if df["tanggal"].isna().any():
        raise GalatSkema("kolom tanggal tidak boleh kosong")
    if not pd.api.types.is_numeric_dtype(df["nilai"]):
        raise GalatSkema("kolom nilai harus numerik (NaN untuk data kosong)")
    if df["sumber"].isna().any() or (df["sumber"].astype(str).str.strip() == "").any():
        raise GalatSkema("kolom sumber wajib terisi")
    salah = set(df["status_data"]) - set(STATUS_VALID)
    if salah:
        raise GalatSkema(f"status_data tidak dikenal: {sorted(salah)}")
    if zona_valid is not None:
        di_luar = set(df["zona"]) - set(zona_valid)
        if di_luar:
            raise GalatSkema(f"zona tidak dikenal: {sorted(di_luar)}")
    return df


def ke_tabel_standar(df: pd.DataFrame, satuan: str) -> pd.DataFrame:
    """Adapter ke tabel standar lapis S lama (sensing/standar.py) agar bisa disimpan lewat db/repositori.

    Parameter:
        df: tabel berskema KOLOM_WAJIB.
        satuan: satuan nilai (mm, cm, ...).
    Kembali:
        DataFrame kolom waktu, lokasi, nilai, satuan, sumber, is_simulated.
    """
    validasi(df)
    return pd.DataFrame({
        "waktu": df["tanggal"].to_numpy(),
        "lokasi": df["zona"].to_numpy(),
        "nilai": df["nilai"].astype(float).to_numpy(),
        "satuan": satuan,
        "sumber": df["sumber"].to_numpy(),
        "is_simulated": (df["status_data"] != "nyata").to_numpy(),
    })


def simpan_csv(df: pd.DataFrame, path: Path) -> Path:
    """Menyimpan tabel ke CSV UTF-8 (akhir baris LF), membuat folder bila perlu."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
    return path


def baca_csv(path: Path) -> pd.DataFrame:
    """Membaca CSV berskema KOLOM_WAJIB (tanggal diubah ke datetime)."""
    df = pd.read_csv(path, encoding="utf-8")
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    return df
