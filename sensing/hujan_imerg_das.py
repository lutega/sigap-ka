"""
Tujuan      : Hujan hulu Tuntang sebagai RERATA beberapa sel GPM IMERG yang mendekati daerah
              tangkapan (DAS) Tuntang di hulu Bendung Glapan, bukan satu sel titik.
Lapis       : S (Sensing), turunan sumber GPM IMERG.
Sumber      : Giovanni Time Series API lewat sensing/hujan_gpm_imerg.ambil_deret (token Earthdata);
              daftar sel di params.json blok das_tuntang (perkiraan dari peta, A-063).
Masukan     : Rentang tanggal, produk ('late' atau 'final').
Keluaran    : Tabel standar per sel (lokasi 'das_1'..'das_n', sumber gpm_imerg_<produk>_sel) dan
              rerata DAS (lokasi 'hulu', sumber gpm_imerg_<produk>_das); is_simulated = False.
              Disimpan ke data/processed/hujan_gpm_imerg_das.csv oleh sensing.jalankan imerg-das.
Keterbatasan: Kotak sel hanya mendekati batas DAS (belum memakai poligon DAS BBWS Pemali-Juana);
              rerata tak berbobot luas. Hari dengan kurang dari porsi_sel_minimum sel terisi = NaN.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import requests

from config import muat_params
from sensing import hujan_gpm_imerg
from sensing.standar import batas_kualitas, tandai_kualitas, validasi_standar

NAMA_SUMBER = "gpm_imerg_das"


def daftar_sel() -> list[dict]:
    """Daftar sel DAS dari params.json: [{'id': 'das_1', 'lat': .., 'lon': ..}, ...]."""
    konf = muat_params().mentah["das_tuntang"]
    return [{"id": f"das_{i + 1}", "lat": lat, "lon": lon} for i, (lat, lon) in enumerate(konf["sel"])]


def ambil(mulai: date, selesai: date, produk: str = "late", sesi_http: requests.Session | None = None,
          token: str | None = None) -> list[dict]:
    """Mengunduh deret harian IMERG untuk setiap sel DAS (satu permintaan Giovanni per sel)."""
    return [hujan_gpm_imerg.ambil_deret(s["id"], mulai, selesai, produk, sesi_http=sesi_http, token=token,
                                        titik={"lat": s["lat"], "lon": s["lon"]})
            for s in daftar_sel()]


def ke_format_standar(daftar: list[dict], porsi_sel_minimum: float | None = None) -> pd.DataFrame:
    """Per sel menjadi tabel standar, ditambah baris rerata DAS (lokasi 'hulu').

    Parameter:
        porsi_sel_minimum: porsi sel yang harus terisi agar rerata hari itu dihitung (bawaan params).
    """
    if porsi_sel_minimum is None:
        porsi_sel_minimum = float(muat_params().mentah["das_tuntang"]["porsi_sel_minimum"])
    per_sel = []
    for mentah in daftar:
        d = hujan_gpm_imerg.ke_format_standar_deret(mentah)
        per_sel.append(d.assign(sumber=d["sumber"] + "_sel"))
    sel = pd.concat(per_sel, ignore_index=True)
    jumlah = sel["lokasi"].nunique()
    g = sel.groupby("waktu")["nilai"]
    rerata = g.mean().where(g.count() >= porsi_sel_minimum * jumlah)
    produk = daftar[0]["produk"]
    das = pd.DataFrame({
        "waktu": rerata.index, "lokasi": "hulu", "nilai": rerata.to_numpy(dtype=float), "satuan": "mm",
        "sumber": f"{hujan_gpm_imerg.SUMBER_PRODUK[produk]}_das", "is_simulated": False, "resolusi_jam": 24,
        "sel_grid": f"rerata {jumlah} sel DAS Tuntang",
    })
    return validasi_standar(pd.concat([sel, das], ignore_index=True))


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai nilai kosong atau di luar 0..hujan_harian_maks_mm."""
    return tandai_kualitas(df, 0.0, batas_kualitas()["hujan_harian_maks_mm"])


def jalankan(mulai: date, selesai: date, produk: str = "late", sesi_http: requests.Session | None = None,
             token: str | None = None) -> tuple[pd.DataFrame, list[dict]]:
    """Pipeline ambil -> ke_format_standar -> cek_kualitas. Kembali (tabel, mentah)."""
    mentah = ambil(mulai, selesai, produk, sesi_http=sesi_http, token=token)
    return cek_kualitas(ke_format_standar(mentah)), mentah
