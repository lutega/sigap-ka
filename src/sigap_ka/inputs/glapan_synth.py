"""
Tujuan      : Estimasi/sintesis seri TMA (tinggi muka air) Bendung Glapan per jam dari hujan hulu DAS
              Tuntang dan hujan lokal, sebagai pengisi sementara sampai data resmi BBWS tersedia.
Lapis       : S (Sensing), sintetis berlabel.
Sumber      : Hujan harian per zona (features/hujan.hujan_zona_harian: BMKG atau IMERG Late);
              titik TMA nyata untuk anchoring dari data/processed/muka_air_glapan.csv (rilis BNPB);
              parameter di params.json muka_air.glapan_api dan ambang Awas muka_air.ambang_awas.
Masukan     : Seri hujan harian zona hulu_tuntang dan lokal_gubug_karangjati.
Keluaran    : Tabel berskema base.KOLOM_WAJIB per jam: zona 'glapan', nilai TMA (cm, asumsi satuan
              rilis BNPB), sumber 'glapan_api_synth', status_data 'sintetis', ditambah komponen
              tampungan dan faktor anchoring.
Keterbatasan: Model konseptual (bukan kalibrasi hidrologi): dua waduk linear, yaitu aliran dasar
              lambat ala Antecedent Precipitation Index (API) dan lonjakan banjir cepat dari hujan di
              atas ambang, keduanya meluruh eksponensial. Hujan harian dibagi rata per jam. Anchoring
              memakai titik nyata yang jamnya tidak diketahui sehingga dicocokkan dengan maksimum
              harian; titik yang dipakai untuk anchoring tidak bisa sekaligus dipakai menguji model.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config import muat_params
from sensing.muka_air_sintetis import hitung_tampungan
from sigap_ka.inputs.base import path_data, tabel_kosong, validasi

SUMBER = "glapan_api_synth"
ZONA = "glapan"


def parameter() -> dict:
    """Parameter model dari params.json (muka_air.glapan_api)."""
    return muat_params().muka_air["glapan_api"]


def hujan_per_jam(zona_harian: pd.DataFrame, zona: str, indeks_jam: pd.DatetimeIndex) -> tuple[np.ndarray, int]:
    """Hujan per jam (mm/jam) satu zona: total harian dibagi rata ke 24 jam tanggal itu.

    Kembali:
        (larik hujan per jam sepanjang indeks_jam, jumlah hari tanpa data yang dianggap 0).
    """
    z = zona_harian[zona_harian["zona"] == zona].set_index("tanggal")["nilai"]
    hari = indeks_jam.normalize()
    harian = z.reindex(pd.DatetimeIndex(hari.unique()))
    kosong = int(harian.isna().sum())
    per_hari = (harian.fillna(0.0) / 24.0).reindex(hari).to_numpy()  # A-050: hari kosong dianggap 0
    return per_hari, kosong


def simulasi(hulu_jam: np.ndarray, lokal_jam: np.ndarray, p: dict | None = None) -> dict[str, np.ndarray]:
    """Dua waduk linear per jam.

    masukan  = bobot_hulu * hujan_hulu + bobot_lokal * hujan_lokal          (mm/jam)
    S_lambat : dS/dt = masukan - S/k_lambat                                  (aliran dasar, ala API)
    S_cepat  : dS/dt = maks(0, masukan - ambang/24) - S/k_cepat              (lonjakan banjir)
    TMA      = dasar + a_lambat * S_lambat^b + a_cepat * S_cepat^b           (cm)
    Kembali:
        dict s_lambat, s_cepat, tma (larik sepanjang masukan).
    """
    p = p or parameter()
    masukan = p["bobot_hulu"] * np.asarray(hulu_jam) + p["bobot_lokal"] * np.asarray(lokal_jam)
    lebih = np.maximum(0.0, masukan - p["ambang_lonjakan_mm_hari"] / 24.0)
    s_lambat = hitung_tampungan(masukan, p["k_lambat_jam"], p["tampungan_lambat_awal_mm"])
    s_cepat = hitung_tampungan(lebih, p["k_cepat_jam"], 0.0)
    b = p["pangkat"]
    tma = p["elevasi_dasar"] + p["pengali_lambat"] * s_lambat ** b + p["pengali_cepat"] * s_cepat ** b
    return {"s_lambat": s_lambat, "s_cepat": s_cepat, "tma": tma}


def titik_anchor(path: Path | None = None) -> pd.DataFrame:
    """Titik TMA nyata (rilis BNPB) untuk anchoring: kolom tanggal (hari) dan nilai."""
    path = path or path_data("processed", "muka_air_glapan.csv")
    if not path.exists():
        return pd.DataFrame(columns=["tanggal", "nilai"])
    d = pd.read_csv(path, encoding="utf-8", parse_dates=["waktu"])
    d = d[d["lokasi"] == "glapan"]
    nyata = d["is_simulated"].astype(str).str.lower().isin(["false", "0"])
    return pd.DataFrame({"tanggal": d.loc[nyata, "waktu"].dt.normalize(), "nilai": d.loc[nyata, "nilai"].astype(float)})


def faktor_anchor(indeks_jam: pd.DatetimeIndex, tma: np.ndarray, anchor: pd.DataFrame,
                  p: dict | None = None) -> tuple[float, list[dict]]:
    """Faktor skala kenaikan TMA agar maksimum harian model sama dengan titik nyata.

    f_i = (TMA_nyata - dasar) / (maks harian model - dasar); f = median(f_i), dibatasi
    [faktor_anchor_min, faktor_anchor_maks]. Titik di luar rentang seri dilewati.
    Kembali:
        (faktor, rincian per titik).
    """
    p = p or parameter()
    dasar = p["elevasi_dasar"]
    seri = pd.Series(tma, index=indeks_jam)
    rincian, faktor = [], []
    for _, r in anchor.iterrows():
        hari = seri[seri.index.normalize() == r["tanggal"]]
        if hari.empty:
            rincian.append({"tanggal": r["tanggal"], "nyata": r["nilai"], "model": None, "dipakai": False})
            continue
        model = float(hari.max())
        f = (r["nilai"] - dasar) / (model - dasar) if model > dasar else None
        rincian.append({"tanggal": r["tanggal"], "nyata": float(r["nilai"]), "model": model, "faktor": f,
                        "dipakai": f is not None})
        if f is not None:
            faktor.append(f)
    if not faktor:
        return 1.0, rincian
    f = float(np.clip(np.median(faktor), p["faktor_anchor_min"], p["faktor_anchor_maks"]))
    return f, rincian


def ke_format_standar(indeks_jam: pd.DatetimeIndex, sim: dict, faktor: float, p: dict | None = None) -> pd.DataFrame:
    """Seri hasil simulasi (setelah anchoring) ke skema standar."""
    p = p or parameter()
    dasar = p["elevasi_dasar"]
    df = pd.DataFrame({
        "tanggal": indeks_jam,
        "zona": ZONA,
        "nilai": dasar + faktor * (sim["tma"] - dasar),
        "sumber": SUMBER,
        "status_data": "sintetis",
        "tampungan_lambat_mm": sim["s_lambat"],
        "tampungan_cepat_mm": sim["s_cepat"],
        "faktor_anchor": faktor,
    })
    return validasi(df, [ZONA])


def jalankan(zona_harian: pd.DataFrame | None = None, anchor: bool = True,
             path_anchor: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """Pipeline: hujan zona -> hujan per jam -> simulasi -> anchoring (opsional) -> skema standar.

    Parameter:
        zona_harian: seri hujan harian per zona; bawaan features.hujan.hujan_zona_harian().
        anchor: cocokkan ke titik TMA nyata bila ada.
    Kembali:
        (seri TMA per jam, laporan {faktor_anchor, rincian_anchor, hari_hujan_kosong, sumber_hujan}).
    """
    if zona_harian is None:
        from sigap_ka.features.hujan import hujan_zona_harian
        zona_harian = hujan_zona_harian()
    hulu = zona_harian[zona_harian["zona"] == "hulu_tuntang"]
    if hulu.empty:
        return tabel_kosong(), {"faktor_anchor": None, "pesan": "tidak ada hujan hulu Tuntang"}
    awal, akhir = pd.Timestamp(hulu["tanggal"].min()), pd.Timestamp(hulu["tanggal"].max())
    jumlah_jam = int((akhir - awal) / pd.Timedelta(hours=1)) + 24
    indeks = pd.date_range(start=awal, periods=jumlah_jam, freq="h")
    hulu_jam, kosong_hulu = hujan_per_jam(zona_harian, "hulu_tuntang", indeks)
    lokal_jam, kosong_lokal = hujan_per_jam(zona_harian, "lokal_gubug_karangjati", indeks)
    p = parameter()
    sim = simulasi(hulu_jam, lokal_jam, p)
    faktor, rincian = 1.0, []
    if anchor:
        faktor, rincian = faktor_anchor(indeks, sim["tma"], titik_anchor(path_anchor), p)
    hasil = ke_format_standar(indeks, sim, faktor, p)
    for r in rincian:  # nilai model setelah anchoring untuk laporan
        if r.get("model") is not None:
            r["model_setelah"] = p["elevasi_dasar"] + faktor * (r["model"] - p["elevasi_dasar"])
    return hasil, {
        "faktor_anchor": faktor, "rincian_anchor": rincian,
        "hari_hujan_kosong": {"hulu_tuntang": kosong_hulu, "lokal_gubug_karangjati": kosong_lokal},
        "sumber_hujan": sorted(zona_harian["sumber"].unique().tolist()),
    }


def main(argv: list[str] | None = None) -> None:
    """CLI: PYTHONPATH=src python -m sigap_ka.inputs.glapan_synth [--tanpa-anchor]"""
    ap = argparse.ArgumentParser(description="Estimasi TMA Glapan sintetis (API/waduk linear)")
    ap.add_argument("--tanpa-anchor", action="store_true")
    arg = ap.parse_args(argv)
    hasil, lap = jalankan(anchor=not arg.tanpa_anchor)
    print(f"TMA sintetis: {len(hasil)} jam; faktor anchor {lap['faktor_anchor']}; sumber hujan {lap.get('sumber_hujan')}")
    for r in lap.get("rincian_anchor", []):
        print(f"  anchor {str(r['tanggal'])[:10]}: nyata {r['nyata']}, model {r.get('model')}, setelah {r.get('model_setelah')}")


if __name__ == "__main__":
    main()
