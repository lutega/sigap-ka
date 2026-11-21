"""
Tujuan      : Membandingkan episode sintetis generator dummy (dasar pelatihan lapis I) dengan hujan
              nyata IMERG Late dan kejadian kandidat. Dibandingkan sebaran hujan 72 jam, fitur yang
              tersedia pada T-0, muka air sintetis, dan frekuensi gangguan per kelas hujan.
Lapis       : Simulasi/evaluasi (pemeriksaan asumsi generator A-010, A-021).
Sumber      : sensing/dummy_generator.py (episode latih, seed inferensi.latih);
              data/processed/uji_balik/pindai_harian.csv (keluaran simulation/uji_balik.py).
Masukan     : Preset, jumlah episode latih, tabel pindai harian.
Keluaran    : data/processed/uji_balik/realisme_generator.csv (kuantil) dan realisme_kelas_hujan.csv
              (frekuensi gangguan per kelas hujan hulu 72 jam), serta ringkasan dict.
Keterbatasan: Satuan berbeda: episode sintetis adalah satu kejadian hujan lebat, sedangkan data
              nyata adalah hari. Frekuensi nyata per kelas memakai 8 hari kejadian kandidat sehingga
              sangat kasar. IMERG 0,1 derajat cenderung meratakan puncak hujan titik.
"""

from __future__ import annotations

import argparse
import warnings

import numpy as np
import pandas as pd

from config import ParamsAktif, muat_params
from inference.fitur import IndeksEpisode
from sensing import dummy_generator
from sensing.standar import dir_olahan
from simulation.episode import dari_sintetis

KUANTIL = (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)
KELAS_HULU = (0, 20, 40, 60, 80, 100, np.inf)
KOLOM_BANDING = {"hulu_72j": "hujan_aktual_hulu_72j", "lokal_72j": "hujan_aktual_lokal_72j",
                 "hulu_3h_tersedia": "hujan_hulu_3h_tersedia", "lokal_3h_tersedia": "hujan_lokal_3h_tersedia",
                 "glapan_relatif_T0": "glapan_relatif_T0"}


def ringkas_sintetis(n: int | None = None, seed: int | None = None, params: ParamsAktif | None = None) -> pd.DataFrame:
    """Satu baris per episode sintetis: hujan 72 jam sebelum T-0, fitur tersedia pada T-0, kebenaran.

    Bawaan n dan seed = episode latih lapis I (inferensi.latih), agar yang dibandingkan adalah data
    yang benar-benar dipakai melatih model.
    """
    params = params or muat_params()
    latih = params.inferensi["latih"]
    n = int(n or latih["jumlah_episode"])
    seed = int(latih["offset_seed"] if seed is None else seed)
    baris = []
    for e in dummy_generator.ambil(n, seed, params.preset, awalan="REAL"):
        h = e.hujan
        jam = ((h["waktu"] - pd.Timestamp(e.t0)) / pd.Timedelta(hours=1)).to_numpy()
        f = IndeksEpisode(dari_sintetis(e), params).fitur_mentah(0.0)

        def jumlah(lok: str) -> float:
            pilih = (h["lokasi"] == lok).to_numpy() & (jam >= -72) & (jam < 0)
            return float(h.loc[pilih, "nilai"].sum())

        baris.append({"hulu_72j": jumlah("hulu"), "lokal_72j": jumlah("lokal"),
                      "hulu_3h_tersedia": f["hujan_hulu_3h"], "lokal_3h_tersedia": f["hujan_lokal_3h"],
                      "glapan_relatif_T0": f["glapan_relatif"],
                      "terganggu": bool(e.kebenaran["terganggu"]), "mekanisme": e.kebenaran["mekanisme"]})
    return pd.DataFrame(baris)


def tabel_kuantil(sintetis: pd.DataFrame, pindai: pd.DataFrame) -> pd.DataFrame:
    """Kuantil tiap besaran untuk: episode sintetis, semua hari nyata, dan hari kejadian kandidat.

    Juga kolom 'persentil_nyata_median_sintetis': persentil median sintetis di antara semua hari nyata.
    """
    baris = []
    for nama, kolom_nyata in KOLOM_BANDING.items():
        semua = pindai[kolom_nyata].dropna().to_numpy(dtype=float)
        kej = pindai.loc[pindai["label"] == "kejadian", kolom_nyata].dropna().to_numpy(dtype=float)
        sin = sintetis[nama].to_numpy(dtype=float)
        for kelompok, nilai in (("sintetis_latih", sin), ("nyata_semua_hari", semua), ("nyata_hari_kejadian", kej)):
            r = {"besaran": nama, "kelompok": kelompok, "n": int(len(nilai))}
            r.update({f"q{int(q * 100)}": (round(float(np.quantile(nilai, q)), 1) if len(nilai) else None)
                      for q in KUANTIL})
            baris.append(r)
        baris[-3]["persentil_nyata_median_sintetis"] = round(float((semua < np.median(sin)).mean() * 100), 1)
    return pd.DataFrame(baris)


def tabel_kelas_hujan(sintetis: pd.DataFrame, pindai: pd.DataFrame) -> pd.DataFrame:
    """Frekuensi gangguan per kelas hujan hulu 72 jam: generator (per episode) vs nyata (per hari).

    Hari 'sekitar' kejadian dibuang dari data nyata (lihat uji_balik.pindai_harian).
    """
    nyata = pindai[pindai["label"] != "sekitar"]
    k_sin = pd.cut(sintetis["hulu_72j"], KELAS_HULU, right=False)
    k_nya = pd.cut(nyata["hujan_aktual_hulu_72j"], KELAS_HULU, right=False)
    s = sintetis.groupby(k_sin, observed=False)["terganggu"].agg(n_sintetis="size", porsi_terganggu_sintetis="mean")
    r = nyata.groupby(k_nya, observed=False)["label"].agg(
        n_hari_nyata="size", hari_kejadian=lambda x: int((x == "kejadian").sum()))
    t = s.join(r)
    t["porsi_hari_kejadian_nyata"] = t["hari_kejadian"] / t["n_hari_nyata"].where(t["n_hari_nyata"] > 0)
    t.index = [f"{int(i.left)}-{'' if np.isinf(i.right) else int(i.right)} mm" for i in t.index]
    t.index.name = "hujan_hulu_72j"
    return t.round(3).reset_index()


def jalankan(params: ParamsAktif | None = None, path_pindai=None) -> dict:
    """Pipeline: episode latih sintetis + pindai harian nyata -> dua tabel -> simpan -> ringkasan."""
    params = params or muat_params()
    folder = dir_olahan() / "uji_balik"
    pindai = pd.read_csv(path_pindai or folder / "pindai_harian.csv")
    sintetis = ringkas_sintetis(params=params)
    kuantil = tabel_kuantil(sintetis, pindai)
    kelas = tabel_kelas_hujan(sintetis, pindai)
    folder.mkdir(parents=True, exist_ok=True)
    kuantil.to_csv(folder / "realisme_generator.csv", index=False, lineterminator="\n")
    kelas.to_csv(folder / "realisme_kelas_hujan.csv", index=False, lineterminator="\n")
    med = kuantil[(kuantil["besaran"] == "hulu_72j") & (kuantil["kelompok"] == "sintetis_latih")].iloc[0]
    return {"porsi_terganggu_sintetis": round(float(sintetis["terganggu"].mean()), 3),
            "median_hulu_72j_sintetis": med["q50"],
            "persentil_nyata_median_sintetis": med["persentil_nyata_median_sintetis"],
            "kuantil": kuantil, "kelas_hujan": kelas}


def main(argv: list[str] | None = None) -> None:
    """CLI: python -m simulation.realisme_generator (jalankan simulation.uji_balik lebih dulu)."""
    argparse.ArgumentParser(description="Pemeriksaan realisme generator dummy terhadap IMERG Late").parse_args(argv)
    warnings.filterwarnings("ignore", message="The 'generic' unit for NumPy timedelta is deprecated")
    r = jalankan()
    print(f"porsi episode sintetis terganggu: {r['porsi_terganggu_sintetis']}; median hulu 72 j sintetis "
          f"{r['median_hulu_72j_sintetis']} mm = persentil {r['persentil_nyata_median_sintetis']} hari nyata")
    print(r["kuantil"].to_string(index=False))
    print(r["kelas_hujan"].to_string(index=False))


if __name__ == "__main__":
    main()
