"""
Tujuan      : Evaluasi kebijakan dan estimasi gangguan: biaya per episode (FR-E2) untuk enam
              kebijakan pada banyak episode sintetis (FR-E1, FR-E3), serta POD, FAR, CSI, dan lead
              time dengan leave-one-episode-out (FR-E4) dibanding aturan hujan lokal dan indeks
              adaptasi H-MHEWS.
Lapis       : Simulasi/evaluasi.
Sumber      : simulation/kebijakan.py, inference/estimasi.py, gating/cost_loss.py, generator dummy.
Masukan     : Jumlah episode, seed, preset.
Keluaran    : HasilSimulasi (tabel biaya per episode per kebijakan, ringkasan, metrik deteksi).
Keterbatasan: Episode dan hasilnya sintetis; keunggulan kebijakan adalah batas atas menurut asumsi
              model sendiri (spesifikasi 6). Uji penentu butuh prakiraan nyata.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config import ParamsAktif, muat_params, muat_pengaturan
from gating.cost_loss import biaya_rencana
from inference.estimasi import Estimator, data_latih, model_bawaan
from inference.fitur import IndeksEpisode, jam_relatif_keputusan
from inference.peluang_gangguan import ModelPeluang, perbarui_dengan_laporan
from simulation.episode import Episode, episode_sintetis
from simulation.kebijakan import KEBIJAKAN, NAMA_KEBIJAKAN, rencana


def faktor_L_aktual(kebenaran: dict, params: ParamsAktif) -> float:
    """Faktor L dari skenario lama tutup yang benar-benar terjadi (1,0 bila tidak diketahui)."""
    s = kebenaran.get("skenario_lama_tutup")
    return params.lama_tutup.skenario[s].faktor_L if s else 1.0


def biaya_episode(rencana_langkah: dict[str, int | None], terganggu: bool, faktor_aktual: float,
                  params: ParamsAktif) -> float:
    """Biaya satu episode = jumlah biaya sembilan tindakan (FR-E2)."""
    ep, diskon = params.episode, params.gating.diskon_biaya_awal_per_langkah
    total = 0.0
    for t in params.daftar_tindakan():
        total += biaya_rencana(t.param.C, t.param.L * faktor_aktual, t.param.P,
                               rencana_langkah.get(t.id), ep.langkah_dari_jam(t.param.waktu_siap_jam),
                               terganggu, diskon)
    return total


@dataclass
class HasilSimulasi:
    """Hasil satu run simulasi."""

    preset: str
    seed: int
    jumlah_episode: int
    biaya: pd.DataFrame                       # kolom episode_ke, episode_id, kebijakan, biaya, terganggu
    ringkasan: dict = field(default_factory=dict)

    def tabel_ringkas(self) -> pd.DataFrame:
        """Rerata, simpangan, dan median biaya per kebijakan."""
        g = self.biaya.groupby("kebijakan")["biaya"]
        tab = pd.DataFrame({"rerata": g.mean(), "simpangan": g.std(), "median": g.median()})
        return tab.loc[[k for k in KEBIJAKAN if k in tab.index]]


def ringkas(biaya: pd.DataFrame) -> dict:
    """Ringkasan: rerata per kebijakan, pembanding terbaik (selain SIGAP dan informasi sempurna),
    dan persentase selisih SIGAP terhadapnya."""
    rerata = biaya.groupby("kebijakan")["biaya"].mean()
    pembanding = rerata.drop(["sigap", "informasi_sempurna"], errors="ignore")
    terbaik = pembanding.idxmin()
    selisih = (rerata["sigap"] - rerata[terbaik]) / rerata[terbaik] * 100.0
    tab = biaya.pivot(index="episode_ke", columns="kebijakan", values="biaya")
    berpasangan = {}
    for k in pembanding.index:  # selisih berpasangan per episode: SIGAP - pembanding
        d = tab["sigap"] - tab[k]
        se = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else 0.0
        berpasangan[k] = {"rerata": round(float(d.mean()), 2), "galat_baku": round(se, 2),
                          "ki95": [round(float(d.mean() - 1.96 * se), 2), round(float(d.mean() + 1.96 * se), 2)]}
    return {
        "rerata_biaya": {k: round(float(rerata[k]), 2) for k in KEBIJAKAN if k in rerata},
        "nama_kebijakan": NAMA_KEBIJAKAN,
        "pembanding_terbaik": terbaik,
        "sigap_vs_pembanding_terbaik_persen": round(float(selisih), 2),
        "selisih_berpasangan_sigap": berpasangan,
        "laju_gangguan": round(float(biaya.drop_duplicates("episode_ke")["terganggu"].mean()), 4),
        "catatan": "Parameter dummy; keunggulan adalah batas atas menurut asumsi model sendiri.",
    }


def simulasi(n: int | None = None, seed: int | None = None, preset: str | None = None,
             estimator: Estimator | None = None, episode: list[Episode] | None = None,
             params: ParamsAktif | None = None) -> HasilSimulasi:
    """Menjalankan n episode sintetis untuk enam kebijakan dengan informasi setara.

    Parameter:
        n: jumlah episode (bawaan simulasi.jumlah_episode = 300).
        seed: seed episode (bawaan SIM_SEED); terpisah dari seed latih model lapis I.
        preset: preset parameter.
        estimator: estimator lapis I (bawaan model bawaan preset).
        episode: daftar episode siap pakai (mengabaikan n/seed).
        params: parameter pengganti (uji sensitivitas); bawaan params preset.
    """
    params = params or muat_params(preset)
    n = int(n or params.simulasi["jumlah_episode"])
    seed = int(muat_pengaturan().sim_seed if seed is None else seed)
    estimator = estimator or Estimator(model_bawaan(params.preset), params)
    episode = episode if episode is not None else episode_sintetis(n, seed, params.preset)
    baris = []
    for i, ep in enumerate(episode):
        lint = estimator.lintasan(ep)
        terganggu = bool(ep.kebenaran["terganggu"])
        fa = faktor_L_aktual(ep.kebenaran, params)
        for nama in KEBIJAKAN:
            r = rencana(nama, lint, terganggu, params)
            baris.append((i, ep.id, nama, biaya_episode(r, terganggu, fa, params), terganggu))
    biaya = pd.DataFrame(baris, columns=["episode_ke", "episode_id", "kebijakan", "biaya", "terganggu"])
    return HasilSimulasi(params.preset, seed, len(episode), biaya, ringkas(biaya))


def sensitivitas_diskon(daftar_diskon: list[float], episode: list[Episode],
                        preset: str | None = None) -> pd.DataFrame:
    """Rerata biaya tiap kebijakan untuk beberapa nilai diskon biaya awal (biaya menunggu).

    Episode dan model lapis I sama untuk semua nilai sehingga hanya lapis G/biaya yang berubah.
    Kembali:
        DataFrame baris = diskon, kolom = kebijakan, plus kolom persen SIGAP vs pembanding terbaik.
    """
    dasar = muat_params(preset)
    model = model_bawaan(dasar.preset)
    baris = []
    for d in daftar_diskon:
        p = dasar.model_copy(update={"gating": dasar.gating.model_copy(
            update={"diskon_biaya_awal_per_langkah": float(d)})})
        h = simulasi(estimator=Estimator(model, p), episode=episode, params=p)
        baris.append({"diskon": d, **h.ringkasan["rerata_biaya"],
                      "pembanding_terbaik": h.ringkasan["pembanding_terbaik"],
                      "sigap_vs_terbaik_persen": h.ringkasan["sigap_vs_pembanding_terbaik_persen"]})
    return pd.DataFrame(baris)


# ---------------------------------------------------------------- metrik deteksi (RQ1)

def metrik_kontingensi(alarm_langkah: list[int | None], terganggu: np.ndarray, jam: list[float]) -> dict:
    """POD, FAR, CSI, dan rerata lead time.

    Parameter:
        alarm_langkah: langkah pertama alarm per episode (None = tidak ada alarm).
        terganggu: hasil per episode (bool).
        jam: jam relatif T-0 tiap langkah (untuk lead time, jam sebelum T-0).
    """
    hit = miss = fa = 0
    lead = []
    for k, y in zip(alarm_langkah, terganggu):
        if k is not None and y:
            hit += 1
            lead.append(-jam[k])
        elif k is None and y:
            miss += 1
        elif k is not None and not y:
            fa += 1
    return {
        "POD": hit / (hit + miss) if hit + miss else 0.0,
        "FAR": fa / (hit + fa) if hit + fa else 0.0,
        "CSI": hit / (hit + miss + fa) if hit + miss + fa else 0.0,
        "lead_time_jam": float(np.mean(lead)) if lead else 0.0,
        "hit": hit, "miss": miss, "false_alarm": fa,
    }


def _langkah_alarm(skor: np.ndarray, ambang: float) -> int | None:
    """Langkah pertama skor >= ambang, tanpa langkah T-0 (lead time nol tidak dihitung)."""
    k = np.nonzero(skor[:-1] >= ambang)[0]
    return int(k[0]) if k.size else None


def peluang_loeo(episode: list, params: ParamsAktif | None = None) -> np.ndarray:
    """Peluang gangguan leave-one-episode-out: tiap episode diprediksi model yang dilatih tanpa episode itu.

    Kembali:
        Larik (jumlah_episode, jumlah_langkah).
    """
    params = params or muat_params()
    jam = jam_relatif_keputusan(params)
    X, y = data_latih(episode, params)
    m = len(jam)
    hasil = np.empty((len(episode), m))
    for i, ep in enumerate(episode):
        maska = np.ones(len(y), bool)
        maska[i * m:(i + 1) * m] = False
        model = ModelPeluang(params=params).latih(X[maska], y[maska])
        P = model.prediksi(X[i * m:(i + 1) * m])
        idx = IndeksEpisode(ep, params)
        for j, t in enumerate(jam):
            q = perbarui_dengan_laporan(P[j], idx.ada_laporan_air(t), params)
            hasil[i, j] = q[1] + q[2]
    return hasil


def skor_pembanding(episode: list, params: ParamsAktif | None = None) -> dict[str, np.ndarray]:
    """Skor pembanding RQ1 dengan informasi setara pada jam yang sama.

    - aturan_hujan_lokal: hujan lokal 3 hari teramati + prakiraan lokal sampai T-0 (mm);
    - hmhews: indeks adaptasi 0-4 = maks(kategori hujan BMKG dari hujan 24 jam teramati dan
      prakiraan sampai T-0, level 3 bila Glapan >= Awas). Hanya pembanding, bukan masukan.
    """
    params = params or muat_params()
    jam = jam_relatif_keputusan(params)
    kat = params.simulasi["pembanding_deteksi"]["hmhews_kategori_hujan_harian_mm"]
    batas = [kat["sedang"], kat["lebat"], kat["sangat_lebat"], kat["ekstrem"]]
    lokal = np.empty((len(episode), len(jam)))
    hm = np.empty_like(lokal)
    for i, ep in enumerate(episode):
        idx = IndeksEpisode(ep, params)
        for j, t in enumerate(jam):
            f = idx.fitur_mentah(t)
            lokal[i, j] = f["hujan_lokal_3h"] + f["prakiraan_lokal"]
            hujan = max(f["hujan_lokal_1h"], f["prakiraan_lokal"])
            level_hujan = sum(hujan >= b for b in batas)
            level_air = 3 if f["glapan_relatif"] >= 0 else 0
            hm[i, j] = max(level_hujan, level_air)
    return {"aturan_hujan_lokal": lokal, "hmhews": hm}


def evaluasi_deteksi(episode: list, params: ParamsAktif | None = None) -> dict[str, dict]:
    """POD/FAR/CSI/lead time SIGAP (LOEO) dan dua pembanding (FR-E4)."""
    params = params or muat_params()
    jam = jam_relatif_keputusan(params)
    y = np.array([bool(e.kebenaran["terganggu"]) for e in episode])
    p = peluang_loeo(episode, params)
    pemb = skor_pembanding(episode, params)
    pd_ = params.simulasi["pembanding_deteksi"]
    ambang = float(params.inferensi["ambang_deteksi"])
    return {
        "sigap_loeo": metrik_kontingensi([_langkah_alarm(r, ambang) for r in p], y, jam),
        "aturan_hujan_lokal": metrik_kontingensi(
            [_langkah_alarm(r, pd_["aturan_hujan_lokal_3h_mm"]) for r in pemb["aturan_hujan_lokal"]], y, jam),
        "hmhews": metrik_kontingensi(
            [_langkah_alarm(r, pd_["hmhews_level_peringatan"]) for r in pemb["hmhews"]], y, jam),
    }
