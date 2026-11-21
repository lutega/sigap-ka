"""
Tujuan      : Kontrak bersama semua modul sumber data lapis S: kolom tabel standar, validasi,
              penanda kualitas, penyimpanan data mentah (data/raw) dan olahan (data/processed).
Lapis       : S (Sensing).
Sumber      : -
Masukan     : DataFrame dari modul sumber.
Keluaran    : DataFrame tervalidasi dengan kolom waktu, lokasi, nilai, satuan, sumber,
              is_simulated (+ kolom tambahan khusus sumber), serta berkas CSV/mentah.
Keterbatasan: Validasi hanya memeriksa struktur dan tipe, bukan kebenaran fisik nilai.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import AKAR_REPO, muat_params, muat_pengaturan

KOLOM_STANDAR = ["waktu", "lokasi", "nilai", "satuan", "sumber", "is_simulated"]
KOLOM_PRAKIRAAN = ["waktu_terbit"] + KOLOM_STANDAR
DIR_MENTAH = AKAR_REPO / "data" / "raw"
DIR_MANUAL = AKAR_REPO / "data" / "manual"


class SumberTidakTersedia(Exception):
    """Sumber tidak dapat dipakai: kredensial kosong, berkas bersurat belum ada, atau jaringan gagal."""


def dir_olahan() -> Path:
    """Folder data olahan dari DATA_DIR di .env (bawaan data/processed)."""
    peng = muat_pengaturan()
    return peng.path_mutlak(peng.data_dir)


def tabel_kosong(prakiraan: bool = False) -> pd.DataFrame:
    """DataFrame kosong berkolom standar.

    Parameter:
        prakiraan: True untuk menambahkan kolom waktu_terbit.
    """
    return pd.DataFrame(columns=KOLOM_PRAKIRAAN if prakiraan else KOLOM_STANDAR)


def validasi_standar(df: pd.DataFrame, prakiraan: bool = False, deret_waktu: bool = True) -> pd.DataFrame:
    """Memeriksa bahwa DataFrame memenuhi kontrak tabel standar.

    Parameter:
        df: tabel dari modul sumber.
        prakiraan: wajibkan kolom waktu_terbit dan waktu_terbit <= waktu valid.
        deret_waktu: wajibkan kolom waktu bertipe datetime.
    Kembali:
        df yang sama bila valid.
    Galat:
        ValueError bila kolom hilang atau tipe salah.
    """
    wajib = KOLOM_PRAKIRAAN if prakiraan else KOLOM_STANDAR
    hilang = [k for k in wajib if k not in df.columns]
    if hilang:
        raise ValueError(f"kolom standar hilang: {hilang}")
    if df.empty:
        return df
    if not df["is_simulated"].map(lambda v: isinstance(v, (bool, np.bool_))).all():
        raise ValueError("is_simulated harus boolean")
    if df["sumber"].isna().any() or (df["sumber"].astype(str).str.len() == 0).any():
        raise ValueError("kolom sumber wajib terisi")
    if deret_waktu and not pd.api.types.is_datetime64_any_dtype(df["waktu"]):
        raise ValueError("kolom waktu harus bertipe datetime")
    if prakiraan:
        if not pd.api.types.is_datetime64_any_dtype(df["waktu_terbit"]):
            raise ValueError("kolom waktu_terbit harus bertipe datetime")
        if (df["waktu_terbit"] > df["waktu"]).any():
            raise ValueError("prakiraan tidak boleh berlaku sebelum terbit")
    return df


def tandai_kualitas(df: pd.DataFrame, batas_bawah: float | None = 0.0,
                    batas_atas: float | None = None) -> pd.DataFrame:
    """Menambahkan kolom kualitas: 'kosong' (nilai hilang), 'janggal' (di luar batas), 'baik'.

    Parameter:
        df: tabel standar.
        batas_bawah, batas_atas: rentang wajar nilai (dari params.json blok kualitas).
    Kembali:
        Salinan df dengan kolom kualitas.
    """
    d = df.copy()
    nilai = pd.to_numeric(d["nilai"], errors="coerce")
    kualitas = np.where(nilai.isna(), "kosong", "baik").astype(object)
    if batas_bawah is not None:
        kualitas[(nilai < batas_bawah).to_numpy()] = "janggal"
    if batas_atas is not None:
        kualitas[(nilai > batas_atas).to_numpy()] = "janggal"
    d["kualitas"] = kualitas
    return d


def batas_kualitas() -> dict[str, float]:
    """Batas wajar nilai dari params.json (blok kualitas)."""
    return muat_params().mentah["kualitas"]


def simpan_mentah(nama_sumber: str, isi: Any, ekstensi: str = "json",
                  waktu: datetime | None = None) -> Path:
    """Menyimpan respons mentah sumber ke data/raw/<sumber>/<cap waktu>.<ekstensi>.

    Parameter:
        isi: dict/list (disimpan JSON), str, atau bytes.
    Kembali:
        Path berkas.
    """
    folder = DIR_MENTAH / nama_sumber
    folder.mkdir(parents=True, exist_ok=True)
    cap = (waktu or datetime.now()).strftime("%Y%m%dT%H%M%S%f")
    path = folder / f"{cap}.{ekstensi}"
    if isinstance(isi, (dict, list)):
        path.write_text(json.dumps(isi, ensure_ascii=False), encoding="utf-8")
    elif isinstance(isi, bytes):
        path.write_bytes(isi)
    else:
        path.write_text(str(isi), encoding="utf-8")
    return path


def simpan_olahan(nama_file: str, df: pd.DataFrame, kunci: list[str] | None = None) -> Path:
    """Menyimpan tabel olahan ke data/processed/<nama_file>.csv, digabung dengan isi lama.

    Parameter:
        nama_file: nama tanpa ekstensi.
        df: tabel baru.
        kunci: kolom kunci untuk membuang duplikat (baris baru menang).
    Kembali:
        Path berkas CSV.
    """
    folder = dir_olahan()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{nama_file}.csv"
    gabung = df
    if path.exists() and kunci:
        lama = baca_olahan(nama_file)
        gabung = pd.concat([lama, df], ignore_index=True)
        gabung = gabung.drop_duplicates(subset=kunci, keep="last")
    if kunci:
        gabung = gabung.sort_values(kunci).reset_index(drop=True)
    gabung.to_csv(path, index=False, encoding="utf-8")
    return path


def baca_olahan(nama_file: str) -> pd.DataFrame:
    """Membaca data/processed/<nama_file>.csv; kolom waktu* diubah ke datetime.

    Kembali:
        DataFrame; kosong bila berkas belum ada.
    """
    path = dir_olahan() / f"{nama_file}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8")
    for kol in df.columns:
        if kol.startswith("waktu") or kol in ("jam_tutup", "jam_buka"):
            df[kol] = pd.to_datetime(df[kol], errors="coerce")
    if "is_simulated" in df.columns:
        df["is_simulated"] = df["is_simulated"].map(
            lambda v: str(v).strip().lower() in ("true", "1", "ya")).astype(bool)
    return df


def ke_bool(nilai: Any) -> bool:
    """Mengubah teks 'true/false/ya/tidak/1/0' menjadi bool Python."""
    return str(nilai).strip().lower() in ("true", "1", "ya", "yes")
