"""
Tujuan      : Membangkitkan muka air hulu (Glapan) dan indeks air di badan rel dari model
              hujan-limpasan sederhana, sebagai pengisi sementara sampai data BBWS masuk.
Lapis       : S (Sensing), sintetis berlabel.
Sumber      : Model internal: waduk linear dS/dt = R_hulu - S/k (langkah 1 jam, solusi eksak),
              elevasi = dasar + a * S^b; indeks badan rel dari hujan lokal 24 jam.
              Parameter di params.json blok muka_air.sintetis dan muka_air.badan_rel.
Masukan     : Seri hujan hulu (dan lokal untuk indeks badan rel) berformat standar,
              resolusi harian atau jam.
Keluaran    : Tabel standar lokasi 'glapan' dan 'badan_rel', sumber 'muka_air_sintetis',
              is_simulated = True.
Keterbatasan: Model belum dikalibrasi; deck mencatat model sintetis versi lama meleset
              (1768 vs nyata 1970 pada 24 Jan 2025). Model ini dibangun ulang (A-013) dan
              selisihnya terhadap titik nyata dilaporkan apa adanya. Hujan harian dibagi rata
              ke 24 jam (A-019).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import muat_params
from sensing.standar import batas_kualitas, tandai_kualitas, validasi_standar

NAMA_SUMBER = "muka_air_sintetis"


def ke_per_jam(df: pd.DataFrame) -> pd.Series:
    """Mengubah seri hujan standar (harian/jam) menjadi seri per jam (mm/jam).

    Hujan harian dibagi rata ke 24 jam (asumsi A-019). Jam tanpa data dianggap 0.
    Kembali:
        Series berindeks waktu per jam.
    """
    if df.empty:
        return pd.Series(dtype=float)
    potongan = []
    res = df["resolusi_jam"] if "resolusi_jam" in df else pd.Series(1, index=df.index)
    for (waktu, nilai, r) in zip(df["waktu"], df["nilai"], res):
        r = int(r) if pd.notna(r) else 1
        v = 0.0 if pd.isna(nilai) else float(nilai)
        jam = pd.date_range(waktu, periods=r, freq="h")
        potongan.append(pd.Series(v / r, index=jam))
    seri = pd.concat(potongan).groupby(level=0).sum().sort_index()
    penuh = pd.date_range(seri.index.min(), seri.index.max(), freq="h")
    return seri.reindex(penuh, fill_value=0.0)


def hitung_tampungan(hujan_mm_per_jam: np.ndarray, k_jam: float, s_awal: float) -> np.ndarray:
    """Tampungan waduk linear per jam dengan solusi eksak untuk hujan konstan per langkah.

    S_t = S_(t-1) * e^(-1/k) + R_t * k * (1 - e^(-1/k))
    Parameter:
        hujan_mm_per_jam: hujan hulu per jam.
        k_jam: konstanta waduk (jam).
        s_awal: tampungan awal (mm).
    Kembali:
        Array tampungan (mm) sepanjang masukan.
    """
    alfa = np.exp(-1.0 / k_jam)
    s = np.empty(len(hujan_mm_per_jam))
    sebelumnya = s_awal
    for i, r in enumerate(hujan_mm_per_jam):
        sebelumnya = sebelumnya * alfa + r * k_jam * (1.0 - alfa)
        s[i] = sebelumnya
    return s


def elevasi(tampungan: np.ndarray) -> np.ndarray:
    """Elevasi muka air sintetis dari tampungan: dasar + a * S^b (params.json)."""
    p = muat_params().muka_air["sintetis"]
    return p["elevasi_dasar"] + p["pengali_tampungan"] * np.power(np.maximum(tampungan, 0), p["pangkat_tampungan"])


def indeks_badan_rel(hujan_lokal_per_jam: pd.Series) -> pd.Series:
    """Indeks air di badan rel: max(0, hujan lokal 24 jam - ambang) / ambang (0 = belum ada air)."""
    ambang = muat_params().muka_air["badan_rel"]["ambang_hujan_lokal_24j_mm"]
    r24 = hujan_lokal_per_jam.rolling(24, min_periods=1).sum()
    return ((r24 - ambang).clip(lower=0) / ambang).rename("indeks")


def ambil(hujan_hulu: pd.DataFrame, hujan_lokal: pd.DataFrame | None = None) -> dict:
    """Menyiapkan masukan model: hujan hulu (dan lokal) per jam.

    Parameter:
        hujan_hulu: tabel standar hujan hulu.
        hujan_lokal: tabel standar hujan lokal (opsional, untuk indeks badan rel).
    Kembali:
        dict {'hulu': Series per jam, 'lokal': Series per jam atau None}.
    """
    return {"hulu": ke_per_jam(hujan_hulu),
            "lokal": ke_per_jam(hujan_lokal) if hujan_lokal is not None else None}


def ke_format_standar(mentah: dict) -> pd.DataFrame:
    """Menjalankan model dan mengeluarkan tabel standar muka air sintetis."""
    p = muat_params().muka_air
    hulu = mentah["hulu"]
    if hulu.empty:
        return validasi_standar(pd.DataFrame(columns=["waktu", "lokasi", "nilai", "satuan",
                                                      "sumber", "is_simulated"]))
    s = hitung_tampungan(hulu.to_numpy(), p["sintetis"]["konstanta_waduk_jam"],
                         p["sintetis"]["tampungan_awal_mm"])
    bagian = [pd.DataFrame({
        "waktu": hulu.index, "lokasi": "glapan", "nilai": elevasi(s),
        "satuan": "cm (sintetis)", "sumber": NAMA_SUMBER, "is_simulated": True,
    })]
    if mentah.get("lokal") is not None and not mentah["lokal"].empty:
        idx = indeks_badan_rel(mentah["lokal"])
        bagian.append(pd.DataFrame({
            "waktu": idx.index, "lokasi": "badan_rel", "nilai": idx.to_numpy(),
            "satuan": "indeks", "sumber": NAMA_SUMBER, "is_simulated": True,
        }))
    df = pd.concat(bagian, ignore_index=True)
    df["waktu"] = pd.to_datetime(df["waktu"])
    return validasi_standar(df)


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai elevasi sintetis di luar rentang wajar (indeks badan rel hanya dicek >= 0)."""
    b = batas_kualitas()
    glapan = tandai_kualitas(df[df["lokasi"] == "glapan"], b["muka_air_min"], b["muka_air_maks"])
    rel = tandai_kualitas(df[df["lokasi"] == "badan_rel"], 0.0, None)
    return pd.concat([glapan, rel]).sort_index()


def jalankan(hujan_hulu: pd.DataFrame, hujan_lokal: pd.DataFrame | None = None) -> pd.DataFrame:
    """Pipeline ambil -> ke_format_standar -> cek_kualitas."""
    return cek_kualitas(ke_format_standar(ambil(hujan_hulu, hujan_lokal)))
