"""
Tujuan      : Menyediakan jadwal 4-6 KA yang melewati Gubug (nomor, relasi, jam lewat).
Lapis       : S (Sensing), data inti.
Sumber      : Jadwal publik KAI, diisi manual di data/manual/jadwal_ka.csv (kolom nomor, relasi,
              jam_lewat_gubug, sumber). Bila berkas belum ada, dipakai placeholder KA-A s.d. KA-F
              dari params.json (jadwal_dummy) dengan is_simulated = True.
Masukan     : Berkas CSV manual (opsional).
Keluaran    : Tabel standar (waktu = jam lewat pada tanggal acuan 1900-01-01, lokasi 'gubug',
              nilai kosong, satuan '', sumber, is_simulated) + kolom nomor, relasi, jam_lewat_gubug.
Keterbatasan: Jadwal nyata belum diisi; placeholder bukan jadwal KAI.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import muat_params
from sensing.standar import DIR_MANUAL, validasi_standar

NAMA_SUMBER = "jadwal_ka"
BERKAS = "jadwal_ka.csv"


def ambil(path: Path | None = None) -> pd.DataFrame:
    """Membaca jadwal manual; bila belum ada, membangkitkan placeholder dummy dari params.json.

    Kembali:
        DataFrame mentah dengan kolom nomor, relasi, jam_lewat_gubug, sumber, is_simulated.
    """
    path = path or DIR_MANUAL / BERKAS
    if path.exists():
        df = pd.read_csv(path, encoding="utf-8", dtype=str)
        df["is_simulated"] = False
        return df
    dummy = muat_params().jadwal_dummy
    df = pd.DataFrame(dummy["ka"])
    df["sumber"] = "placeholder params.json (jadwal_dummy)"
    df["is_simulated"] = True  # data dummy selalu berlabel
    return df


def ke_format_standar(mentah: pd.DataFrame) -> pd.DataFrame:
    """Mengubah jadwal menjadi tabel standar + kolom jadwal."""
    jam = pd.to_datetime("1900-01-01 " + mentah["jam_lewat_gubug"].astype(str), format="%Y-%m-%d %H:%M")
    df = pd.DataFrame({
        "waktu": jam,
        "lokasi": "gubug",
        "nilai": float("nan"),
        "satuan": "",
        "sumber": NAMA_SUMBER,
        "is_simulated": mentah["is_simulated"].astype(bool),
        "nomor": mentah["nomor"],
        "relasi": mentah["relasi"],
        "jam_lewat_gubug": mentah["jam_lewat_gubug"],
        "asal": mentah.get("sumber", ""),
    })
    return validasi_standar(df)


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai nomor KA ganda atau jam tidak valid sebagai janggal."""
    d = df.copy()
    ganda = d["nomor"].duplicated(keep=False)
    d["kualitas"] = ["janggal" if g or pd.isna(w) else "baik" for g, w in zip(ganda, d["waktu"])]
    return d


def ke_baris_db(df: pd.DataFrame) -> pd.DataFrame:
    """Memetakan ke kolom tabel jadwal_ka."""
    return pd.DataFrame({"nomor": df["nomor"], "relasi": df["relasi"],
                         "jam_lewat_gubug": df["jam_lewat_gubug"], "sumber": df["asal"],
                         "is_simulated": df["is_simulated"]})


def jalankan(path: Path | None = None) -> pd.DataFrame:
    """Pipeline ambil -> ke_format_standar -> cek_kualitas."""
    return cek_kualitas(ke_format_standar(ambil(path)))
