"""
Tujuan      : Mengambil hujan harian NASA POWER untuk titik lokal (Gubug-Karangjati), hulu
              Tuntang, dan Gundih; dipakai untuk riwayat episode 2024-2026 dan akumulasi anteseden.
Lapis       : S (Sensing), data inti.
Sumber      : NASA POWER Daily API (https://power.larc.nasa.gov/api/temporal/daily/point),
              parameter PRECTOTCORR (presipitasi terkoreksi, mm/hari). Tanpa akun.
Masukan     : Kunci lokasi di params.json (lokal/hulu/gundih), tanggal mulai dan selesai.
Keluaran    : Tabel standar (waktu = awal hari WIB, resolusi_jam = 24, is_simulated = False).
Keterbatasan: Grid kasar (sekitar 0,5 x 0,625 derajat) sehingga lokal dan hulu bisa jatuh di sel
              yang berdekatan; latensi beberapa hari (asumsi A-015). Tanggal harian POWER
              diperlakukan sebagai tanggal WIB (asumsi A-017).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import requests

from config import muat_params
from sensing.standar import (
    SumberTidakTersedia,
    batas_kualitas,
    tabel_kosong,
    tandai_kualitas,
    validasi_standar,
)

NAMA_SUMBER = "nasa_power"
PARAMETER = "PRECTOTCORR"
NILAI_KOSONG = -999.0  # penanda data hilang NASA POWER


def ambil(lokasi: str, mulai: date, selesai: date, sesi_http: requests.Session | None = None,
          batas_waktu_detik: int = 60) -> dict:
    """Mengunduh JSON NASA POWER harian untuk satu titik.

    Parameter:
        lokasi: kunci lokasi di params.json ('lokal', 'hulu', 'gundih').
        mulai, selesai: rentang tanggal (inklusif).
        sesi_http: sesi requests opsional (untuk tes/mock).
    Kembali:
        dict JSON respons asli ditambah kunci '_permintaan' (url dan parameter).
    Galat:
        SumberTidakTersedia bila jaringan gagal atau respons tidak valid.
    """
    titik = muat_params().lokasi[lokasi]
    url = muat_params().sumber_data[NAMA_SUMBER]["url"]
    param = {
        "parameters": PARAMETER,
        "community": "AG",
        "longitude": titik["lon"],
        "latitude": titik["lat"],
        "start": mulai.strftime("%Y%m%d"),
        "end": selesai.strftime("%Y%m%d"),
        "format": "JSON",
    }
    http = sesi_http or requests
    try:
        resp = http.get(url, params=param, timeout=batas_waktu_detik)
        resp.raise_for_status()
        isi = resp.json()
    except (requests.RequestException, ValueError) as galat:
        raise SumberTidakTersedia(f"NASA POWER gagal diambil: {galat}") from galat
    isi["_permintaan"] = {"url": url, "parameter": param, "lokasi": lokasi}
    return isi


def ke_format_standar(mentah: dict, lokasi: str | None = None) -> pd.DataFrame:
    """Mengubah JSON NASA POWER menjadi tabel standar.

    Parameter:
        mentah: keluaran ambil().
        lokasi: kunci lokasi; bila kosong diambil dari mentah['_permintaan'].
    Kembali:
        DataFrame kolom standar + resolusi_jam. Nilai -999 menjadi NaN.
    """
    lokasi = lokasi or mentah.get("_permintaan", {}).get("lokasi")
    try:
        seri = mentah["properties"]["parameter"][PARAMETER]
    except KeyError as galat:
        raise ValueError("struktur JSON NASA POWER tidak dikenal") from galat
    if not seri:
        return tabel_kosong().assign(resolusi_jam=pd.Series(dtype=int))
    tanggal = pd.to_datetime(list(seri.keys()), format="%Y%m%d")
    nilai = np.array(list(seri.values()), dtype=float)
    nilai[nilai <= NILAI_KOSONG + 1e-9] = np.nan  # -999 = data hilang
    df = pd.DataFrame({
        "waktu": tanggal,
        "lokasi": lokasi,
        "nilai": nilai,
        "satuan": "mm",
        "sumber": NAMA_SUMBER,
        "is_simulated": False,
        "resolusi_jam": 24,
    })
    return validasi_standar(df)


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai nilai kosong atau di luar 0..hujan_harian_maks_mm sebagai kosong/janggal."""
    return tandai_kualitas(df, 0.0, batas_kualitas()["hujan_harian_maks_mm"])


def jalankan(lokasi: str, mulai: date, selesai: date,
             sesi_http: requests.Session | None = None) -> tuple[pd.DataFrame, dict]:
    """Pipeline ambil -> ke_format_standar -> cek_kualitas untuk satu titik.

    Kembali:
        (tabel standar berkualitas, dict mentah).
    """
    mentah = ambil(lokasi, mulai, selesai, sesi_http=sesi_http)
    return cek_kualitas(ke_format_standar(mentah, lokasi)), mentah


def tautan(mentah: dict) -> str:
    """URL lengkap permintaan untuk dicatat di log_pengambilan."""
    p = mentah.get("_permintaan", {})
    q = "&".join(f"{k}={v}" for k, v in p.get("parameter", {}).items())
    return f"{p.get('url')}?{q}"
