"""
Tujuan      : Menyusun ringkasan evaluasi pada data nyata untuk API dan dasbor. Isinya: validasi IMERG
              terhadap BMKG, kejadian kandidat beserta hasil uji balik, kemampuan membedakan hari
              (AUC dan selang 95%), kepekaan bias, dan realisme generator.
Lapis       : Simulasi/evaluasi -> API (tab Data).
Sumber      : data/processed/uji_balik/{ringkasan.json, kepekaan_bias.csv, realisme_generator.csv,
              realisme_kelas_hujan.csv}, data/processed/validasi_imerg_bmkg.csv,
              data/manual/kejadian_kandidat.csv (lewat ringkasan_publik, tanpa tautan lengkap).
Masukan     : Berkas hasil di atas (dibuat simulation.uji_balik, simulation.realisme_generator,
              sigap_ka.features.validasi_imerg).
Keluaran    : dict siap JSON; bagian yang berkasnya belum ada berisi None, tidak galat.
Keterbatasan: Membaca berkas hasil, tidak menghitung ulang. Semua kejadian berstatus kandidat dan
              model dilatih pada data sintetis; teks batas klaim ikut disertakan.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from sensing.standar import dir_olahan
from sigap_ka.features import validasi_imerg
from sigap_ka.inputs import kejadian_kandidat

NAMA_SKOR = {
    "p_T-0": "Peluang SIGAP pada T-0",
    "p_T-24": "Peluang SIGAP pada T-24",
    "hujan_hulu_3h_tersedia": "Hujan hulu 3 hari yang tersedia (tanpa model)",
    "hujan_aktual_hulu_72j": "Hujan hulu 72 jam yang benar-benar turun (belum tersedia saat keputusan)",
    "hujan_aktual_lokal_72j": "Hujan lokal 72 jam yang benar-benar turun (belum tersedia saat keputusan)",
}
KOLOM_KANDIDAT = ["hujan_aktual_hulu_72j", "hujan_hulu_3h_tersedia", "p_T-24", "p_T-0", "p_maks", "tindakan_sigap"]
BATAS_KLAIM = [
    "Kejadian berasal dari berita publik dan berstatus kandidat; belum diverifikasi tim dan belum dipetakan ke E1-E6.",
    "Model lapis I dilatih pada episode sintetis, sehingga skala peluang belum terkalibrasi pada data nyata.",
    "Hari tanpa berita belum tentu tanpa gangguan; AUC hanya menggambarkan kemampuan membedakan hari.",
    "Peluang rendah tidak berarti jalur bebas risiko; status jalur tetap ditetapkan KAI.",
]


def _baca_json(path: Path) -> dict | None:
    """Membaca JSON bila ada (NaN diterima), selain itu None."""
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _baca_csv(path: Path) -> pd.DataFrame | None:
    """Membaca CSV bila ada, selain itu None."""
    return pd.read_csv(path) if path.exists() else None


def _validasi_imerg(folder: Path) -> dict | None:
    """Metrik IMERG Late/Final terhadap rerata stasiun BMKG Semarang dari tabel validasi bulanan."""
    t = _baca_csv(folder / "validasi_imerg_bmkg.csv")
    if t is None:
        return None
    hasil = {p: validasi_imerg.metrik(t, p) for p in validasi_imerg.PRODUK if p in t}
    stasiun = [c for c in t.columns if c.startswith("Stasiun")]
    if len(stasiun) == 2:
        hasil["antarstasiun"] = validasi_imerg.metrik(t, stasiun[0], stasiun[1])
    return hasil


def _pemisahan(isi: dict) -> list[dict]:
    """Daftar skor -> {skor, nama, auc, bawah, atas} dari blok pemisahan ringkasan uji balik."""
    keluar = []
    for k, v in (isi or {}).get("skor", {}).items():
        sel = v.get("auc_selang95") or [None, None]
        keluar.append({"skor": k, "nama": NAMA_SKOR.get(k, k), "auc": v.get("auc"), "bawah": sel[0], "atas": sel[1]})
    return keluar


def muat_ringkasan(folder: Path | None = None) -> dict:
    """Ringkasan evaluasi nyata (lihat docstring modul). Bagian tanpa berkas = None."""
    folder = folder or dir_olahan()
    ub = _baca_json(folder / "uji_balik" / "ringkasan.json")
    kandidat = [dict(r) for r in kejadian_kandidat.ringkasan_publik()]
    pemisahan, info_sumber = {}, {}
    if ub:
        for nama, isi in ub.get("per_sumber", {}).items():
            info_sumber[nama] = {"nama": isi.get("nama", nama), "catatan": isi.get("catatan"),
                                 "muka_air": isi.get("muka_air")}
            per_id = {r["id_kandidat"]: r for r in isi.get("kandidat", [])}
            for r in kandidat:
                hasil = per_id.get(r["id_kandidat"], {})
                r[nama] = {k: hasil.get(k) for k in KOLOM_KANDIDAT}
            if "pemisahan" in isi:
                p = isi["pemisahan"]
                pemisahan[nama] = {
                    "n_kejadian": p.get("n_kejadian"), "n_lain": p.get("n_lain"), "skor": _pemisahan(p),
                    "ambang": {k: v for k, v in p.get("skor", {}).get("p_T-0", {}).items() if k.startswith("ambang_")},
                    "pembanding": {k.removeprefix("pemisahan_"): _pemisahan(v) for k, v in isi.items()
                                   if k.startswith("pemisahan_")},
                }
    kb = _baca_csv(folder / "uji_balik" / "kepekaan_bias.csv")
    kepekaan = None
    if kb is not None and len(kb):
        kepekaan = {"skala": sorted(kb["skala_hujan"].unique().tolist()),
                    "baris": [{"id_kandidat": i, **{str(r["skala_hujan"]): {"p_T-0": r["p_T-0"], "tindakan": r["tindakan_sigap"]}
                                                     for _, r in g.iterrows()}}
                              for i, g in kb.groupby("id_kandidat")]}
    rk = _baca_csv(folder / "uji_balik" / "realisme_generator.csv")
    kelas = _baca_csv(folder / "uji_balik" / "realisme_kelas_hujan.csv")
    realisme = None
    if rk is not None:
        median = rk.pivot_table(index="besaran", columns="kelompok", values="q50").reset_index()
        realisme = {"median": median.to_dict("records"),
                    "kelas_hujan": kelas.to_dict("records") if kelas is not None else []}
    return {
        "status": "kandidat; model dilatih pada data sintetis; bukan validasi resmi",
        "dibuat": ub.get("dibuat") if ub else None,
        "preset": ub.get("preset") if ub else None,
        "prakiraan_utama": ub.get("prakiraan_utama") if ub else None,
        "sumber_utama": ub.get("sumber_utama") if ub else None,
        "sumber": info_sumber,
        "validasi_imerg": _validasi_imerg(folder),
        "kandidat": kandidat,
        "pemisahan": pemisahan,
        "kepekaan_bias": kepekaan,
        "realisme": realisme,
        "batas_klaim": BATAS_KLAIM,
    }
