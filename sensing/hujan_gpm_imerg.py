"""
Tujuan      : Mengambil hujan satelit harian GPM IMERG (NASA/JAXA) untuk titik lokal, hulu Tuntang,
              dan Gundih; grid 0,1 derajat sehingga hujan hulu terpisah dari hujan lokal.
Lapis       : S (Sensing), data inti (butuh akun Earthdata gratis + persetujuan aplikasi GES DISC).
Sumber      : Jalur utama: Giovanni Time Series API (satu permintaan per titik untuk seluruh rentang).
              Cadangan: GES DISC OPeNDAP per hari (produk Late). Produk:
              - Late (GPM_3IMERGDL.07): tersedia sekitar 14 jam setelah hari berakhir; dipakai untuk
                memutar ulang episode karena itulah yang tersedia bagi operator pada jam keputusan.
              - Final (GPM_3IMERGDF.07): terkalibrasi penakar, terbit sekitar 3,5 bulan kemudian;
                dipakai untuk analisis riwayat (spesifikasi 8.1), bukan untuk jam keputusan.
              Autentikasi: EARTHDATA_TOKEN (.env) sebagai header Authorization Bearer.
Masukan     : Kunci lokasi, rentang tanggal, produk ('late' atau 'final').
Keluaran    : Tabel standar (waktu = awal hari UTC = 07.00 WIB, resolusi_jam = 24, satuan mm,
              sumber 'gpm_imerg_late' atau 'gpm_imerg_final', is_simulated = False).
Keterbatasan: Resolusi harian (hujan dibagi rata per jam saat dipakai model per jam). Nilai satu sel
              grid, bukan rerata daerah tangkapan Tuntang (A-048).
"""

from __future__ import annotations

import io
import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests

from config import muat_params, muat_pengaturan
from sensing.standar import SumberTidakTersedia, batas_kualitas, tandai_kualitas, validasi_standar

NAMA_SUMBER = "gpm_imerg"
SUMBER_PRODUK = {"late": "gpm_imerg_late", "final": "gpm_imerg_final"}
NILAI_KOSONG = -9999.9
RESOLUSI_DERAJAT = 0.1
SELISIH_WIB = pd.Timedelta(hours=7)  # hari IMERG dihitung dalam UTC


def _token(token: str | None) -> str:
    """Token Earthdata dari argumen atau .env; galat bila kosong."""
    token = token if token is not None else muat_pengaturan().earthdata_token
    if not token:
        raise SumberTidakTersedia("GPM IMERG butuh EARTHDATA_TOKEN di .env (akun Earthdata gratis)")
    return token


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


# ---------------------------------------------------------------- jalur utama: Giovanni

def ambil_deret(lokasi: str, mulai: date, selesai: date, produk: str = "late",
                sesi_http: requests.Session | None = None, token: str | None = None) -> dict:
    """Mengunduh deret harian IMERG satu titik lewat Giovanni Time Series API (satu permintaan).

    Parameter:
        lokasi: kunci lokasi di params.json.
        mulai, selesai: rentang tanggal (inklusif, hari UTC).
        produk: 'late' atau 'final'.
    Kembali:
        dict {'lokasi', 'produk', 'url', 'teks'} (teks CSV Giovanni).
    Galat:
        SumberTidakTersedia bila token kosong, akun belum disetujui, atau permintaan gagal.
    """
    token = _token(token)
    konf = muat_params().sumber_data[NAMA_SUMBER]
    titik = muat_params().lokasi[lokasi]
    url = (f"{konf['url_giovanni']}?data={konf['giovanni_data'][produk]}"
           f"&location=[{titik['lat']},{titik['lon']}]"
           f"&time={mulai:%Y-%m-%d}T00:00:00/{selesai:%Y-%m-%d}T23:59:59")
    http = sesi_http or requests
    try:
        resp = http.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=300)
    except requests.RequestException as galat:
        raise SumberTidakTersedia(f"Giovanni IMERG gagal diambil: {galat}") from galat
    if resp.status_code in (401, 403):
        raise SumberTidakTersedia(pesan_otorisasi(resp))
    if not resp.ok or "Timestamp" not in resp.text:
        raise SumberTidakTersedia(f"Giovanni IMERG gagal (HTTP {resp.status_code}): {resp.text[:120]}")
    return {"lokasi": lokasi, "produk": produk, "url": url, "teks": resp.text}


def urai_giovanni(teks: str) -> tuple[dict, pd.DataFrame]:
    """Mengurai CSV Giovanni: metadata 'kunci,nilai' lalu tabel 'Timestamp (UTC),Data'.

    Kembali:
        (metadata, DataFrame kolom tanggal_utc, nilai) dengan nilai pengisi menjadi NaN.
    """
    meta, baris = {}, teks.splitlines()
    for i, b in enumerate(baris):
        if b.startswith("Timestamp"):
            tabel = pd.read_csv(io.StringIO("\n".join(baris[i:])))
            tabel.columns = ["tanggal_utc", "nilai"]
            tabel["tanggal_utc"] = pd.to_datetime(tabel["tanggal_utc"])
            undef = float(meta.get("undef", NILAI_KOSONG))
            nilai = pd.to_numeric(tabel["nilai"], errors="coerce")
            tabel["nilai"] = nilai.where(nilai > undef + 1e-6)
            return meta, tabel
        if "," in b:
            k, v = b.split(",", 1)
            meta[k.strip()] = v.strip()
    raise ValueError("format CSV Giovanni tidak dikenal (tidak ada baris Timestamp)")


def ke_format_standar_deret(mentah: dict) -> pd.DataFrame:
    """Deret Giovanni menjadi tabel standar (waktu = awal hari UTC dalam WIB)."""
    meta, tabel = urai_giovanni(mentah["teks"])
    df = pd.DataFrame({
        "waktu": tabel["tanggal_utc"] + SELISIH_WIB,
        "lokasi": mentah["lokasi"],
        "nilai": tabel["nilai"].astype(float),
        "satuan": "mm",
        "sumber": SUMBER_PRODUK[mentah["produk"]],
        "is_simulated": False,
        "resolusi_jam": 24,
        "sel_grid": f"{meta.get('lat', '?')}, {meta.get('lon', '?')}",
    })
    return validasi_standar(df)


# ---------------------------------------------------------------- cadangan: OPeNDAP per hari

def indeks_grid(lat: float, lon: float) -> tuple[int, int]:
    """Indeks sel grid IMERG 0,1 derajat (lon -179,95..179,95; lat -89,95..89,95).

    Kembali:
        (indeks_lon, indeks_lat).
    """
    i_lon = int(round((lon + 179.95) / RESOLUSI_DERAJAT))
    i_lat = int(round((lat + 89.95) / RESOLUSI_DERAJAT))
    return i_lon, i_lat


def url_harian(tanggal: date, lat: float, lon: float) -> str:
    """URL OPeNDAP ASCII produk Late untuk satu hari dan satu sel grid."""
    dasar = muat_params().sumber_data[NAMA_SUMBER]["url"]
    i_lon, i_lat = indeks_grid(lat, lon)
    nama = f"3B-DAY-L.MS.MRG.3IMERG.{tanggal:%Y%m%d}-S000000-E235959.V07B.nc4"
    return (f"{dasar}/{tanggal:%Y}/{tanggal:%m}/{nama}.ascii"
            f"?precipitation[0:0][{i_lon}:{i_lon}][{i_lat}:{i_lat}]")


def ambil(lokasi: str, mulai: date, selesai: date, sesi_http: requests.Session | None = None,
          token: str | None = None) -> list[dict]:
    """Mengunduh nilai harian IMERG Late per hari lewat OPeNDAP (jalur cadangan, lambat).

    Kembali:
        Daftar dict {'tanggal', 'url', 'teks', 'lokasi'} per hari.
    Galat:
        SumberTidakTersedia bila token kosong, akun belum disetujui, atau permintaan gagal.
    """
    token = _token(token)
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


def urai_ascii(teks: str) -> float:
    """Mengambil nilai presipitasi dari respons ASCII OPeNDAP satu sel.

    Format yang ditangani: baris data yang diakhiri '], <nilai>', misalnya
    'precipitation.precipitation[precipitation.time=16451][precipitation.lon=110.45], 53.48'.
    Kembali:
        Nilai mm/hari; NaN bila kosong atau bernilai pengisi.
    """
    cocok = re.findall(r"\]\s*,\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*$", teks, flags=re.M)
    if not cocok:
        return float("nan")
    nilai = float(cocok[-1])
    return float("nan") if nilai <= NILAI_KOSONG + 1e-6 else nilai


def ke_format_standar(mentah: list[dict]) -> pd.DataFrame:
    """Daftar respons OPeNDAP harian (produk Late) menjadi tabel standar."""
    df = pd.DataFrame({
        "waktu": pd.to_datetime([m["tanggal"] for m in mentah]) + SELISIH_WIB,
        "lokasi": [m["lokasi"] for m in mentah],
        "nilai": np.array([urai_ascii(m["teks"]) for m in mentah], dtype=float),
        "satuan": "mm",
        "sumber": SUMBER_PRODUK["late"],
        "is_simulated": False,
        "resolusi_jam": 24,
    })
    return validasi_standar(df)


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai nilai kosong atau di luar 0..hujan_harian_maks_mm."""
    return tandai_kualitas(df, 0.0, batas_kualitas()["hujan_harian_maks_mm"])


def jalankan(lokasi: str, mulai: date, selesai: date, produk: str = "late",
             sesi_http: requests.Session | None = None, token: str | None = None):
    """Pipeline: Giovanni (utama) -> bila gagal dan produk Late, OPeNDAP per hari -> cek_kualitas.

    Kembali:
        (tabel standar berkualitas, mentah).
    """
    try:
        mentah = ambil_deret(lokasi, mulai, selesai, produk, sesi_http=sesi_http, token=token)
        return cek_kualitas(ke_format_standar_deret(mentah)), mentah
    except SumberTidakTersedia as galat:
        if produk != "late" or "NASA GESDISC DATA ARCHIVE" in str(galat):
            raise
        mentah = ambil(lokasi, mulai, selesai, sesi_http=sesi_http, token=token)
        return cek_kualitas(ke_format_standar(mentah)), mentah
