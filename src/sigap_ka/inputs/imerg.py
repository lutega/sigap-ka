"""
Tujuan      : Adapter hujan harian GPM IMERG (hasil sensing/hujan_gpm_imerg.py) ke skema standar
              paket ini, dipakai sebagai cadangan zona yang belum punya stasiun BMKG.
Lapis       : S (Sensing).
Sumber      : data/processed/hujan_gpm_imerg.csv (Giovanni; produk Late dan Final).
Masukan     : Produk ('gpm_imerg_late' atau 'gpm_imerg_final').
Keluaran    : Tabel berskema base.KOLOM_WAJIB (tanggal = hari UTC IMERG, zona lokal/hulu/Gundih),
              status_data = "nyata".
Keterbatasan: Satu sel grid 0,1 derajat per zona (bukan rerata daerah tangkapan). Hari IMERG adalah
              hari UTC (07.00-07.00 WIB); hari curah hujan BMKG biasanya diukur pukul 07.00 WIB
              untuk 24 jam sebelumnya, jadi tanggal BMKG D kira-kira setara hari IMERG D-1 (A-049).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sigap_ka.inputs.base import path_data, tabel_kosong, validasi

PETA_ZONA = {"lokal": "lokal_gubug_karangjati", "hulu": "hulu_tuntang", "gundih": "gundih",
             "semarang_pembanding": "semarang_pembanding"}  # sel stasiun BMKG Semarang (validasi saja)


def ambil(path: Path | None = None) -> pd.DataFrame:
    """Membaca data/processed/hujan_gpm_imerg.csv (kosong bila belum diunduh)."""
    path = path or path_data("processed", "hujan_gpm_imerg.csv")
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8", parse_dates=["waktu"])


def ke_format_standar(mentah: pd.DataFrame, produk: str = "gpm_imerg_late") -> pd.DataFrame:
    """Memilih satu produk dan mengubahnya ke skema standar (waktu 07.00 WIB -> tanggal hari UTC)."""
    if mentah.empty:
        return tabel_kosong()
    d = mentah[(mentah["sumber"] == produk) & (mentah["lokasi"].isin(PETA_ZONA))].copy()
    hasil = pd.DataFrame({
        "tanggal": (d["waktu"] - pd.Timedelta(hours=7)).dt.normalize(),
        "zona": d["lokasi"].map(PETA_ZONA),
        "nilai": d["nilai"].astype(float),
        "sumber": produk,
        "status_data": "nyata",
    }).sort_values(["zona", "tanggal"]).reset_index(drop=True)
    return validasi(hasil, PETA_ZONA.values())


def jalankan(produk: str = "gpm_imerg_late", path: Path | None = None) -> pd.DataFrame:
    """Pipeline ambil -> ke_format_standar."""
    return ke_format_standar(ambil(path), produk)
