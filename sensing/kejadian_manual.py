"""
Tujuan      : Membaca katalog kejadian gangguan (E1-E6 dst.) yang diisi manual dari berita,
              pengumuman KAI121/Daop 4, dan rilis BNPB/BPBD.
Lapis       : S (Sensing), data inti (KEJADIAN_METODE=manual).
Sumber      : data/manual/kejadian.csv, kolom: id, tanggal, jam_tutup, jam_buka, lokasi_km,
              mekanisme, ka_terdampak, sumber, status_konfirmasi, catatan.
Masukan     : Berkas CSV manual.
Keluaran    : Tabel standar (waktu = jam tutup atau tanggal, lokasi = KM, nilai = lama tutup jam,
              satuan 'jam', sumber, is_simulated = False) ditambah kolom katalog spesifikasi 8.3.
Keterbatasan: Katalog di repo baru berisi kerangka E1-E6 dengan fakta dari dokumen; kolom yang
              belum diketahui dibiarkan kosong berstatus 'belum terkonfirmasi' (tidak ditebak).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sensing.standar import DIR_MANUAL, SumberTidakTersedia, validasi_standar

NAMA_SUMBER = "kejadian_manual"
BERKAS = "kejadian.csv"
KOLOM_KATALOG = ["id", "tanggal", "jam_tutup", "jam_buka", "lokasi_km", "mekanisme",
                 "ka_terdampak", "status_konfirmasi", "catatan"]
MEKANISME_VALID = {"genangan", "gerusan"}


def ambil(path: Path | None = None) -> pd.DataFrame:
    """Membaca CSV katalog manual. Galat SumberTidakTersedia bila berkas belum ada."""
    path = path or DIR_MANUAL / BERKAS
    if not path.exists():
        raise SumberTidakTersedia(f"berkas katalog {path.name} belum ada")
    return pd.read_csv(path, encoding="utf-8", dtype=str).replace({np.nan: None})


def ke_format_standar(mentah: pd.DataFrame, metode: str = "manual",
                      sumber: str = NAMA_SUMBER) -> pd.DataFrame:
    """Mengubah katalog menjadi tabel standar + kolom katalog.

    Parameter:
        mentah: katalog mentah (kolom KOLOM_KATALOG + sumber).
        metode: 'manual' atau 'ocr_llm' (dicatat di kolom metode).
    Kembali:
        DataFrame; nilai = lama tutup (jam) bila jam tutup dan buka diketahui, selain itu NaN.
    """
    tutup = pd.to_datetime(mentah["jam_tutup"], errors="coerce")
    buka = pd.to_datetime(mentah["jam_buka"], errors="coerce")
    tanggal = pd.to_datetime(mentah["tanggal"], errors="coerce")
    lama = (buka - tutup).dt.total_seconds() / 3600.0
    mek = mentah["mekanisme"].map(lambda m: m.strip().lower() if isinstance(m, str) else None)
    df = pd.DataFrame({
        "waktu": tutup.fillna(tanggal),
        "lokasi": mentah["lokasi_km"].fillna("koridor Brumbung-Karangjati"),
        "nilai": lama.astype(float),
        "satuan": "jam",
        "sumber": sumber,
        "is_simulated": False,
        "id": mentah["id"],
        "tanggal": tanggal.dt.date,
        "jam_tutup": tutup,
        "jam_buka": buka,
        "lokasi_km": mentah["lokasi_km"],
        "mekanisme": mek,
        "ka_terdampak": mentah["ka_terdampak"],
        "tautan_sumber": mentah.get("sumber"),
        "metode": metode,
        "status_konfirmasi": mentah["status_konfirmasi"].fillna("belum terkonfirmasi"),
        "catatan": mentah["catatan"],
    })
    df["waktu"] = pd.to_datetime(df["waktu"])
    return validasi_standar(df)


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Menandai baris katalog: 'kosong' (jam tutup/buka/mekanisme belum ada), 'janggal'
    (buka sebelum tutup atau mekanisme tidak dikenal), 'baik'."""
    d = df.copy()
    kualitas = []
    for _, r in d.iterrows():
        if pd.isna(r["jam_tutup"]) or pd.isna(r["jam_buka"]) or not r["mekanisme"]:
            kualitas.append("kosong")
        elif r["nilai"] < 0 or r["mekanisme"] not in MEKANISME_VALID:
            kualitas.append("janggal")
        else:
            kualitas.append("baik")
    d["kualitas"] = kualitas
    return d


def ke_baris_db(df: pd.DataFrame) -> pd.DataFrame:
    """Memetakan tabel katalog ke kolom tabel kejadian di database."""
    return pd.DataFrame({
        "id": df["id"], "tanggal": df["tanggal"], "jam_tutup": df["jam_tutup"],
        "jam_buka": df["jam_buka"], "lokasi_km": df["lokasi_km"], "mekanisme": df["mekanisme"],
        "ka_terdampak": df["ka_terdampak"], "sumber": df["tautan_sumber"],
        "metode": df["metode"], "status_konfirmasi": df["status_konfirmasi"],
        "kode_periksa": df.get("kode_periksa"), "is_simulated": df["is_simulated"],
        "catatan": df["catatan"],
    })


def jalankan(path: Path | None = None) -> pd.DataFrame:
    """Pipeline ambil -> ke_format_standar -> cek_kualitas."""
    return cek_kualitas(ke_format_standar(ambil(path)))
