"""
Tujuan      : Membaca katalog kejadian KANDIDAT gangguan banjir di koridor Brumbung-Karangjati yang
              dihimpun dari berita publik, memeriksa strukturnya, dan menurunkan jam acuan T-0 per
              kandidat untuk uji balik (backtest) model pada hujan nyata.
Lapis       : S (Sensing), bahan evaluasi lapis I dan G.
Sumber      : data/manual/kejadian_kandidat.csv (berita daring dan rilis BNPB/KAI yang dikutip media;
              tautan dicatat per baris). BUKAN data resmi KAI dan BUKAN pengganti E1-E6.
Masukan     : Berkas CSV katalog kandidat.
Keluaran    : DataFrame kandidat tervalidasi; tabel T-0 (id_kandidat, t0, jam_diketahui, ...);
              ringkasan publik tanpa tautan untuk API/dasbor.
Keterbatasan: Jam dari berita sering tidak ada atau berbeda antarsumber. Bila jam tidak dinyatakan,
              T-0 diambil pukul 00.00 hari kejadian agar model tidak memakai informasi hari itu
              (konservatif terhadap kebocoran informasi). Status semua baris "kandidat"; pemetaan ke
              E1-E6 dan verifikasi jam dilakukan tim (asumsi A-055).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from sigap_ka.inputs.base import GalatSkema, path_data

KOLOM = ["id_kandidat", "tanggal", "jam_acuan", "dasar_jam_acuan", "jam_tutup", "jam_buka", "petak",
         "lokasi_km", "jenis_gangguan", "mekanisme", "kutipan_mekanisme", "dampak_ka", "penyebab",
         "sumber_dibaca", "sumber_belum_dibaca", "kemungkinan_E", "status", "catatan"]
JENIS_GANGGUAN = ("tutup_dua_jalur", "satu_jalur_bergantian", "berhenti_sementara", "terlambat")
MEKANISME = ("genangan", "gerusan", "tidak_jelas")
PEMISAH_URL = " | "


def baca(path: Path | None = None) -> pd.DataFrame:
    """Membaca dan memvalidasi katalog kandidat.

    Aturan: semua kolom ada; id unik; tanggal terbaca; jam_acuan kosong atau HH:MM; jenis_gangguan
    dan mekanisme dari daftar baku; tiap baris punya minimal satu sumber yang dibaca; status
    diawali "kandidat".
    Galat:
        GalatSkema bila aturan dilanggar.
    """
    df = pd.read_csv(path or path_data("manual", "kejadian_kandidat.csv"), dtype=str, keep_default_na=False)
    hilang = [k for k in KOLOM if k not in df.columns]
    if hilang:
        raise GalatSkema(f"kolom kandidat hilang: {hilang}")
    if df["id_kandidat"].duplicated().any():
        raise GalatSkema("id_kandidat ganda")
    tgl = pd.to_datetime(df["tanggal"], format="%Y-%m-%d", errors="coerce")
    if tgl.isna().any():
        raise GalatSkema(f"tanggal tidak terbaca: {df.loc[tgl.isna(), 'id_kandidat'].tolist()}")
    jam_salah = df["jam_acuan"].ne("") & ~df["jam_acuan"].str.fullmatch(r"([01]\d|2[0-3]):[0-5]\d")
    if jam_salah.any():
        raise GalatSkema(f"jam_acuan bukan HH:MM: {df.loc[jam_salah, 'id_kandidat'].tolist()}")
    for kolom, baku in (("jenis_gangguan", JENIS_GANGGUAN), ("mekanisme", MEKANISME)):
        salah = set(df[kolom]) - set(baku)
        if salah:
            raise GalatSkema(f"{kolom} tidak dikenal: {sorted(salah)}")
    if (df["sumber_dibaca"].str.strip() == "").any():
        raise GalatSkema("setiap kandidat wajib punya minimal satu sumber yang dibaca")
    if not df["status"].str.startswith("kandidat").all():
        raise GalatSkema("status katalog ini harus diawali 'kandidat'")
    df["tanggal"] = tgl
    return df


def t0(baris: pd.Series) -> tuple[datetime, bool]:
    """Jam acuan T-0 satu kandidat dan apakah jamnya dinyatakan sumber.

    Kembali:
        (t0, jam_diketahui). Tanpa jam -> pukul 00.00 hari kejadian, jam_diketahui False.
    """
    tanggal = pd.Timestamp(baris["tanggal"]).normalize()
    if baris["jam_acuan"]:
        jam, menit = (int(x) for x in baris["jam_acuan"].split(":"))
        return (tanggal + pd.Timedelta(hours=jam, minutes=menit)).to_pydatetime(), True
    return tanggal.to_pydatetime(), False


def tabel_t0(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Tabel T-0 per kandidat untuk uji balik.

    Kembali:
        DataFrame id_kandidat, t0, jam_diketahui, jenis_gangguan, mekanisme, tutup (True bila kedua
        jalur ditutup), petak, lokasi_km.
    """
    df = baca() if df is None else df
    baris = []
    for _, r in df.iterrows():
        waktu, diketahui = t0(r)
        baris.append({"id_kandidat": r["id_kandidat"], "t0": waktu, "jam_diketahui": diketahui,
                      "jenis_gangguan": r["jenis_gangguan"], "mekanisme": r["mekanisme"],
                      "tutup": r["jenis_gangguan"] == "tutup_dua_jalur", "petak": r["petak"],
                      "lokasi_km": r["lokasi_km"]})
    return pd.DataFrame(baris)


def domain_sumber(teks: str) -> list[str]:
    """Nama domain dari daftar URL berpemisah ' | ' (tanpa 'www.'), urut kemunculan, tanpa duplikat."""
    hasil = []
    for url in (u.strip() for u in (teks or "").split("|")):
        if not url:
            continue
        dom = urlparse(url).netloc.lower().removeprefix("www.")
        if dom and dom not in hasil:
            hasil.append(dom)
    return hasil


def ringkasan_publik(df: pd.DataFrame | None = None) -> list[dict]:
    """Ringkasan kandidat untuk API/dasbor: tanpa tautan lengkap (hanya domain sumber).

    Tautan lengkap tetap di berkas CSV; judul berita bisa memuat kata yang dilarang penjaga klaim,
    jadi tidak diteruskan ke keluaran sistem.
    """
    df = baca() if df is None else df
    keluar = []
    for _, r in df.iterrows():
        waktu, diketahui = t0(r)
        keluar.append({
            "id_kandidat": r["id_kandidat"], "t0": waktu.isoformat(timespec="minutes"),
            "jam_diketahui": diketahui, "petak": r["petak"], "lokasi_km": r["lokasi_km"],
            "jenis_gangguan": r["jenis_gangguan"], "mekanisme": r["mekanisme"],
            "sumber": domain_sumber(r["sumber_dibaca"]), "status": r["status"],
        })
    return keluar
