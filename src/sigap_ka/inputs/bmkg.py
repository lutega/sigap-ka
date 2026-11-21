"""
Tujuan      : Membaca curah hujan harian stasiun BMKG dari berkas .csv/.xlsx, membersihkan kode
              anomali, memetakan stasiun ke zona SIGAP-KA, dan menyimpan tabel bersih.
Lapis       : S (Sensing), data tambahan (portal/permintaan data BMKG).
Sumber      : Berkas unduhan/salinan portal data BMKG di data/raw/bmkg/ (tidak di-commit). Pemetaan
              stasiun -> zona di config/stasiun_bmkg.json (dirujuk params.json). Kode BMKG:
              8888 = tidak terukur, 9999 = tidak ada data.
Masukan     : Folder berkas mentah; tiap berkas satu stasiun (nama stasiun dari baris metadata
              "Nama Stasiun" atau dari nama berkas), tabel berkolom Tanggal dan curah hujan (RR).
Keluaran    : data/interim/bmkg_clean.csv berskema base.KOLOM_WAJIB + stasiun, catatan_qc;
              sumber = "bmkg", status_data = "nyata".
Keterbatasan: Format persis berkas portal BMKG belum diverifikasi dengan berkas asli; pembaca
              mencari baris judul secara toleran. Stasiun yang tidak ada di pemetaan dilewati dan
              dilaporkan (zonanya tidak ditebak). Stasiun Kota Semarang dipetakan ke zona
              'semarang_pembanding' (bukan zona lokal/hulu/Gundih) karena jaraknya 25-30 km.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from config import AKAR_REPO, muat_params
from sigap_ka.inputs.base import path_data, simpan_csv, tabel_kosong, validasi

SUMBER = "bmkg"
EKSTENSI = (".csv", ".xlsx", ".xls")
NAMA_KOLOM_HUJAN = ("rr", "curahhujan", "curahhujanmm", "ch", "hujan", "rainfall", "precipitation", "presipitasi")
NAMA_KOLOM_TANGGAL = ("tanggal", "tgl", "date", "waktu")


def _norm(teks) -> str:
    """Teks dinormalisasi: huruf kecil, hanya huruf dan angka."""
    return re.sub(r"[^a-z0-9]", "", str(teks).lower())


def konfigurasi() -> dict:
    """Konfigurasi BMKG dari params.json (folder mentah, berkas pemetaan, kode anomali)."""
    return muat_params().sumber_data["bmkg_stasiun"]


def muat_pemetaan(path: Path | None = None) -> dict:
    """Membaca pemetaan stasiun -> zona (config/stasiun_bmkg.json)."""
    path = path or AKAR_REPO / konfigurasi()["berkas_pemetaan"]
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def zona_valid(pemetaan: dict) -> list[str]:
    """Semua zona yang diizinkan pemetaan."""
    return list(pemetaan.get("zona_hujan", [])) + list(pemetaan.get("zona_lain", []))


def cari_stasiun(nama: str, pemetaan: dict) -> tuple[str, str] | None:
    """Mencocokkan nama stasiun (dari berkas) ke entri pemetaan lewat nama atau alias.

    Kembali:
        (nama baku, zona) atau None bila tidak terdaftar.
    """
    n = _norm(nama)
    if not n:
        return None
    for baku, info in pemetaan.get("stasiun", {}).items():
        kandidat = [baku] + list(info.get("alias", []))
        if any(_norm(k) == n or (len(_norm(k)) >= 6 and _norm(k) in n) for k in kandidat):
            return baku, info["zona"]
    return None


def _cari_judul(mentah: pd.DataFrame) -> tuple[int, int, int, str | None]:
    """Mencari baris judul tabel, kolom tanggal, kolom hujan, dan nama stasiun di metadata.

    Kembali:
        (indeks baris judul, indeks kolom tanggal, indeks kolom hujan, nama stasiun atau None).
    Galat:
        ValueError bila kolom tanggal atau hujan tidak ditemukan.
    """
    nama_stasiun = None
    for i in range(min(len(mentah), 40)):
        sel = [str(v).strip() for v in mentah.iloc[i].tolist()]
        normal = [_norm(v) for v in sel]
        for j, v in enumerate(normal):  # metadata "Nama Stasiun : ..."
            if v.startswith("namastasiun"):
                isi = sel[j].split(":", 1)[1].strip() if ":" in sel[j] else ""
                if not isi:
                    isi = next((s.lstrip(": ").strip() for s in sel[j + 1:] if s and s.lower() != "nan" and s.strip(": ")), "")
                nama_stasiun = isi or nama_stasiun
        kol_tgl = next((j for j, v in enumerate(normal) if v in NAMA_KOLOM_TANGGAL), None)
        kol_rr = next((j for j, v in enumerate(normal) if v in NAMA_KOLOM_HUJAN), None)
        if kol_tgl is not None and kol_rr is not None:
            return i, kol_tgl, kol_rr, nama_stasiun
    raise ValueError("kolom Tanggal dan curah hujan (RR) tidak ditemukan")


def baca_berkas(path: Path) -> pd.DataFrame:
    """Membaca satu berkas stasiun menjadi tabel mentah (stasiun, tanggal, nilai_mentah, berkas).

    Baris yang tanggalnya tidak terbaca (catatan kaki, keterangan kode) dibuang.
    """
    if path.suffix.lower() == ".csv":
        mentah = pd.read_csv(path, header=None, dtype=str, encoding="utf-8-sig", sep=None, engine="python")
    else:
        mentah = pd.read_excel(path, header=None, dtype=object)
    i, kol_tgl, kol_rr, nama = _cari_judul(mentah)
    tabel = mentah.iloc[i + 1:, [kol_tgl, kol_rr]].copy()
    tabel.columns = ["tanggal", "nilai_mentah"]
    tgl = pd.to_datetime(tabel["tanggal"], errors="coerce", dayfirst=True, format="mixed")
    tabel = tabel.assign(tanggal=tgl.dt.normalize()).dropna(subset=["tanggal"])
    tabel["stasiun"] = nama or path.stem.replace("_", " ")
    tabel["berkas"] = path.name
    return tabel.reset_index(drop=True)


def bersihkan(tabel: pd.DataFrame, kode_anomali=(8888, 9999)) -> pd.DataFrame:
    """Membersihkan nilai: kode anomali, nilai negatif, nilai tak terbaca, dan tanggal ganda.

    - 8888/9999 dan nilai negatif -> NaN (catatan_qc menyebut alasannya);
    - teks tak terbaca -> NaN;
    - tanggal ganda per stasiun: bila nilainya sama disimpan satu, bila berbeda -> satu baris NaN.
    Kembali:
        Tabel (stasiun, tanggal, nilai, catatan_qc, berkas) tanpa tanggal ganda.
    """
    d = tabel.copy()
    teks = d["nilai_mentah"].astype(str).str.strip().str.replace(",", ".", regex=False)
    nilai = pd.to_numeric(teks, errors="coerce")
    catatan = np.where(nilai.isna() & ~teks.str.lower().isin(["", "nan", "none", "-"]), "tak terbaca", "")
    catatan = np.where(nilai.isna() & teks.str.lower().isin(["", "nan", "none", "-"]), "kosong", catatan)
    anomali = nilai.isin(list(kode_anomali))
    catatan = np.where(anomali, "kode " + nilai.fillna(0).astype(int).astype(str), catatan)
    negatif = nilai < 0
    catatan = np.where(negatif, "negatif", catatan)
    d["nilai"] = nilai.where(~anomali & ~negatif).astype(float)
    d["catatan_qc"] = catatan

    hasil = []
    for (stasiun, tanggal), grup in d.groupby(["stasiun", "tanggal"], sort=True):
        if len(grup) == 1:
            hasil.append(grup.iloc[0])
            continue
        baris = grup.iloc[0].copy()
        semua_terisi = grup["nilai"].notna().all()
        unik = grup["nilai"].dropna().unique()
        if semua_terisi and len(unik) == 1:      # salinan identik: simpan satu
            baris["catatan_qc"] = "tanggal ganda (nilai sama)"
        elif len(unik) == 0:                     # semua kosong/anomali: tetap kosong
            baris["catatan_qc"] = "tanggal ganda (semua kosong)"
        else:                                    # nilai bertentangan (termasuk sebagian kosong)
            baris["nilai"] = np.nan
            baris["catatan_qc"] = "tanggal ganda (nilai berbeda)"
        hasil.append(baris)
    if not hasil:
        return d.iloc[0:0][["stasiun", "tanggal", "nilai", "catatan_qc", "berkas"]]
    return pd.DataFrame(hasil)[["stasiun", "tanggal", "nilai", "catatan_qc", "berkas"]].reset_index(drop=True)


def ambil(dir_mentah: Path | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Membaca semua berkas .csv/.xlsx di folder mentah BMKG.

    Kembali:
        (tabel mentah gabungan, daftar pesan untuk berkas yang gagal dibaca).
    """
    dir_mentah = dir_mentah or AKAR_REPO / konfigurasi()["dir_mentah"]
    pesan, bagian = [], []
    if not dir_mentah.exists():
        return pd.DataFrame(columns=["tanggal", "nilai_mentah", "stasiun", "berkas"]), [f"folder {dir_mentah} belum ada"]
    for path in sorted(dir_mentah.iterdir()):
        if path.suffix.lower() not in EKSTENSI:
            continue
        try:
            bagian.append(baca_berkas(path))
        except Exception as galat:  # berkas rusak/format lain: dilaporkan, tidak menghentikan berkas lain
            pesan.append(f"{path.name}: {galat}")
    if not bagian:
        return pd.DataFrame(columns=["tanggal", "nilai_mentah", "stasiun", "berkas"]), pesan or ["tidak ada berkas .csv/.xlsx"]
    return pd.concat(bagian, ignore_index=True), pesan


def ke_format_standar(tabel_bersih: pd.DataFrame, pemetaan: dict) -> tuple[pd.DataFrame, list[str]]:
    """Memetakan stasiun ke zona dan menyusun skema keluaran standar.

    Kembali:
        (tabel berskema KOLOM_WAJIB + stasiun, catatan_qc; daftar stasiun yang tidak terpetakan).
    """
    if tabel_bersih.empty:
        return tabel_kosong(["stasiun", "catatan_qc"]), []
    cocok = {s: cari_stasiun(s, pemetaan) for s in tabel_bersih["stasiun"].unique()}
    tak_terpetakan = sorted(s for s, c in cocok.items() if c is None)
    d = tabel_bersih[tabel_bersih["stasiun"].map(lambda s: cocok[s] is not None)].copy()
    d["zona"] = d["stasiun"].map(lambda s: cocok[s][1])
    d["stasiun"] = d["stasiun"].map(lambda s: cocok[s][0])
    d["sumber"] = SUMBER
    d["status_data"] = "nyata"
    d = d[["tanggal", "zona", "nilai", "sumber", "status_data", "stasiun", "catatan_qc"]]
    d = d.sort_values(["zona", "stasiun", "tanggal"]).reset_index(drop=True)
    return validasi(d, zona_valid(pemetaan)), tak_terpetakan


def jalankan(dir_mentah: Path | None = None, path_keluar: Path | None = None,
             pemetaan: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Pipeline ambil -> bersihkan -> petakan zona -> simpan data/interim/bmkg_clean.csv.

    Kembali:
        (tabel bersih berskema standar, laporan {berkas_gagal, stasiun_tak_terpetakan, jumlah_nan}).
    """
    pemetaan = pemetaan or muat_pemetaan()
    mentah, gagal = ambil(dir_mentah)
    bersih = bersihkan(mentah, tuple(konfigurasi().get("kode_anomali", (8888, 9999)))) if len(mentah) else mentah
    hasil, tak = ke_format_standar(bersih, pemetaan) if len(mentah) else (tabel_kosong(["stasiun", "catatan_qc"]), [])
    simpan_csv(hasil, path_keluar or path_data("interim", "bmkg_clean.csv"))
    laporan = {"berkas_gagal": gagal, "stasiun_tak_terpetakan": tak,
               "jumlah_baris": int(len(hasil)), "jumlah_nan": int(hasil["nilai"].isna().sum()) if len(hasil) else 0}
    return hasil, laporan


def main(argv: list[str] | None = None) -> None:
    """CLI: PYTHONPATH=src python -m sigap_ka.inputs.bmkg"""
    argparse.ArgumentParser(description="Bersihkan curah hujan stasiun BMKG").parse_args(argv)
    hasil, lap = jalankan()
    print(f"bmkg_clean.csv: {lap['jumlah_baris']} baris, {lap['jumlah_nan']} NaN")
    for p in lap["berkas_gagal"]:
        print(f"  [catatan] {p}")
    for s in lap["stasiun_tak_terpetakan"]:
        print(f"  [tak terpetakan] {s} (tambahkan ke config/stasiun_bmkg.json)")
    if len(hasil):
        print(hasil.groupby(["zona", "stasiun"])["tanggal"].agg(["min", "max", "count"]).to_string())


if __name__ == "__main__":
    main()
