"""
Tujuan      : Uji balik (backtest) lapis I-G pada hujan nyata IMERG Late terhadap katalog kejadian
              kandidat; uji kepekaan bias hujan satelit; dan pemindaian harian 2024-2026 untuk melihat
              apakah peluang pada hari kejadian lebih tinggi daripada hari lain.
Lapis       : Simulasi/evaluasi (melintasi S-I-G).
Sumber      : data/processed/hujan_gpm_imerg.csv (IMERG Late), data/manual/kejadian_kandidat.csv,
              model lapis I bawaan (dilatih pada episode sintetis), kurva pemicu lapis G.
Masukan     : Blok uji_balik di config/params.json.
Keluaran    : data/processed/uji_balik/kandidat.csv, kepekaan_bias.csv, pindai_harian.csv, ringkasan.json.
Keterbatasan: Kejadian berstatus kandidat dari berita (A-055), dan hari tanpa berita belum tentu tanpa
              gangguan. Model dilatih pada data sintetis (A-026) sehingga skala peluang mencerminkan
              generator. Muka air per jam sintetis. Hujan harian IMERG Late baru tersedia 14-38 jam
              setelah turun, sehingga hujan beberapa jam terakhir sebelum kejadian belum terlihat
              model (A-057).
"""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from config import ParamsAktif, muat_params
from inference.estimasi import Estimator
from inference.fitur import IndeksEpisode
from sensing.standar import dir_olahan
from sigap_ka.inputs import kejadian_kandidat
from simulation import kebijakan
from simulation.episode import bangun_episode_hujan_nyata, muat_hujan_imerg_late


# ---------------------------------------------------------------- bantu

def hujan_aktual(hujan: pd.DataFrame, lokasi: str, t0: datetime, jam: int = 72) -> float:
    """Hujan yang BENAR-BENAR turun dalam `jam` jam sebelum T-0 (tanpa memandang latensi; untuk diagnosis).

    Baris harian dihitung proporsional terhadap bagian periodenya yang jatuh dalam jendela.
    """
    d = hujan[hujan["lokasi"] == lokasi]
    if d.empty:
        return float("nan")
    awal = d["waktu"].to_numpy(dtype="datetime64[ns]")
    res = d["resolusi_jam"].to_numpy(dtype=float) if "resolusi_jam" in d else np.full(len(d), 24.0)
    akhir = awal + (res * 3600).astype("timedelta64[s]")
    ujung = np.datetime64(pd.Timestamp(t0).to_datetime64(), "ns")
    pangkal = ujung - np.timedelta64(int(jam * 3600), "s")
    tumpang = (np.minimum(akhir, ujung) - np.maximum(awal, pangkal)) / np.timedelta64(1, "h")
    porsi = np.clip(tumpang, 0, None) / res
    return float(np.nansum(d["nilai"].to_numpy(dtype=float) * porsi))


def cakupan_data(hujan: pd.DataFrame, t0: datetime, params: ParamsAktif) -> float:
    """Porsi hari berdata (minimum lokal dan hulu) dalam jendela antesedent + horizon sebelum T-0."""
    ep = params.episode
    mulai = (pd.Timestamp(t0) - pd.Timedelta(hours=ep.horizon_jam + ep.antesedent_hari * 24)).normalize()
    hari = pd.date_range(mulai, pd.Timestamp(t0).normalize() - pd.Timedelta(days=1), freq="D")
    if not len(hari):
        return 0.0
    porsi = []
    for lok in ("lokal", "hulu"):
        ada = set(hujan.loc[hujan["lokasi"] == lok, "waktu"].dt.normalize())
        porsi.append(sum(h in ada for h in hari) / len(hari))
    return float(min(porsi))


def _teks_tindakan(rencana: dict[str, int | None], params: ParamsAktif) -> str:
    """Rencana SIGAP {id: langkah} menjadi teks 'T1@T-42; T6@T-18' berurutan waktu."""
    ep = params.episode
    isi = sorted((k, tid) for tid, k in rencana.items() if k is not None)
    return "; ".join(f"{tid}@T-{ep.jam_sebelum_t0(k)}" for k, tid in isi)


def evaluasi_episode(ep, estimator: Estimator, params: ParamsAktif) -> dict:
    """Peluang pada jam-jam yang dilaporkan, peluang maksimum, fitur pada T-0, dan rencana SIGAP."""
    lin = estimator.lintasan(ep)
    rencana = kebijakan.sigap(lin, None, params)
    fitur = IndeksEpisode(ep, params).fitur_mentah(0.0)
    hasil = {f"p_T-{j}": round(float(lin["peluang"][params.episode.langkah_dari_jam(j)]), 4)
             for j in params.uji_balik["jam_dilaporkan"]}
    hasil["p_maks"] = round(float(lin["peluang"].max()), 4)
    hasil.update({
        "hujan_lokal_1h_tersedia": round(fitur["hujan_lokal_1h"], 1),
        "hujan_lokal_3h_tersedia": round(fitur["hujan_lokal_3h"], 1),
        "hujan_hulu_3h_tersedia": round(fitur["hujan_hulu_3h"], 1),
        "glapan_relatif_T0": round(fitur["glapan_relatif"], 1),
        "jumlah_tindakan": sum(k is not None for k in rencana.values()),
        "tindakan_sigap": _teks_tindakan(rencana, params),
    })
    return hasil


# ---------------------------------------------------------------- uji balik kandidat

def uji_balik_kandidat(params: ParamsAktif | None = None, estimator: Estimator | None = None,
                       hujan: pd.DataFrame | None = None, kandidat: pd.DataFrame | None = None,
                       varian: list[str] | None = None) -> pd.DataFrame:
    """Uji balik setiap kandidat untuk tiap varian prakiraan.

    Kembali:
        Satu baris per (kandidat, varian): T-0, cakupan data, hujan aktual 72 jam (lokal, hulu),
        peluang T-48..T-0, fitur tersedia pada T-0, dan rencana SIGAP.
    """
    params = params or muat_params()
    estimator = estimator or Estimator(params=params)
    hujan = muat_hujan_imerg_late() if hujan is None else hujan
    kandidat = kejadian_kandidat.tabel_t0() if kandidat is None else kandidat
    varian = varian or params.uji_balik["varian_prakiraan"]
    baris = []
    for _, k in kandidat.iterrows():
        t0 = pd.Timestamp(k["t0"]).to_pydatetime()
        cak = cakupan_data(hujan, t0, params)
        dasar = {"id_kandidat": k["id_kandidat"], "t0": t0.isoformat(timespec="minutes"),
                 "jam_diketahui": bool(k["jam_diketahui"]), "jenis_gangguan": k["jenis_gangguan"],
                 "mekanisme": k["mekanisme"], "cakupan_data": round(cak, 2),
                 "hujan_aktual_lokal_72j": round(hujan_aktual(hujan, "lokal", t0), 1),
                 "hujan_aktual_hulu_72j": round(hujan_aktual(hujan, "hulu", t0), 1)}
        for mode in varian:
            if cak < 0.8:
                baris.append({**dasar, "prakiraan": mode, "catatan": "data hujan kurang dari 80% jendela"})
                continue
            ep = bangun_episode_hujan_nyata(t0, f"UB-{k['id_kandidat']}", f"Uji balik {k['id_kandidat']}", params,
                                            hujan_harian=hujan, prakiraan=mode)
            baris.append({**dasar, "prakiraan": mode, **evaluasi_episode(ep, estimator, params), "catatan": ""})
    return pd.DataFrame(baris)


def kepekaan_bias(params: ParamsAktif | None = None, estimator: Estimator | None = None,
                  hujan: pd.DataFrame | None = None, kandidat: pd.DataFrame | None = None,
                  skala: list[float] | None = None, prakiraan: str | None = None) -> pd.DataFrame:
    """Peluang dan rencana SIGAP tiap kandidat bila seluruh hujan IMERG dikalikan faktor skala.

    Skala < 1 meniru koreksi bias IMERG Late yang lebih tinggi dari penakar (A-054).
    """
    params = params or muat_params()
    estimator = estimator or Estimator(params=params)
    hujan = muat_hujan_imerg_late() if hujan is None else hujan
    kandidat = kejadian_kandidat.tabel_t0() if kandidat is None else kandidat
    skala = skala or params.uji_balik["skala_bias"]
    prakiraan = prakiraan or params.uji_balik["prakiraan_utama"]
    baris = []
    for _, k in kandidat.iterrows():
        t0 = pd.Timestamp(k["t0"]).to_pydatetime()
        if cakupan_data(hujan, t0, params) < 0.8:
            continue
        for f in skala:
            ep = bangun_episode_hujan_nyata(t0, f"UB-{k['id_kandidat']}", "kepekaan bias", params,
                                            hujan_harian=hujan, skala_hujan=f, prakiraan=prakiraan)
            baris.append({"id_kandidat": k["id_kandidat"], "t0": t0.isoformat(timespec="minutes"),
                          "skala_hujan": f, "prakiraan": prakiraan, **evaluasi_episode(ep, estimator, params)})
    return pd.DataFrame(baris)


# ---------------------------------------------------------------- pemindaian harian

def pindai_harian(params: ParamsAktif | None = None, estimator: Estimator | None = None,
                  hujan: pd.DataFrame | None = None, kandidat: pd.DataFrame | None = None,
                  prakiraan: str | None = None, mulai: str | None = None, selesai: str | None = None) -> pd.DataFrame:
    """Peluang harian (T-0 = tanggal + jam_pindai) sepanjang cakupan IMERG Late.

    Label: 'kejadian' bila ada kandidat bertanggal sama; 'sekitar' bila dalam jeda_hari_kontrol hari
    dari kandidat (gangguan sering berlanjut beberapa hari); selain itu 'lain'.
    """
    params = params or muat_params()
    estimator = estimator or Estimator(params=params)
    hujan = muat_hujan_imerg_late() if hujan is None else hujan
    kandidat = kejadian_kandidat.tabel_t0() if kandidat is None else kandidat
    prakiraan = prakiraan or params.uji_balik["prakiraan_utama"]
    ub = params.uji_balik
    tgl_kejadian = sorted({pd.Timestamp(t).normalize() for t in kandidat["t0"]})
    jeda = pd.Timedelta(days=int(ub["jeda_hari_kontrol"]))
    ep = params.episode
    awal_data = hujan["waktu"].min().normalize() + pd.Timedelta(hours=ep.horizon_jam + ep.antesedent_hari * 24 + 24)
    akhir_data = hujan["waktu"].max().normalize()
    tanggal = pd.date_range(pd.Timestamp(mulai) if mulai else awal_data.normalize(),
                            pd.Timestamp(selesai) if selesai else akhir_data, freq="D")
    baris = []
    for d in tanggal:
        t0 = (d + pd.Timedelta(hours=int(ub["jam_pindai"]))).to_pydatetime()
        if cakupan_data(hujan, t0, params) < 0.8:
            continue
        if d in tgl_kejadian:
            label = "kejadian"
        elif any(abs(d - t) <= jeda for t in tgl_kejadian):
            label = "sekitar"
        else:
            label = "lain"
        epi = bangun_episode_hujan_nyata(t0, f"PINDAI-{d:%Y%m%d}", "pindai harian", params,
                                         hujan_harian=hujan, prakiraan=prakiraan)
        baris.append({"tanggal": d.date().isoformat(), "label": label,
                      "hujan_aktual_lokal_72j": round(hujan_aktual(hujan, "lokal", t0), 1),
                      "hujan_aktual_hulu_72j": round(hujan_aktual(hujan, "hulu", t0), 1),
                      **evaluasi_episode(epi, estimator, params)})
    return pd.DataFrame(baris)


def _auc(positif: np.ndarray, negatif: np.ndarray) -> float | None:
    """AUC Mann-Whitney: peluang skor hari kejadian > skor hari lain (seri dihitung setengah)."""
    if not len(positif) or not len(negatif):
        return None
    lebih = (positif[:, None] > negatif[None, :]).sum() + 0.5 * (positif[:, None] == negatif[None, :]).sum()
    return round(float(lebih / (len(positif) * len(negatif))), 3)


def metrik_pemisahan(pindai: pd.DataFrame, params: ParamsAktif | None = None,
                     kolom: tuple[str, ...] = ("p_T-0", "p_T-24", "hujan_hulu_3h_tersedia",
                                               "hujan_aktual_hulu_72j", "hujan_aktual_lokal_72j")) -> dict:
    """Seberapa jauh skor memisahkan hari kejadian dari hari lain (hari 'sekitar' dibuang).

    Kembali:
        dict per kolom skor: n_kejadian, n_lain, auc, persentil tiap hari kejadian di antara hari lain,
        dan untuk tiap ambang peluang: porsi hari kejadian >= ambang dan hari lain >= ambang per tahun.
    """
    params = params or muat_params()
    kej = pindai[pindai["label"] == "kejadian"]
    lain = pindai[pindai["label"] == "lain"]
    hasil = {"n_kejadian": int(len(kej)), "n_lain": int(len(lain)), "skor": {}}
    for k in kolom:
        if k not in pindai:
            continue
        pos, neg = kej[k].to_numpy(dtype=float), lain[k].to_numpy(dtype=float)
        isi = {"auc": _auc(pos, neg),
               "persentil_kejadian": {t: round(float((neg < v).mean() * 100), 1)
                                      for t, v in zip(kej["tanggal"], pos)}}
        if k.startswith("p_"):
            for a in params.uji_balik["ambang_peluang_laporan"]:
                isi[f"ambang_{a}"] = {
                    "porsi_kejadian": round(float((pos >= a).mean()), 3) if len(pos) else None,
                    "hari_lain_per_tahun": round(float((neg >= a).mean() * 365.25), 1) if len(neg) else None,
                }
        hasil["skor"][k] = isi
    return hasil


# ---------------------------------------------------------------- pipeline

def jalankan(params: ParamsAktif | None = None, pindai: bool = True) -> dict:
    """Menjalankan uji balik kandidat, kepekaan bias, dan (opsional) pemindaian harian; menyimpan hasil.

    Kembali:
        Ringkasan (juga disimpan ke data/processed/uji_balik/ringkasan.json).
    """
    params = params or muat_params()
    estimator = Estimator(params=params)
    hujan = muat_hujan_imerg_late()
    if hujan.empty:
        raise ValueError("IMERG Late belum diunduh (python -m sensing.jalankan imerg)")
    kandidat = kejadian_kandidat.tabel_t0()
    folder = dir_olahan() / "uji_balik"
    folder.mkdir(parents=True, exist_ok=True)

    ub = uji_balik_kandidat(params, estimator, hujan, kandidat)
    ub.to_csv(folder / "kandidat.csv", index=False, lineterminator="\n")
    kb = kepekaan_bias(params, estimator, hujan, kandidat)
    kb.to_csv(folder / "kepekaan_bias.csv", index=False, lineterminator="\n")
    ringkasan = {
        "dibuat": datetime.now().isoformat(timespec="seconds"),
        "status": "kandidat; model dilatih pada data sintetis; hasil bukan validasi resmi",
        "preset": params.preset, "prakiraan_utama": params.uji_balik["prakiraan_utama"],
        "jumlah_kandidat": int(len(kandidat)),
        "kandidat": ub[ub["prakiraan"] == params.uji_balik["prakiraan_utama"]].to_dict("records"),
    }
    if pindai:
        ph = pindai_harian(params, estimator, hujan, kandidat)
        ph.to_csv(folder / "pindai_harian.csv", index=False, lineterminator="\n")
        ringkasan["pemisahan"] = metrik_pemisahan(ph, params)
    with open(folder / "ringkasan.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(ringkasan, f, ensure_ascii=False, indent=1, default=str)
    return ringkasan


def main(argv: list[str] | None = None) -> None:
    """CLI: python -m simulation.uji_balik [--tanpa-pindai]"""
    ap = argparse.ArgumentParser(description="Uji balik SIGAP-KA pada hujan nyata dan kejadian kandidat")
    ap.add_argument("--tanpa-pindai", action="store_true", help="lewati pemindaian harian (lebih cepat)")
    arg = ap.parse_args(argv)
    # peringatan pandas 2.3 + numpy 2.5 (lihat pyproject filterwarnings), bukan masalah kode ini
    warnings.filterwarnings("ignore", message="The 'generic' unit for NumPy timedelta is deprecated")
    r = jalankan(pindai=not arg.tanpa_pindai)
    kolom = ["id_kandidat", "t0", "hujan_aktual_hulu_72j", "hujan_hulu_3h_tersedia", "p_T-24", "p_T-0",
             "p_maks", "tindakan_sigap"]
    print(pd.DataFrame(r["kandidat"]).reindex(columns=kolom).to_string(index=False))
    if "pemisahan" in r:
        for k, v in r["pemisahan"]["skor"].items():
            print(f"{k:<26} AUC {v['auc']}")


if __name__ == "__main__":
    main()
