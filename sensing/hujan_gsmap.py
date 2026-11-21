"""
Tujuan      : Mengambil hujan satelit hampir real-time GSMaP (JAXA) per jam; dipakai operasional
              dan sebagai cadangan bila IMERG terlambat.
Lapis       : S (Sensing), data inti (butuh akun JAXA gratis).
Sumber      : Server JAXA (hokusai.eorc.jaxa.jp, SFTP), berkas GSMaP NRT per jam
              gsmap_nrt.YYYYMMDD.HH00.dat.gz: grid float32 little-endian 3600 x 1200,
              0,1 derajat, lintang 59,95 LU s.d. 59,95 LS, bujur 0,05 s.d. 359,95 BT, mm/jam.
              Kredensial: JAXA_USER dan JAXA_PASSWORD di .env; butuh paket paramiko.
Masukan     : Kunci lokasi, rentang waktu per jam.
Keluaran    : Tabel standar (resolusi_jam = 1, satuan mm, is_simulated = False).
Keterbatasan: Jalur direktori server dan nama berkas belum diuji terhadap server asli; pengurai
              grid diuji dengan grid sintetis. Waktu berkas GSMaP dalam UTC dan diubah ke WIB (+7).
"""

from __future__ import annotations

import gzip
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from config import muat_params, muat_pengaturan
from sensing.standar import SumberTidakTersedia, batas_kualitas, tandai_kualitas, validasi_standar

NAMA_SUMBER = "gsmap"
NX, NY = 3600, 1200
SELISIH_WIB = timedelta(hours=7)


def indeks_grid(lat: float, lon: float) -> tuple[int, int]:
    """Indeks (baris, kolom) sel GSMaP untuk lintang/bujur (bujur negatif diubah ke 0-360)."""
    lon = lon % 360.0
    baris = int(round((59.95 - lat) / 0.1))
    kolom = int(round((lon - 0.05) / 0.1))
    if not (0 <= baris < NY and 0 <= kolom < NX):
        raise ValueError("titik di luar cakupan GSMaP (60 LU - 60 LS)")
    return baris, kolom


def urai_grid(isi_gz: bytes, lat: float, lon: float) -> float:
    """Mengambil nilai satu sel dari berkas GSMaP terkompresi gzip.

    Kembali:
        Hujan mm/jam; NaN untuk nilai negatif (penanda data hilang).
    """
    data = np.frombuffer(gzip.decompress(isi_gz), dtype="<f4")
    if data.size != NX * NY:
        raise ValueError(f"ukuran grid GSMaP tidak sesuai: {data.size}")
    baris, kolom = indeks_grid(lat, lon)
    nilai = float(data.reshape(NY, NX)[baris, kolom])
    return float("nan") if nilai < 0 else nilai


def jalur_berkas(waktu_utc: datetime) -> str:
    """Jalur berkas NRT per jam di server JAXA."""
    return (f"/realtime_ver/v8/hourly/{waktu_utc:%Y/%m/%d}/"
            f"gsmap_nrt.{waktu_utc:%Y%m%d.%H}00.dat.gz")


def ambil(lokasi: str, mulai_wib: datetime, selesai_wib: datetime, klien_sftp=None) -> list[dict]:
    """Mengunduh berkas GSMaP per jam lalu mengambil sel lokasi.

    Parameter:
        lokasi: kunci lokasi di params.json.
        mulai_wib, selesai_wib: rentang jam (WIB, inklusif).
        klien_sftp: objek dengan metode open(path) -> file (untuk tes); bila kosong dibuat dari kredensial.
    Kembali:
        Daftar dict {'waktu', 'lokasi', 'nilai', 'jalur'}.
    Galat:
        SumberTidakTersedia bila kredensial kosong, paramiko tidak ada, atau unduhan gagal.
    """
    peng = muat_pengaturan()
    titik = muat_params().lokasi[lokasi]
    if klien_sftp is None:
        if not (peng.jaxa_user and peng.jaxa_password):
            raise SumberTidakTersedia("GSMaP butuh JAXA_USER dan JAXA_PASSWORD di .env (akun JAXA gratis)")
        try:
            import paramiko  # noqa: F401
        except ImportError as galat:
            raise SumberTidakTersedia("GSMaP butuh paket paramiko (pip install paramiko)") from galat
        klien_sftp = _buka_sftp(peng.jaxa_user, peng.jaxa_password)
    hasil = []
    t = mulai_wib.replace(minute=0, second=0, microsecond=0)
    while t <= selesai_wib:
        jalur = jalur_berkas(t - SELISIH_WIB)
        try:
            with klien_sftp.open(jalur) as f:
                isi = f.read()
        except Exception as galat:  # jaringan/izin/berkas belum ada
            raise SumberTidakTersedia(f"GSMaP gagal diambil ({jalur}): {galat}") from galat
        hasil.append({"waktu": t, "lokasi": lokasi, "jalur": jalur,
                      "nilai": urai_grid(isi, titik["lat"], titik["lon"])})
        t += timedelta(hours=1)
    return hasil


def _buka_sftp(user: str, password: str):  # pragma: no cover - butuh server asli
    """Membuka koneksi SFTP ke server JAXA."""
    import paramiko
    transport = paramiko.Transport((muat_params().sumber_data[NAMA_SUMBER]["url"], 2051))
    transport.connect(username=user, password=password)
    return paramiko.SFTPClient.from_transport(transport)


def ke_format_standar(mentah: list[dict]) -> pd.DataFrame:
    """Mengubah daftar nilai per jam menjadi tabel standar."""
    df = pd.DataFrame({
        "waktu": pd.to_datetime([m["waktu"] for m in mentah]),
        "lokasi": [m["lokasi"] for m in mentah],
        "nilai": np.array([m["nilai"] for m in mentah], dtype=float),
        "satuan": "mm",
        "sumber": NAMA_SUMBER,
        "is_simulated": False,
        "resolusi_jam": 1,
    })
    return validasi_standar(df)


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai nilai kosong atau di luar 0..hujan_jam_maks_mm."""
    return tandai_kualitas(df, 0.0, batas_kualitas()["hujan_jam_maks_mm"])


def jalankan(lokasi: str, mulai_wib: datetime, selesai_wib: datetime, **kw):
    """Pipeline ambil -> ke_format_standar -> cek_kualitas."""
    mentah = ambil(lokasi, mulai_wib, selesai_wib, **kw)
    return cek_kualitas(ke_format_standar(mentah)), mentah
