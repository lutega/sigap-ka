"""
Tujuan      : Menghitung fitur hujan harian per zona: hujan_lokal_1d/3d/5d, hujan_hulu_3d,
              hujan_gundih_1d/3d, dari stasiun BMKG bila ada dan IMERG Late sebagai cadangan.
Lapis       : Penyiapan fitur lapis I (tabel harian untuk analisis dan kalibrasi).
Sumber      : data/interim/bmkg_clean.csv (inputs/bmkg.py), data/processed/hujan_gpm_imerg.csv
              (inputs/imerg.py); urutan prioritas sumber di params.json (fitur_hujan.urutan_sumber).
Masukan     : Tabel berskema standar per zona.
Keluaran    : data/processed/hujan_features.csv: satu baris per tanggal, kolom fitur (mm) dan
              sumber yang dipakai tiap zona.
Keterbatasan: Akumulasi berjendela memakai min_periods = panjang jendela: bila ada hari kosong di
              jendela, fitur NaN (tidak diisi tebakan). Beberapa stasiun dalam satu zona dirata-rata.
              Ini tabel harian; model pada jam keputusan tetap memakai inference/fitur.py yang
              memperhitungkan latensi tiap sumber.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from config import muat_params
from sigap_ka.inputs import bmkg, imerg
from sigap_ka.inputs.base import ZONA_HUJAN, baca_csv, path_data, simpan_csv, validasi

FITUR = {
    "hujan_lokal_1d": ("lokal_gubug_karangjati", 1),
    "hujan_lokal_3d": ("lokal_gubug_karangjati", 3),
    "hujan_lokal_5d": ("lokal_gubug_karangjati", 5),
    "hujan_hulu_3d": ("hulu_tuntang", 3),
    "hujan_gundih_1d": ("gundih", 1),
    "hujan_gundih_3d": ("gundih", 3),
}
KOLOM_SUMBER = {"lokal_gubug_karangjati": "sumber_lokal", "hulu_tuntang": "sumber_hulu", "gundih": "sumber_gundih"}


def _per_zona(df: pd.DataFrame) -> pd.DataFrame:
    """Rerata harian per zona (beberapa stasiun dalam satu zona dirata-rata; NaN diabaikan)."""
    if df.empty:
        return pd.DataFrame(columns=["tanggal", "zona", "nilai", "sumber", "status_data"])
    g = df[df["zona"].isin(ZONA_HUJAN)].groupby(["tanggal", "zona"], as_index=False)
    return g.agg(nilai=("nilai", "mean"), sumber=("sumber", "first"), status_data=("status_data", "first"))


def hujan_zona_harian(sumber_data: dict[str, pd.DataFrame] | None = None,
                      urutan: list[str] | None = None) -> pd.DataFrame:
    """Seri hujan harian tiap zona dengan sumber berprioritas.

    Untuk setiap (tanggal, zona) dipakai nilai terisi dari sumber pertama dalam urutan; bila
    kosong, sumber berikutnya. Sumber yang dipakai tercatat di kolom sumber.
    Parameter:
        sumber_data: {'bmkg': tabel, 'gpm_imerg_late': tabel}; bawaan dibaca dari berkas.
        urutan: prioritas sumber; bawaan params.json fitur_hujan.urutan_sumber.
    Kembali:
        Tabel berskema standar (zona lokal/hulu/Gundih).
    """
    urutan = urutan or muat_params().mentah["fitur_hujan"]["urutan_sumber"]
    if sumber_data is None:
        p = path_data("interim", "bmkg_clean.csv")
        sumber_data = {"bmkg": baca_csv(p) if p.exists() else pd.DataFrame(),
                       "gpm_imerg_late": imerg.jalankan("gpm_imerg_late")}
    hasil = None
    for nama in urutan:
        bagian = _per_zona(sumber_data.get(nama, pd.DataFrame()))
        bagian = bagian[bagian["nilai"].notna()]
        if bagian.empty:
            continue
        if hasil is None:
            hasil = bagian
            continue
        kunci = set(zip(hasil["tanggal"], hasil["zona"]))
        tambah = bagian[[(t, z) not in kunci for t, z in zip(bagian["tanggal"], bagian["zona"])]]
        if not tambah.empty:
            hasil = pd.concat([hasil, tambah], ignore_index=True)
    if hasil is None or hasil.empty:
        return pd.DataFrame(columns=["tanggal", "zona", "nilai", "sumber", "status_data"])
    hasil["tanggal"] = pd.to_datetime(hasil["tanggal"])
    hasil = hasil.sort_values(["zona", "tanggal"]).reset_index(drop=True)
    return validasi(hasil, ZONA_HUJAN)


def hitung_fitur(zona_harian: pd.DataFrame) -> pd.DataFrame:
    """Akumulasi berjendela per tanggal (indeks harian kontinu; hari tanpa data = NaN).

    Kembali:
        DataFrame kolom tanggal, fitur FITUR, dan sumber_lokal/sumber_hulu/sumber_gundih.
    """
    if zona_harian.empty:
        return pd.DataFrame(columns=["tanggal"] + list(FITUR) + list(KOLOM_SUMBER.values()))
    awal, akhir = zona_harian["tanggal"].min(), zona_harian["tanggal"].max()
    indeks = pd.date_range(awal, akhir, freq="D")
    tabel = pd.DataFrame({"tanggal": indeks})
    for zona, kol in KOLOM_SUMBER.items():
        z = zona_harian[zona_harian["zona"] == zona].set_index("tanggal")
        nilai = z["nilai"].reindex(indeks)
        for fitur, (zf, hari) in FITUR.items():
            if zf == zona:
                tabel[fitur] = nilai.rolling(hari, min_periods=hari).sum().to_numpy()
        tabel[kol] = z["sumber"].reindex(indeks).to_numpy()
    return tabel[["tanggal"] + list(FITUR) + list(KOLOM_SUMBER.values())]


def jalankan(path_keluar: Path | None = None, sumber_data: dict | None = None) -> pd.DataFrame:
    """Pipeline: seri zona berprioritas -> fitur -> simpan data/processed/hujan_features.csv."""
    fitur = hitung_fitur(hujan_zona_harian(sumber_data))
    simpan_csv(fitur, path_keluar or path_data("processed", "hujan_features.csv"))
    return fitur


def main(argv: list[str] | None = None) -> None:
    """CLI: PYTHONPATH=src python -m sigap_ka.features.hujan [--dengan-bmkg]"""
    ap = argparse.ArgumentParser(description="Fitur hujan harian per zona")
    ap.add_argument("--dengan-bmkg", action="store_true", help="jalankan pembersihan BMKG lebih dulu")
    arg = ap.parse_args(argv)
    if arg.dengan_bmkg:
        bmkg.jalankan()
    fitur = jalankan()
    print(f"hujan_features.csv: {len(fitur)} hari")
    for kol in KOLOM_SUMBER.values():
        if kol in fitur and len(fitur):
            print(f"  {kol}: {fitur[kol].value_counts(dropna=False).to_dict()}")


if __name__ == "__main__":
    main()
