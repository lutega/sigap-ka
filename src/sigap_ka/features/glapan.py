"""
Tujuan      : Fitur muka air Bendung Glapan per jam: glapan_relatif (TMA - ambang Awas) dan
              tren_glapan_6j (TMA_t - TMA_(t-6)), dari seri TMA sintetis (inputs/glapan_synth.py).
Lapis       : Penyiapan fitur lapis I.
Sumber      : inputs/glapan_synth.py; ambang Awas dari params.json (muka_air.ambang_awas = 1905,
              nyata dari rilis BNPB).
Masukan     : Seri TMA per jam berskema standar.
Keluaran    : data/interim/glapan_tma_synth.csv (seri TMA sintetis) dan
              data/processed/glapan_features.csv (tanggal, tma, glapan_relatif, tren_glapan_6j,
              sumber, status_data).
Keterbatasan: Fitur ikut sintetis (status_data = sintetis) selama seri TMA belum dari BBWS. Jam yang
              hilang membuat tren 6 jam NaN (indeks per jam dibuat kontinu).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from config import muat_params
from sigap_ka.inputs import glapan_synth
from sigap_ka.inputs.base import path_data, simpan_csv


def hitung_fitur(tma: pd.DataFrame, ambang_awas: float | None = None) -> pd.DataFrame:
    """Fitur per jam dari seri TMA.

    Parameter:
        tma: tabel berskema standar (tanggal per jam, nilai TMA).
        ambang_awas: bawaan params.json muka_air.ambang_awas.
    Kembali:
        DataFrame tanggal, tma, glapan_relatif, tren_glapan_6j, sumber, status_data.
    """
    awas = muat_params().muka_air["ambang_awas"] if ambang_awas is None else ambang_awas
    if tma.empty:
        return pd.DataFrame(columns=["tanggal", "tma", "glapan_relatif", "tren_glapan_6j", "sumber", "status_data"])
    s = tma.set_index("tanggal")["nilai"].sort_index()
    s = s[~s.index.duplicated(keep="last")].asfreq("h")  # indeks per jam kontinu
    return pd.DataFrame({
        "tanggal": s.index,
        "tma": s.to_numpy(),
        "glapan_relatif": (s - awas).to_numpy(),
        "tren_glapan_6j": (s - s.shift(6)).to_numpy(),
        "sumber": tma["sumber"].iloc[0],
        "status_data": tma["status_data"].iloc[0],
    })


def jalankan(anchor: bool = True, zona_harian: pd.DataFrame | None = None,
             path_interim: Path | None = None, path_fitur: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """Pipeline: TMA sintetis -> simpan interim -> fitur -> simpan processed.

    Kembali:
        (tabel fitur, laporan dari glapan_synth).
    """
    tma, laporan = glapan_synth.jalankan(zona_harian=zona_harian, anchor=anchor)
    simpan_csv(tma, path_interim or path_data("interim", "glapan_tma_synth.csv"))
    fitur = hitung_fitur(tma)
    simpan_csv(fitur, path_fitur or path_data("processed", "glapan_features.csv"))
    return fitur, laporan


def main(argv: list[str] | None = None) -> None:
    """CLI: PYTHONPATH=src python -m sigap_ka.features.glapan [--tanpa-anchor]"""
    ap = argparse.ArgumentParser(description="Fitur muka air Glapan (sintetis)")
    ap.add_argument("--tanpa-anchor", action="store_true")
    arg = ap.parse_args(argv)
    fitur, lap = jalankan(anchor=not arg.tanpa_anchor)
    print(f"glapan_features.csv: {len(fitur)} jam; faktor anchor {lap.get('faktor_anchor')}")
    if len(fitur):
        print(f"  TMA min {fitur['tma'].min():.0f}, maks {fitur['tma'].max():.0f}; "
              f"jam di atas Awas: {int((fitur['glapan_relatif'] > 0).sum())}")


if __name__ == "__main__":
    main()
