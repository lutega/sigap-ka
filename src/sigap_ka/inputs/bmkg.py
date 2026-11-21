"""
Tujuan      : Membaca curah hujan stasiun BMKG (harian atau bulanan) dari berkas .csv/.xlsx,
              membersihkan kode anomali, memetakan stasiun ke zona SIGAP-KA, dan menyimpan tabel bersih.
Lapis       : S (Sensing), data tambahan (portal data BMKG).
Sumber      : Berkas unduhan portal data BMKG di data/raw/bmkg/ (tidak di-commit). Format yang sudah
              diverifikasi dengan berkas asli (DataIklimBulanan_*.xlsx): satu lembar per stasiun,
              metadata (ID WMO, NAMA STASIUN, LINTANG, BUJUR, ELEVASI), judul tabel "Periode | rainfall"
              (YYYY-MM, jumlah sebulan dalam mm), catatan kaki kode 8888 (tidak terukur) dan 9999
              (tidak ada data). Format harian (judul "Tanggal | ... | RR") juga ditangani.
              Pemetaan stasiun -> zona di config/stasiun_bmkg.json (dirujuk params.json).
Masukan     : Folder berkas mentah.
Keluaran    : data/interim/bmkg_clean.csv berskema base.KOLOM_WAJIB + stasiun, id_wmo, lat, lon,
              resolusi ('harian'/'bulanan'), catatan_qc; sumber = "bmkg", status_data = "nyata".
Keterbatasan: Data bulanan tidak dipakai fitur harian (hanya untuk validasi IMERG). Stasiun yang tidak
              ada di pemetaan dilewati dan dilaporkan. Stasiun Kota Semarang dipetakan ke zona
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
NAMA_KOLOM_TANGGAL = ("tanggal", "tgl", "date", "waktu", "periode", "bulan")
KOLOM_TAMBAHAN = ["stasiun", "id_wmo", "lat", "lon", "resolusi", "catatan_qc"]
POLA_BULAN = re.compile(r"^\s*(\d{4})-(\d{1,2})\s*$")


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


def cari_stasiun(nama: str, pemetaan: dict, id_wmo: str | None = None) -> tuple[str, str] | None:
    """Mencocokkan stasiun ke entri pemetaan lewat ID WMO (bila ada), nama, atau alias.

    Kembali:
        (nama baku, zona) atau None bila tidak terdaftar.
    """
    for baku, info in pemetaan.get("stasiun", {}).items():
        if id_wmo and str(info.get("id_wmo", "")) == str(id_wmo):
            return baku, info["zona"]
    n = _norm(nama)
    if not n:
        return None
    for baku, info in pemetaan.get("stasiun", {}).items():
        kandidat = [baku] + list(info.get("alias", []))
        if any(_norm(k) == n or (len(_norm(k)) >= 6 and _norm(k) in n) for k in kandidat):
            return baku, info["zona"]
    return None


def _nilai_meta(sel: list[str], j: int) -> str:
    """Nilai metadata pada baris: teks setelah ':' di sel yang sama, atau sel terisi berikutnya."""
    if ":" in sel[j]:
        isi = sel[j].split(":", 1)[1].strip()
        if isi:
            return isi
    return next((s.lstrip(": ").strip() for s in sel[j + 1:] if s and s.lower() != "nan" and s.strip(": ")), "")


def _cari_judul(mentah: pd.DataFrame) -> tuple[int, int, int, dict]:
    """Mencari baris judul tabel, kolom tanggal/periode, kolom hujan, dan metadata stasiun.

    Kembali:
        (indeks baris judul, kolom tanggal, kolom hujan, metadata {nama, id_wmo, lat, lon}).
    Galat:
        ValueError bila kolom tanggal/periode atau hujan tidak ditemukan.
    """
    meta = {"nama": None, "id_wmo": None, "lat": None, "lon": None}
    kunci_meta = {"namastasiun": "nama", "idwmo": "id_wmo", "lintang": "lat", "bujur": "lon"}
    for i in range(min(len(mentah), 40)):
        sel = [str(v).strip() for v in mentah.iloc[i].tolist()]
        normal = [_norm(v) for v in sel]
        for j, v in enumerate(normal):
            for awalan, kunci in kunci_meta.items():
                if v.startswith(awalan):
                    meta[kunci] = _nilai_meta(sel, j) or meta[kunci]
        kol_tgl = next((j for j, v in enumerate(normal) if v in NAMA_KOLOM_TANGGAL), None)
        kol_rr = next((j for j, v in enumerate(normal) if v in NAMA_KOLOM_HUJAN), None)
        if kol_tgl is not None and kol_rr is not None:
            for k in ("lat", "lon"):
                meta[k] = pd.to_numeric(str(meta[k]).replace(",", "."), errors="coerce") if meta[k] else None
            return i, kol_tgl, kol_rr, meta
    raise ValueError("kolom Tanggal/Periode dan curah hujan (RR/rainfall) tidak ditemukan")


def _urai_tanggal(nilai: pd.Series) -> tuple[pd.Series, str]:
    """Mengurai kolom tanggal: 'YYYY-MM' -> awal bulan (resolusi bulanan), selain itu tanggal harian.

    Kembali:
        (Series tanggal ter-normalisasi, resolusi 'bulanan' atau 'harian').
    """
    teks = nilai.astype(str)
    cocok_bulan = teks.str.match(POLA_BULAN)
    harian = pd.to_datetime(nilai.where(~cocok_bulan), errors="coerce", dayfirst=True, format="mixed")
    # baris catatan kaki tidak terbaca sebagai bulan maupun tanggal sehingga tidak memengaruhi keputusan
    if cocok_bulan.sum() > 0 and cocok_bulan.sum() >= harian.notna().sum():
        tgl = pd.to_datetime(teks.where(cocok_bulan) + "-01", format="%Y-%m-%d", errors="coerce")
        return tgl, "bulanan"
    return harian.dt.normalize(), "harian"


def baca_lembar(mentah: pd.DataFrame, nama_cadangan: str, berkas: str) -> pd.DataFrame:
    """Satu tabel stasiun (lembar Excel atau CSV) menjadi tabel mentah berkolom seragam."""
    i, kol_tgl, kol_rr, meta = _cari_judul(mentah)
    tabel = mentah.iloc[i + 1:, [kol_tgl, kol_rr]].copy()
    tabel.columns = ["tanggal", "nilai_mentah"]
    tgl, resolusi = _urai_tanggal(tabel["tanggal"])
    tabel = tabel.assign(tanggal=tgl).dropna(subset=["tanggal"])  # catatan kaki ikut terbuang
    tabel["stasiun"] = meta["nama"] or nama_cadangan
    tabel["id_wmo"] = meta["id_wmo"]
    tabel["lat"] = meta["lat"]
    tabel["lon"] = meta["lon"]
    tabel["resolusi"] = resolusi
    tabel["berkas"] = berkas
    return tabel.reset_index(drop=True)


def baca_berkas(path: Path) -> pd.DataFrame:
    """Membaca satu berkas (.csv atau semua lembar .xlsx) menjadi tabel mentah gabungan.

    Lembar tanpa tabel curah hujan dilewati; bila tidak ada lembar yang terbaca, galat ValueError.
    """
    if path.suffix.lower() == ".csv":
        mentah = pd.read_csv(path, header=None, dtype=str, encoding="utf-8-sig", sep=None, engine="python")
        return baca_lembar(mentah, path.stem.replace("_", " "), path.name)
    bagian, gagal = [], []
    for nama_lembar, mentah in pd.read_excel(path, header=None, dtype=object, sheet_name=None).items():
        try:
            bagian.append(baca_lembar(mentah, str(nama_lembar), f"{path.name}#{nama_lembar}"))
        except ValueError as galat:
            gagal.append(f"{nama_lembar}: {galat}")
    if not bagian:
        raise ValueError("; ".join(gagal) or "tidak ada lembar")
    return pd.concat(bagian, ignore_index=True)


def bersihkan(tabel: pd.DataFrame, kode_anomali=(8888, 9999)) -> pd.DataFrame:
    """Membersihkan nilai: kode anomali, nilai negatif, nilai tak terbaca, dan tanggal ganda.

    - 8888/9999 dan nilai negatif -> NaN (catatan_qc menyebut alasannya);
    - teks tak terbaca -> NaN;
    - tanggal ganda per stasiun dan resolusi: bila nilainya sama disimpan satu, bila berbeda -> NaN.
    Kembali:
        Tabel (stasiun, tanggal, nilai, catatan_qc, id_wmo, lat, lon, resolusi, berkas) tanpa ganda.
    """
    kolom = ["stasiun", "tanggal", "nilai", "catatan_qc", "id_wmo", "lat", "lon", "resolusi", "berkas"]
    d = tabel.copy()
    for k in ("id_wmo", "lat", "lon"):
        if k not in d:
            d[k] = None
    if "resolusi" not in d:
        d["resolusi"] = "harian"
    teks = d["nilai_mentah"].astype(str).str.strip().str.replace(",", ".", regex=False)
    nilai = pd.to_numeric(teks, errors="coerce")
    kosong = teks.str.lower().isin(["", "nan", "none", "-"])
    catatan = np.where(nilai.isna() & ~kosong, "tak terbaca", "")
    catatan = np.where(nilai.isna() & kosong, "kosong", catatan)
    anomali = nilai.isin(list(kode_anomali))
    catatan = np.where(anomali, "kode " + nilai.fillna(0).astype(int).astype(str), catatan)
    negatif = nilai < 0
    catatan = np.where(negatif, "negatif", catatan)
    d["nilai"] = nilai.where(~anomali & ~negatif).astype(float)
    d["catatan_qc"] = catatan

    hasil = []
    for _, grup in d.groupby(["stasiun", "resolusi", "tanggal"], sort=True):
        baris = grup.iloc[0].copy()
        if len(grup) > 1:
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
        return d.iloc[0:0][kolom]
    return pd.DataFrame(hasil)[kolom].reset_index(drop=True)


def ambil(dir_mentah: Path | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Membaca semua berkas .csv/.xlsx di folder mentah BMKG.

    Kembali:
        (tabel mentah gabungan, daftar pesan untuk berkas yang gagal dibaca).
    """
    dir_mentah = dir_mentah or AKAR_REPO / konfigurasi()["dir_mentah"]
    kosong = pd.DataFrame(columns=["tanggal", "nilai_mentah", "stasiun", "berkas"])
    if not dir_mentah.exists():
        return kosong, [f"folder {dir_mentah} belum ada"]
    pesan, bagian = [], []
    for path in sorted(dir_mentah.iterdir()):
        if path.suffix.lower() not in EKSTENSI:
            continue
        try:
            bagian.append(baca_berkas(path))
        except Exception as galat:  # berkas rusak/format lain: dilaporkan, tidak menghentikan berkas lain
            pesan.append(f"{path.name}: {galat}")
    if not bagian:
        return kosong, pesan or ["tidak ada berkas .csv/.xlsx"]
    kolom = list(dict.fromkeys(c for b in bagian for c in b.columns))
    bagian = [b.dropna(axis=1, how="all") for b in bagian]  # kolom metadata kosong (mis. CSV tanpa ID WMO)
    return pd.concat(bagian, ignore_index=True).reindex(columns=kolom), pesan


def ke_format_standar(tabel_bersih: pd.DataFrame, pemetaan: dict) -> tuple[pd.DataFrame, list[str]]:
    """Memetakan stasiun ke zona dan menyusun skema keluaran standar.

    Kembali:
        (tabel berskema KOLOM_WAJIB + KOLOM_TAMBAHAN; daftar stasiun yang tidak terpetakan).
    """
    if tabel_bersih.empty:
        return tabel_kosong(KOLOM_TAMBAHAN), []
    pasangan = tabel_bersih[["stasiun", "id_wmo"]].drop_duplicates()
    cocok = {(s, w): cari_stasiun(s, pemetaan, None if pd.isna(w) else str(w).strip()) for s, w in pasangan.itertuples(index=False)}
    kunci = list(zip(tabel_bersih["stasiun"], tabel_bersih["id_wmo"]))
    tak_terpetakan = sorted({s for (s, _), c in cocok.items() if c is None})
    d = tabel_bersih[[cocok[k] is not None for k in kunci]].copy()
    k_d = list(zip(d["stasiun"], d["id_wmo"]))
    d["zona"] = [cocok[k][1] for k in k_d]
    d["stasiun"] = [cocok[k][0] for k in k_d]
    d["sumber"] = SUMBER
    d["status_data"] = "nyata"
    d = d[["tanggal", "zona", "nilai", "sumber", "status_data"] + KOLOM_TAMBAHAN]
    d = d.sort_values(["zona", "stasiun", "resolusi", "tanggal"]).reset_index(drop=True)
    return validasi(d, zona_valid(pemetaan)), tak_terpetakan


def jalankan(dir_mentah: Path | None = None, path_keluar: Path | None = None,
             pemetaan: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Pipeline ambil -> bersihkan -> petakan zona -> simpan data/interim/bmkg_clean.csv.

    Kembali:
        (tabel bersih berskema standar, laporan {berkas_gagal, stasiun_tak_terpetakan, jumlah_nan,
        resolusi}).
    """
    pemetaan = pemetaan or muat_pemetaan()
    mentah, gagal = ambil(dir_mentah)
    if len(mentah):
        bersih = bersihkan(mentah, tuple(konfigurasi().get("kode_anomali", (8888, 9999))))
        hasil, tak = ke_format_standar(bersih, pemetaan)
    else:
        hasil, tak = tabel_kosong(KOLOM_TAMBAHAN), []
    simpan_csv(hasil, path_keluar or path_data("interim", "bmkg_clean.csv"))
    laporan = {"berkas_gagal": gagal, "stasiun_tak_terpetakan": tak, "jumlah_baris": int(len(hasil)),
               "jumlah_nan": int(hasil["nilai"].isna().sum()) if len(hasil) else 0,
               "resolusi": sorted(hasil["resolusi"].dropna().unique().tolist()) if len(hasil) else []}
    return hasil, laporan


def main(argv: list[str] | None = None) -> None:
    """CLI: PYTHONPATH=src python -m sigap_ka.inputs.bmkg"""
    argparse.ArgumentParser(description="Bersihkan curah hujan stasiun BMKG").parse_args(argv)
    hasil, lap = jalankan()
    print(f"bmkg_clean.csv: {lap['jumlah_baris']} baris, {lap['jumlah_nan']} NaN, resolusi {lap['resolusi']}")
    for p in lap["berkas_gagal"]:
        print(f"  [catatan] {p}")
    for s in lap["stasiun_tak_terpetakan"]:
        print(f"  [tak terpetakan] {s} (tambahkan ke config/stasiun_bmkg.json)")
    if len(hasil):
        ring = hasil.groupby(["zona", "stasiun", "resolusi"]).agg(
            awal=("tanggal", "min"), akhir=("tanggal", "max"), baris=("nilai", "size"), kosong=("nilai", lambda s: int(s.isna().sum())))
        print(ring.to_string())


if __name__ == "__main__":
    main()
