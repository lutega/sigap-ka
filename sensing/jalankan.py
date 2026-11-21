"""
Tujuan      : CLI lapis S: mengambil data dari sumber (raw -> processed), mencatat asal data,
              dan memuat data olahan ke database agar API dan demo berjalan offline.
Lapis       : S (Sensing).
Sumber      : Modul-modul di sensing/.
Masukan     : Perintah CLI, contoh:
                python -m sensing.jalankan nasa_power --dari 2024-01-01 --sampai 2026-11-20
                python -m sensing.jalankan bmkg
                python -m sensing.jalankan manual
                python -m sensing.jalankan muat
                python -m sensing.jalankan status
Keluaran    : data/raw/<sumber>/..., data/processed/*.csv, data/processed/log_pengambilan.csv,
              dan baris di database (perintah muat atau tanpa --tanpa-db).
Keterbatasan: Perintah unduh butuh internet; perintah muat dan manual berjalan offline.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime

import pandas as pd

from sensing import (
    hujan_nasa_power,
    jadwal_ka,
    kejadian_manual,
    muka_air_glapan,
    prakiraan_bmkg,
)
from sensing.registri import modul_kejadian, status_sumber
from sensing.standar import SumberTidakTersedia, baca_olahan, dir_olahan, simpan_mentah, simpan_olahan

KUNCI_HUJAN = ["waktu", "lokasi", "sumber"]
KUNCI_PRAKIRAAN = ["waktu_terbit", "waktu", "lokasi", "sumber"]
BERKAS_LOG = "log_pengambilan"


def catat_log(sumber: str, status: str, rentang_mulai=None, rentang_selesai=None,
              tautan: str | None = None, jumlah_baris: int = 0, pesan: str | None = None) -> None:
    """Menambahkan catatan asal data ke data/processed/log_pengambilan.csv (dimuat ke DB oleh 'muat')."""
    baris = pd.DataFrame([{
        "sumber": sumber, "waktu_ambil": datetime.now().replace(microsecond=0), "status": status,
        "rentang_mulai": rentang_mulai, "rentang_selesai": rentang_selesai,
        "versi_atau_tautan": tautan, "jumlah_baris": jumlah_baris, "pesan": pesan,
    }])
    path = dir_olahan() / f"{BERKAS_LOG}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    baris.to_csv(path, mode="a", header=not path.exists(), index=False, encoding="utf-8",
                 lineterminator="\n")


def ambil_nasa_power(dari: date, sampai: date, daftar_lokasi=("lokal", "hulu", "gundih"),
                     sesi_http=None) -> pd.DataFrame:
    """Mengunduh NASA POWER untuk beberapa lokasi, menyimpan raw/processed, dan mencatat log."""
    semua = []
    for lok in daftar_lokasi:
        try:
            df, mentah = hujan_nasa_power.jalankan(lok, dari, sampai, sesi_http=sesi_http)
        except SumberTidakTersedia as galat:
            catat_log("nasa_power", "gagal", dari, sampai, pesan=f"{lok}: {galat}")
            print(f"  [gagal] nasa_power {lok}: {galat}")
            continue
        simpan_mentah("nasa_power", mentah)
        catat_log("nasa_power", "sukses", dari, sampai, hujan_nasa_power.tautan(mentah), len(df), lok)
        print(f"  [sukses] nasa_power {lok}: {len(df)} hari, kosong {int(df['nilai'].isna().sum())}")
        semua.append(df)
    if not semua:
        return pd.DataFrame()
    hasil = pd.concat(semua, ignore_index=True)
    simpan_olahan("hujan_nasa_power", hasil, KUNCI_HUJAN)
    return hasil


def ambil_imerg(dari: date, sampai: date, daftar_lokasi=("lokal", "hulu", "gundih"),
                daftar_produk=("late", "final"), sesi_http=None) -> pd.DataFrame:
    """Mengunduh IMERG harian (Late dan Final) untuk beberapa lokasi, menyimpan raw/processed, mencatat log.

    Token Earthdata tidak ikut tersimpan: yang dicatat hanya URL permintaan tanpa header.
    """
    from sensing import hujan_gpm_imerg
    semua = []
    for produk in daftar_produk:
        for lok in daftar_lokasi:
            sumber = hujan_gpm_imerg.SUMBER_PRODUK[produk]
            try:
                df, mentah = hujan_gpm_imerg.jalankan(lok, dari, sampai, produk, sesi_http=sesi_http)
            except SumberTidakTersedia as galat:
                catat_log(sumber, "gagal", dari, sampai, pesan=f"{lok}: {galat}")
                print(f"  [gagal] {sumber} {lok}: {galat}")
                continue
            simpan_mentah(sumber, mentah if isinstance(mentah, dict) else {"harian": mentah})
            tautan = mentah["url"] if isinstance(mentah, dict) else "GES DISC OPeNDAP per hari"
            ada = df["nilai"].notna()
            catat_log(sumber, "sukses", df.loc[ada, "waktu"].min(), df.loc[ada, "waktu"].max(), tautan, int(ada.sum()), lok)
            print(f"  [sukses] {sumber} {lok}: {int(ada.sum())} hari berisi, sel {df['sel_grid'].iloc[0] if 'sel_grid' in df else '?'}")
            semua.append(df[ada])
    if not semua:
        return pd.DataFrame()
    hasil = pd.concat(semua, ignore_index=True)
    simpan_olahan("hujan_gpm_imerg", hasil, KUNCI_HUJAN)
    return hasil


def ambil_bmkg(sesi_http=None) -> pd.DataFrame:
    """Mengunduh prakiraan BMKG terkini, menyimpan raw/processed, dan mencatat log."""
    try:
        df, mentah = prakiraan_bmkg.jalankan(sesi_http=sesi_http)
    except SumberTidakTersedia as galat:
        catat_log("bmkg_prakiraan", "gagal", pesan=str(galat))
        print(f"  [gagal] bmkg_prakiraan: {galat}")
        return pd.DataFrame()
    simpan_mentah("bmkg_prakiraan", mentah)
    p = mentah["_permintaan"]
    catat_log("bmkg_prakiraan", "sukses", df["waktu"].min(), df["waktu"].max(),
              f"{p['url']}?adm4={p['adm4']}", len(df))
    simpan_olahan("prakiraan_bmkg", df, KUNCI_PRAKIRAAN)
    print(f"  [sukses] bmkg_prakiraan: {len(df)} periode")
    return df


def ambil_manual() -> dict[str, pd.DataFrame]:
    """Memproses berkas manual (Glapan, katalog kejadian, jadwal KA) ke data/processed."""
    hasil = {}
    glapan, _ = muka_air_glapan.jalankan()
    simpan_olahan("muka_air_glapan", glapan, ["waktu", "lokasi", "sumber"], ganti=True)
    catat_log("glapan_bnpb", "sukses", glapan["waktu"].min(), glapan["waktu"].max(),
              "data/manual/muka_air_glapan.csv", len(glapan))
    hasil["muka_air_glapan"] = glapan

    m, catatan = modul_kejadian()
    kej = m.jalankan()
    simpan_olahan("kejadian", kej, ["id"], ganti=True)
    catat_log(m.NAMA_SUMBER, "sukses", tautan="data/manual", jumlah_baris=len(kej), pesan=catatan)
    hasil["kejadian"] = kej

    jad = jadwal_ka.jalankan()
    simpan_olahan("jadwal_ka", jad, ["nomor"], ganti=True)
    catat_log("jadwal_ka", "sukses" if not jad["is_simulated"].any() else "cadangan",
              jumlah_baris=len(jad), pesan="placeholder dummy" if jad["is_simulated"].any() else None)
    hasil["jadwal_ka"] = jad
    for nama, df in hasil.items():
        print(f"  [sukses] {nama}: {len(df)} baris")
    return hasil


def muat_ke_db(engine=None) -> dict[str, int]:
    """Memuat seluruh data olahan (CSV di data/processed) ke database.

    Kembali:
        Jumlah baris per tabel.
    """
    from db import repositori as repo
    from db.inisialisasi import inisialisasi
    from db.koneksi import buat_engine, sesi_dari
    from db.model import LogPengambilan

    engine = engine or buat_engine()
    inisialisasi(engine)
    jumlah = {}
    with sesi_dari(engine) as sesi:
        jumlah["obs_hujan"] = 0
        for berkas in ("hujan_nasa_power", "hujan_gpm_imerg"):
            hujan = baca_olahan(berkas)
            if not hujan.empty:
                jumlah["obs_hujan"] += repo.simpan_obs_hujan(sesi, hujan)
        pk = baca_olahan("prakiraan_bmkg")
        if not pk.empty:
            jumlah["prakiraan_hujan"] = repo.simpan_prakiraan(sesi, pk)
        glapan = baca_olahan("muka_air_glapan")
        if not glapan.empty:
            jumlah["obs_muka_air"] = repo.simpan_muka_air(sesi, glapan)
        kej = baca_olahan("kejadian")
        if not kej.empty:
            kej["tanggal"] = pd.to_datetime(kej["tanggal"], errors="coerce").dt.date
            jumlah["kejadian"] = repo.simpan_kejadian(sesi, kejadian_manual.ke_baris_db(kej))
        jad = baca_olahan("jadwal_ka")
        if not jad.empty:
            jad["asal"] = jad.get("asal", "")
            jumlah["jadwal_ka"] = repo.simpan_jadwal(sesi, jadwal_ka.ke_baris_db(jad))
        log = baca_olahan(BERKAS_LOG)
        if not log.empty:
            sesi.query(LogPengambilan).delete()  # log CSV adalah sumber kebenaran catatan asal data
            for r in log.to_dict("records"):
                repo.catat_pengambilan(
                    sesi, r["sumber"], r["status"],
                    rentang_mulai=_dt(r.get("rentang_mulai")), rentang_selesai=_dt(r.get("rentang_selesai")),
                    versi_atau_tautan=_teks(r.get("versi_atau_tautan")),
                    jumlah_baris=int(r.get("jumlah_baris") or 0), pesan=_teks(r.get("pesan")),
                    waktu_ambil=_dt(r.get("waktu_ambil")))
            jumlah["log_pengambilan"] = len(log)
    return jumlah


def _dt(v):
    """Nilai waktu dari CSV menjadi datetime Python atau None."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
        return None
    t = pd.to_datetime(v, errors="coerce")
    return None if pd.isna(t) else t.to_pydatetime()


def _teks(v):
    """Nilai teks dari CSV (NaN menjadi None)."""
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)


def main(argv: list[str] | None = None) -> None:
    """Titik masuk CLI."""
    ap = argparse.ArgumentParser(description="Lapis S SIGAP-KA: ambil dan muat data")
    sub = ap.add_subparsers(dest="perintah", required=True)
    p = sub.add_parser("nasa_power", help="unduh hujan harian NASA POWER")
    p.add_argument("--dari", type=date.fromisoformat, default=date(2024, 1, 1))
    p.add_argument("--sampai", type=date.fromisoformat, default=date.today())
    p.add_argument("--lokasi", nargs="+", default=["lokal", "hulu", "gundih"])
    q = sub.add_parser("imerg", help="unduh hujan harian GPM IMERG (Late dan Final) lewat Giovanni")
    q.add_argument("--dari", type=date.fromisoformat, default=date(2024, 1, 1))
    q.add_argument("--sampai", type=date.fromisoformat, default=date.today())
    q.add_argument("--lokasi", nargs="+", default=["lokal", "hulu", "gundih"])
    q.add_argument("--produk", nargs="+", default=["late", "final"], choices=["late", "final"])
    sub.add_parser("bmkg", help="unduh prakiraan BMKG terkini")
    sub.add_parser("manual", help="proses berkas manual (Glapan, kejadian, jadwal)")
    sub.add_parser("muat", help="muat data/processed ke database")
    sub.add_parser("status", help="tampilkan kesiapan sumber")
    arg = ap.parse_args(argv)

    if arg.perintah == "nasa_power":
        ambil_nasa_power(arg.dari, arg.sampai, arg.lokasi)
    elif arg.perintah == "imerg":
        ambil_imerg(arg.dari, arg.sampai, arg.lokasi, arg.produk)
    elif arg.perintah == "bmkg":
        ambil_bmkg()
    elif arg.perintah == "manual":
        ambil_manual()
    elif arg.perintah == "muat":
        print(f"Dimuat ke database: {muat_ke_db()}")
    elif arg.perintah == "status":
        for s in status_sumber():
            tanda = "siap" if s["siap"] else "belum"
            print(f"  {s['nama']:<18} {s['kelompok']:<9} {tanda:<6} {s['alasan']}")


if __name__ == "__main__":
    main()
