"""
Tujuan      : Menguji ketelitian hujan satelit GPM IMERG (Late dan Final) terhadap pengukuran stasiun BMKG
              di Kota Semarang, pada total bulanan di sel IMERG yang sama dengan stasiun.
Lapis       : Validasi masukan lapis S (bahan batas klaim).
Sumber      : data/interim/bmkg_clean.csv (inputs/bmkg.py, resolusi bulanan, zona semarang_pembanding);
              data/processed/hujan_gpm_imerg.csv lokasi semarang_pembanding (inputs/imerg.py).
Masukan     : -
Keluaran    : data/processed/validasi_imerg_bmkg.csv (per bulan: tiap stasiun, rerata stasiun,
              IMERG Late, IMERG Final) dan metrik bias (%), korelasi, MAE, RMSE per produk.
Keterbatasan: Hanya satu sel (Semarang, sekitar 25-30 km dari koridor) sehingga tidak langsung
              mewakili hulu Tuntang. IMERG Final dikalibrasi penakar bulanan global (GPCC) sehingga
              wajar lebih dekat ke stasiun; IMERG Late yang relevan untuk jam keputusan. Hari IMERG adalah
              hari UTC (selisih batas bulan sekitar 7 jam diabaikan). Bulan IMERG yang tidak lengkap dibuang.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from sigap_ka.inputs import imerg
from sigap_ka.inputs.base import baca_csv, path_data, simpan_csv

ZONA = "semarang_pembanding"
PRODUK = ("gpm_imerg_late", "gpm_imerg_final")


def imerg_bulanan(harian: pd.DataFrame) -> pd.Series:
    """Total bulanan IMERG dari seri harian; bulan dengan hari kurang dari jumlah hari kalender -> NaN."""
    if harian.empty:
        return pd.Series(dtype=float)
    s = harian.set_index("tanggal")["nilai"]
    bulan = s.index.to_period("M")
    total = s.groupby(bulan).sum(min_count=1)
    jumlah = s.groupby(bulan).count()
    lengkap = jumlah == pd.Series([p.days_in_month for p in jumlah.index], index=jumlah.index)
    total = total.where(lengkap)
    total.index = total.index.to_timestamp()
    return total


def tabel_perbandingan(bmkg: pd.DataFrame, imerg_harian: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Tabel per bulan: kolom per stasiun BMKG, rerata_stasiun, dan tiap produk IMERG.

    Parameter:
        bmkg: tabel bmkg_clean (baris bulanan zona semarang_pembanding dipakai).
        imerg_harian: {produk: tabel harian berskema standar zona semarang_pembanding}.
    """
    b = bmkg[(bmkg["zona"] == ZONA) & (bmkg.get("resolusi", "bulanan") == "bulanan")]
    tabel = b.pivot_table(index="tanggal", columns="stasiun", values="nilai", aggfunc="mean")
    tabel.columns = [str(c) for c in tabel.columns]
    tabel["rerata_stasiun"] = tabel.mean(axis=1, skipna=False)
    for produk, harian in imerg_harian.items():
        tabel[produk] = imerg_bulanan(harian).reindex(tabel.index)
    tabel.index.name = "bulan"
    return tabel.reset_index()


def metrik(tabel: pd.DataFrame, kolom: str, acuan: str = "rerata_stasiun") -> dict:
    """Metrik produk satelit terhadap acuan stasiun pada bulan yang keduanya terisi.

    Kembali:
        dict n_bulan, bias_persen ((sum satelit - sum stasiun)/sum stasiun x 100), korelasi,
        mae_mm, rmse_mm.
    """
    d = tabel[[acuan, kolom]].dropna()
    if len(d) < 2:
        return {"n_bulan": int(len(d)), "bias_persen": None, "korelasi": None, "mae_mm": None, "rmse_mm": None}
    galat = d[kolom] - d[acuan]
    return {
        "n_bulan": int(len(d)),
        "bias_persen": round(float(galat.sum() / d[acuan].sum() * 100), 1),
        "korelasi": round(float(np.corrcoef(d[kolom], d[acuan])[0, 1]), 3),
        "mae_mm": round(float(galat.abs().mean()), 1),
        "rmse_mm": round(float(np.sqrt((galat ** 2).mean())), 1),
    }


def jalankan(path_bmkg: Path | None = None, path_imerg: Path | None = None,
             path_keluar: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """Pipeline: baca BMKG bersih dan IMERG sel Semarang -> tabel perbandingan -> metrik -> simpan."""
    bmkg = baca_csv(path_bmkg or path_data("interim", "bmkg_clean.csv"))
    mentah = imerg.ambil(path_imerg)
    harian = {}
    for produk in PRODUK:
        d = imerg.ke_format_standar(mentah, produk)
        harian[produk] = d[d["zona"] == ZONA]
    tabel = tabel_perbandingan(bmkg, harian)
    simpan_csv(tabel, path_keluar or path_data("processed", "validasi_imerg_bmkg.csv"))
    hasil = {p: metrik(tabel, p) for p in PRODUK}
    sama = tabel.dropna(subset=list(PRODUK))  # perbandingan adil Late vs Final pada bulan yang sama
    hasil["gpm_imerg_late_bulan_final"] = metrik(sama, "gpm_imerg_late")
    stasiun = [c for c in tabel.columns if c.startswith("Stasiun")]
    if len(stasiun) == 2:  # kesesuaian antarstasiun sebagai pembanding skala galat
        hasil["antarstasiun"] = metrik(tabel, stasiun[0], stasiun[1])
    return tabel, hasil


def main(argv: list[str] | None = None) -> None:
    """CLI: PYTHONPATH=src python -m sigap_ka.features.validasi_imerg"""
    argparse.ArgumentParser(description="Validasi IMERG terhadap stasiun BMKG Semarang").parse_args(argv)
    tabel, hasil = jalankan()
    print(tabel.round(1).to_string(index=False))
    for k, m in hasil.items():
        print(f"{k:<16} {m}")


if __name__ == "__main__":
    main()
