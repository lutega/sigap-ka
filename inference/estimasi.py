"""
Tujuan      : Satu pintu lapis I: pada tiap jam keputusan menghasilkan peluang gangguan, peluang per
              mekanisme, sebaran lama tutup, dan bukti utama (rolling horizon: dihitung ulang setiap
              ada bukti baru); juga menyiapkan data latih dan model bawaan.
Lapis       : I (Inferensi).
Sumber      : inference/fitur.py, peluang_gangguan.py, mekanisme.py, lama_tutup.py; episode latih
              sintetis dari sensing/dummy_generator.py.
Masukan     : Episode (atribut t0, hujan, prakiraan, muka_air, laporan) dan jam keputusan.
Keluaran    : HasilInferensi per jam keputusan.
Keterbatasan: Model bawaan dilatih pada episode sintetis berseed tetap (inferensi.latih) sehingga
              mencerminkan asumsi generator dummy, bukan kalibrasi nyata (A-026).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import timedelta
from functools import lru_cache

import numpy as np

from config import ParamsAktif, muat_params
from inference import lama_tutup, mekanisme
from inference.fitur import IndeksEpisode, jam_relatif_keputusan
from inference.peluang_gangguan import ModelPeluang, perbarui_dengan_laporan

KELAS_INDEKS = {None: 0, "genangan": 1, "gerusan": 2}


@dataclass
class HasilInferensi:
    """Keluaran lapis I pada satu jam keputusan."""

    jam_sebelum_t0: int
    waktu: str
    peluang: float
    peluang_genangan: float
    peluang_gerusan: float
    mekanisme_dominan: str
    porsi_genangan: float
    lama_tutup: dict
    bukti: list
    fitur: dict
    laporan_air_badan_rel: bool
    laporan_jalan_putus: bool
    catatan: list = field(default_factory=list)

    def ke_dict(self) -> dict:
        """Representasi dict (untuk API)."""
        return asdict(self)


class Estimator:
    """Menghitung lapis I untuk episode; model dan parameter dapat diganti (untuk tes/simulasi)."""

    def __init__(self, model: ModelPeluang | None = None, params: ParamsAktif | None = None):
        self.params = params or muat_params()
        self.model = model or model_bawaan(self.params.preset)

    def _indeks(self, episode) -> IndeksEpisode:
        """Indeks numpy episode (dibuat sekali per objek episode)."""
        idx = getattr(episode, "_indeks_sigap", None)
        if idx is None or idx.params is not self.params:
            idx = IndeksEpisode(episode, self.params)
            try:
                episode._indeks_sigap = idx
            except AttributeError:  # pragma: no cover - objek tanpa __dict__
                pass
        return idx

    def peluang_mentah(self, episode, jam_rel: float) -> np.ndarray:
        """Peluang (tidak, genangan, gerusan) pada jam relatif T-0, termasuk pembaruan laporan."""
        idx = self._indeks(episode)
        p = self.model.prediksi(idx.vektor(jam_rel))
        return perbarui_dengan_laporan(p, idx.ada_laporan_air(jam_rel), self.params)

    def peluang_episode(self, episode) -> np.ndarray:
        """Peluang gangguan total pada semua jam keputusan (cepat, untuk simulasi).

        Kembali:
            Larik (jumlah_langkah,) berurutan dari T-horizon ke T-0.
        """
        idx = self._indeks(episode)
        jam = jam_relatif_keputusan(self.params)
        X = np.vstack([idx.vektor(t) for t in jam])
        P = self.model.prediksi(X)
        hasil = np.empty(len(jam))
        for i, t in enumerate(jam):
            q = perbarui_dengan_laporan(P[i], idx.ada_laporan_air(t), self.params)
            hasil[i] = q[1] + q[2]
        return hasil

    def estimasi(self, episode, jam_sebelum_t0: int) -> HasilInferensi:
        """Hasil lapis I lengkap pada satu jam keputusan.

        Parameter:
            episode: objek episode.
            jam_sebelum_t0: jam keputusan dinyatakan sebagai jam sebelum T-0 (mis. 24 = T-24).
        """
        idx = self._indeks(episode)
        t = -float(jam_sebelum_t0)
        x = idx.vektor(t)
        mentah = idx.fitur_mentah(t)
        p = self.peluang_mentah(episode, t)
        mek = mekanisme.tentukan(p)
        catatan = []
        if idx.ada_laporan_air(t):
            catatan.append("Laporan petugas: air di badan rel. Status jalur tetap ditetapkan KAI.")
        return HasilInferensi(
            jam_sebelum_t0=int(jam_sebelum_t0),
            waktu=(episode.t0 - timedelta(hours=jam_sebelum_t0)).isoformat(),
            peluang=float(p[1] + p[2]),
            peluang_genangan=mek["peluang_genangan"],
            peluang_gerusan=mek["peluang_gerusan"],
            mekanisme_dominan=mek["dominan"],
            porsi_genangan=mek["porsi_genangan"],
            lama_tutup=lama_tutup.ringkas(p, self.params),
            bukti=mekanisme.bukti_utama(self.model, x, mentah, p),
            fitur={k: round(v, 2) for k, v in mentah.items()},
            laporan_air_badan_rel=idx.ada_laporan_air(t),
            laporan_jalan_putus=idx.ada_laporan_jalan_putus(t),
            catatan=catatan,
        )

    def estimasi_episode(self, episode) -> list[HasilInferensi]:
        """Hasil lapis I untuk semua jam keputusan episode (T-horizon s.d. T-0)."""
        ep = self.params.episode
        return [self.estimasi(episode, ep.jam_sebelum_t0(k)) for k in range(ep.jumlah_langkah)]


def data_latih(daftar_episode, params: ParamsAktif | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Menyusun matriks latih: satu baris per (episode, jam keputusan), label kelas kebenaran.

    Parameter:
        daftar_episode: episode berkebenaran (atribut kebenaran['mekanisme']).
    Kembali:
        (X (n, d), y (n,)).
    """
    params = params or muat_params()
    jam = jam_relatif_keputusan(params)
    X, y = [], []
    for ep in daftar_episode:
        idx = IndeksEpisode(ep, params)
        kelas = KELAS_INDEKS[ep.kebenaran.get("mekanisme") if ep.kebenaran.get("terganggu") else None]
        for t in jam:
            X.append(idx.vektor(t))
            y.append(kelas)
    return np.vstack(X), np.array(y)


def latih_model(daftar_episode, params: ParamsAktif | None = None) -> ModelPeluang:
    """Melatih ModelPeluang dari episode berkebenaran."""
    params = params or muat_params()
    X, y = data_latih(daftar_episode, params)
    return ModelPeluang(params=params).latih(X, y)


@lru_cache(maxsize=3)
def model_bawaan(preset: str = "base") -> ModelPeluang:
    """Model lapis I bawaan untuk preset: dilatih pada episode sintetis berseed tetap.

    Seed latih = inferensi.latih.offset_seed (terpisah dari SIM_SEED agar episode uji simulasi
    tidak ikut dilatih).
    """
    from sensing import dummy_generator

    params = muat_params(preset)
    latih = params.inferensi["latih"]
    episode = dummy_generator.ambil(int(latih["jumlah_episode"]), int(latih["offset_seed"]), preset,
                                    awalan="LATIH")
    return latih_model(episode, params)
