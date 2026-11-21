"""
Tujuan      : Mengambil hujan satelit GPM IMERG (NASA/JAXA) untuk hujan hulu Tuntang.
Lapis       : S (Sensing), data inti (butuh akun Earthdata gratis).
Sumber      : NASA GES DISC OPeNDAP, produk harian IMERG Late (GPM_3IMERGDL, V07), subset satu
              sel grid 0,1 derajat dalam format ASCII. Autentikasi: token Earthdata di
              EARTHDATA_TOKEN (.env), dikirim sebagai header Authorization Bearer.
Masukan     : Kunci lokasi, rentang tanggal.
Keluaran    : Tabel standar (resolusi_jam = 24, satuan mm, is_simulated = False).
Keterbatasan: Pola nama berkas dan format ASCII OPeNDAP diuji dengan fixture, belum terhadap
              layanan asli karena kredensial belum tersedia (keterbatasan tercatat). Tanpa
              token, modul memberi SumberTidakTersedia dan registri beralih ke cadangan.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests

from config import muat_params, muat_pengaturan
from sensing.standar import SumberTidakTersedia, batas_kualitas, tandai_kualitas, validasi_standar

NAMA_SUMBER = "gpm_imerg"
NILAI_KOSONG = -9999.9
RESOLUSI_DERAJAT = 0.1


def indeks_grid(lat: float, lon: float) -> tuple[int, int]:
    """Indeks sel grid IMERG 0,1 derajat (lon -179,95..179,95; lat -89,95..89,95).

    Kembali:
        (indeks_lon, indeks_lat).
    """
    i_lon = int(round((lon + 179.95) / RESOLUSI_DERAJAT))
    i_lat = int(round((lat + 89.95) / RESOLUSI_DERAJAT))
    return i_lon, i_lat


def url_harian(tanggal: date, lat: float, lon: float) -> str:
    """URL OPeNDAP ASCII untuk satu hari dan satu sel grid."""
    dasar = muat_params().sumber_data[NAMA_SUMBER]["url"]
    i_lon, i_lat = indeks_grid(lat, lon)
    nama = f"3B-DAY-L.MS.MRG.3IMERG.{tanggal:%Y%m%d}-S000000-E235959.V07B.nc4"
    return (f"{dasar}/{tanggal:%Y}/{tanggal:%m}/{nama}.ascii"
            f"?precipitation[0:0][{i_lon}:{i_lon}][{i_lat}:{i_lat}]")


def ambil(lokasi: str, mulai: date, selesai: date, sesi_http: requests.Session | None = None,
          token: str | None = None) -> list[dict]:
    """Mengunduh nilai harian IMERG untuk satu titik.

    Parameter:
        lokasi: kunci lokasi di params.json.
        mulai, selesai: rentang tanggal (inklusif).
        token: token Earthdata; bawaan dari EARTHDATA_TOKEN.
    Kembali:
        Daftar dict {'tanggal', 'url', 'teks'} per hari.
    Galat:
        SumberTidakTersedia bila token kosong atau permintaan gagal.
    """
    token = token if token is not None else muat_pengaturan().earthdata_token
    if not token:
        raise SumberTidakTersedia("GPM IMERG butuh EARTHDATA_TOKEN di .env (akun Earthdata gratis)")
    titik = muat_params().lokasi[lokasi]
    http = sesi_http or requests
    hasil = []
    hari = mulai
    while hari <= selesai:
        url = url_harian(hari, titik["lat"], titik["lon"])
        try:
            resp = http.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        except requests.RequestException as galat:
            raise SumberTidakTersedia(f"GPM IMERG gagal diambil ({hari}): {galat}") from galat
        if resp.status_code in (401, 403):
            raise SumberTidakTersedia(pesan_otorisasi(resp))
        if not resp.ok:
            raise SumberTidakTersedia(f"GPM IMERG gagal diambil ({hari}): HTTP {resp.status_code}")
        hasil.append({"tanggal": hari, "url": url, "teks": resp.text, "lokasi": lokasi})
        hari += timedelta(days=1)
    return hasil


def pesan_otorisasi(resp: requests.Response) -> str:
    """Pesan galat yang dapat ditindaklanjuti untuk respons 401/403 GES DISC.

    GES DISC menolak token yang valid bila pemilik akun belum menyetujui aplikasi
    "NASA GESDISC DATA ARCHIVE" (EULA); responsnya memuat resolution_url untuk persetujuan itu.
    """
    try:
        isi = resp.json()
    except ValueError:
        isi = {}
    if "EULA" in str(isi.get("error_description", "")) or resp.status_code == 401:
        tautan = isi.get("resolution_url") or "https://urs.earthdata.nasa.gov/profile (Applications > Authorized Apps)"
        return ("GPM IMERG ditolak (HTTP %d): akun Earthdata belum menyetujui aplikasi NASA GESDISC DATA "
                "ARCHIVE. Buka %s, login, lalu setujui." % (resp.status_code, tautan))
    return f"GPM IMERG ditolak (HTTP {resp.status_code}): periksa EARTHDATA_TOKEN"


def urai_ascii(teks: str) -> float:
    """Mengambil nilai presipitasi dari respons ASCII OPeNDAP satu sel.

    Format yang ditangani: baris data berbentuk '[0][0], 12.5' atau
    'precipitation.precipitation[0][0], 12.5' setelah header variabel.
    Kembali:
        Nilai mm/hari; NaN bila kosong atau bernilai pengisi.
    """
    cocok = re.findall(r"\]\s*,\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*$", teks, flags=re.M)
    if not cocok:
        return float("nan")
    nilai = float(cocok[-1])
    return float("nan") if nilai <= NILAI_KOSONG + 1e-6 else nilai


def ke_format_standar(mentah: list[dict]) -> pd.DataFrame:
    """Mengubah daftar respons harian menjadi tabel standar."""
    df = pd.DataFrame({
        "waktu": pd.to_datetime([m["tanggal"] for m in mentah]),
        "lokasi": [m["lokasi"] for m in mentah],
        "nilai": np.array([urai_ascii(m["teks"]) for m in mentah], dtype=float),
        "satuan": "mm",
        "sumber": NAMA_SUMBER,
        "is_simulated": False,
        "resolusi_jam": 24,
    })
    return validasi_standar(df)


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai nilai kosong atau di luar 0..hujan_harian_maks_mm."""
    return tandai_kualitas(df, 0.0, batas_kualitas()["hujan_harian_maks_mm"])


def jalankan(lokasi: str, mulai: date, selesai: date, **kw) -> tuple[pd.DataFrame, list[dict]]:
    """Pipeline ambil -> ke_format_standar -> cek_kualitas."""
    mentah = ambil(lokasi, mulai, selesai, **kw)
    return cek_kualitas(ke_format_standar(mentah)), mentah
