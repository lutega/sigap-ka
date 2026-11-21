"""
Tujuan      : Mengambil prakiraan hujan dan peringatan dini cuaca BMKG untuk koridor; masukan
              utama keputusan pada jam keputusan.
Lapis       : S (Sensing), data inti.
Sumber      : API data terbuka BMKG (https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=...),
              prakiraan per 3 jam dengan kolom tp (hujan, mm), local_datetime (WIB), dan
              analysis_date (waktu analisis model, UTC). Peringatan dini dari umpan RSS
              nowcast BMKG (URL di params.json).
Masukan     : Kode wilayah adm4 (params.json), opsional kata kunci wilayah peringatan.
Keluaran    : Tabel standar prakiraan: waktu_terbit, waktu (awal periode valid), lokasi, nilai,
              satuan, sumber, is_simulated = False, resolusi_jam = 3.
Keterbatasan: Kode adm4 adalah perkiraan (A-008). tp diasumsikan akumulasi 3 jam yang berakhir
              pada local_datetime (A-018). API hanya memberi prakiraan terkini; arsip prakiraan
              lama tidak tersedia sehingga episode riwayat memakai prakiraan sintetis berlabel.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import timedelta

import pandas as pd
import requests

from config import muat_params
from sensing.standar import SumberTidakTersedia, batas_kualitas, tandai_kualitas, validasi_standar

NAMA_SUMBER = "bmkg_prakiraan"
SELISIH_WIB = timedelta(hours=7)
PERIODE_JAM = 3


def ambil(adm4: str | None = None, sesi_http: requests.Session | None = None) -> dict:
    """Mengunduh prakiraan BMKG untuk satu kode wilayah adm4.

    Parameter:
        adm4: kode wilayah desa; bawaan dari params.json.
    Kembali:
        dict JSON respons asli + kunci '_permintaan'.
    Galat:
        SumberTidakTersedia bila jaringan gagal atau respons tidak valid.
    """
    konf = muat_params().sumber_data[NAMA_SUMBER]
    adm4 = adm4 or konf["adm4_lokal"]
    http = sesi_http or requests
    try:
        resp = http.get(konf["url"], params={"adm4": adm4}, timeout=30)
        resp.raise_for_status()
        isi = resp.json()
    except (requests.RequestException, ValueError) as galat:
        raise SumberTidakTersedia(f"Prakiraan BMKG gagal diambil (adm4={adm4}): {galat}") from galat
    isi["_permintaan"] = {"url": konf["url"], "adm4": adm4}
    return isi


def ke_format_standar(mentah: dict, lokasi: str = "lokal") -> pd.DataFrame:
    """Mengubah JSON BMKG menjadi tabel standar prakiraan.

    Parameter:
        mentah: keluaran ambil().
        lokasi: kunci lokasi SIGAP yang diwakili kode adm4 ini.
    Kembali:
        DataFrame berkolom standar prakiraan. Periode yang sudah dimulai sebelum waktu terbit dibuang.
    """
    baris = []
    for blok in mentah.get("data", []):
        for hari in blok.get("cuaca", []):
            for c in hari:
                if "local_datetime" not in c or "analysis_date" not in c:
                    continue
                akhir = pd.to_datetime(c["local_datetime"])
                terbit = pd.to_datetime(c["analysis_date"]).tz_localize(None) + SELISIH_WIB
                baris.append({
                    "waktu_terbit": terbit,
                    "waktu": akhir - timedelta(hours=PERIODE_JAM),  # awal periode 3 jam
                    "lokasi": lokasi,
                    "nilai": float(c.get("tp", float("nan"))),
                    "satuan": "mm",
                    "sumber": NAMA_SUMBER,
                    "is_simulated": False,
                    "resolusi_jam": PERIODE_JAM,
                })
    df = pd.DataFrame(baris, columns=["waktu_terbit", "waktu", "lokasi", "nilai", "satuan",
                                      "sumber", "is_simulated", "resolusi_jam"])
    if not df.empty:
        df = df[df["waktu"] >= df["waktu_terbit"]].sort_values("waktu").reset_index(drop=True)
        df["waktu_terbit"] = pd.to_datetime(df["waktu_terbit"])
        df["waktu"] = pd.to_datetime(df["waktu"])
    return validasi_standar(df, prakiraan=True)


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai prakiraan kosong atau di luar 0..hujan_jam_maks_mm x 3."""
    return tandai_kualitas(df, 0.0, batas_kualitas()["hujan_jam_maks_mm"] * PERIODE_JAM)


def jalankan(adm4: str | None = None, lokasi: str = "lokal", **kw):
    """Pipeline ambil -> ke_format_standar -> cek_kualitas."""
    mentah = ambil(adm4, **kw)
    return cek_kualitas(ke_format_standar(mentah, lokasi)), mentah


def ambil_peringatan(kata_kunci: tuple[str, ...] = ("Grobogan", "Semarang", "Demak"),
                     sesi_http: requests.Session | None = None, teks_rss: str | None = None) -> list[dict]:
    """Mengambil peringatan dini cuaca (nowcast) BMKG yang menyebut wilayah koridor.

    Parameter:
        kata_kunci: nama wilayah yang dicari pada judul/deskripsi.
        teks_rss: isi RSS (untuk tes); bila kosong diunduh dari URL di params.json.
    Kembali:
        Daftar dict {judul, tautan, terbit, deskripsi}.
    Galat:
        SumberTidakTersedia bila unduhan gagal.
    """
    if teks_rss is None:
        url = muat_params().sumber_data[NAMA_SUMBER]["url_peringatan"]
        http = sesi_http or requests
        try:
            resp = http.get(url, timeout=30)
            resp.raise_for_status()
            teks_rss = resp.text
        except requests.RequestException as galat:
            raise SumberTidakTersedia(f"Peringatan dini BMKG gagal diambil: {galat}") from galat
    akar = ET.fromstring(teks_rss)
    hasil = []
    for item in akar.iter("item"):
        judul = item.findtext("title", default="")
        desk = item.findtext("description", default="")
        if any(k.lower() in (judul + " " + desk).lower() for k in kata_kunci):
            hasil.append({"judul": judul, "tautan": item.findtext("link", default=""),
                          "terbit": item.findtext("pubDate", default=""), "deskripsi": desk})
    return hasil
