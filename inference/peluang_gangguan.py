"""
Tujuan      : Menaksir peluang gangguan jalur pada jam keputusan dengan regresi logistik
              multinomial Bayesian dua mekanisme (kelas: tidak terganggu, genangan, gerusan),
              prior ahli Gaussian, dan aproksimasi Laplace; laporan petugas lapangan masuk
              sebagai pembaruan rasio kemungkinan.
Lapis       : I (Inferensi).
Sumber      : Prior di params.json (inferensi.prior_rerata, prior_preset); data latih episode
              berlabel (sintetis dari generator, ditambah episode nyata bila katalog terisi).
Masukan     : Matriks fitur terskala (inference/fitur.py) dan label kelas.
Keluaran    : Peluang (tidak, genangan, gerusan); peluang total = genangan + gerusan.
Keterbatasan: Model linear pada fitur; kejadian nyata hanya enam sehingga prior dan data
              sintetis mendominasi (spesifikasi 9.3). Prediktif dihitung Monte Carlo dengan
              seed tetap agar hasil dapat diulang.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from config import ParamsAktif, muat_params
from inference.fitur import NAMA_FITUR

MEKANISME = ("genangan", "gerusan")


def _softmax_dengan_nol(logit: np.ndarray) -> np.ndarray:
    """Softmax atas [0, logit_genangan, logit_gerusan] pada sumbu terakhir.

    Parameter:
        logit: larik (..., 2).
    Kembali:
        Larik (..., 3) peluang (tidak, genangan, gerusan).
    """
    penuh = np.concatenate([np.zeros(logit.shape[:-1] + (1,)), logit], axis=-1)
    penuh -= penuh.max(axis=-1, keepdims=True)
    e = np.exp(penuh)
    return e / e.sum(axis=-1, keepdims=True)


def prior_dari_params(params: ParamsAktif | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Rerata dan simpangan prior koefisien (2 x (1 + jumlah fitur)), kolom 0 = intersep.

    Preset mengatur pengali rerata dan simpangan (uji sensitivitas prior, spesifikasi 9.3).
    """
    params = params or muat_params()
    rerata = params.inferensi["prior_rerata"]
    pp = params.prior
    mu = np.array([[rerata[m]["intersep"]] + [rerata[m][f] * pp["pengali_rerata"] for f in NAMA_FITUR]
                   for m in MEKANISME], dtype=float)
    sd = np.array([[pp["sd_intersep"]] + [pp["sd_koefisien"]] * len(NAMA_FITUR) for _ in MEKANISME],
                  dtype=float)
    return mu, sd


@dataclass
class ModelPeluang:
    """Model logistik multinomial Bayesian; tanpa pelatihan, model memakai rerata prior."""

    params: ParamsAktif = field(default_factory=muat_params)
    w_map: np.ndarray | None = None          # (2, d+1)
    kovarians: np.ndarray | None = None      # (2(d+1), 2(d+1))
    jumlah_sampel_latih: int = 0
    iterasi: int = 0

    def __post_init__(self):
        self.mu, self.sd = prior_dari_params(self.params)
        if self.w_map is None:
            self.w_map = self.mu.copy()
            self.kovarians = np.diag((self.sd ** 2).ravel())
        self._sampel = None

    # ------------------------------------------------------------ pelatihan
    def _nlp(self, w: np.ndarray, X1: np.ndarray, Y: np.ndarray) -> float:
        """Negatif log posterior (tanpa konstanta)."""
        P = _softmax_dengan_nol(X1 @ w.T)
        loglik = np.sum(Y * np.log(np.clip(P, 1e-12, 1.0)))
        return float(-loglik + 0.5 * np.sum(((w - self.mu) / self.sd) ** 2))

    def latih(self, X: np.ndarray, y: np.ndarray) -> "ModelPeluang":
        """Mencari MAP dengan Newton teredam lalu kovarians Laplace = invers Hessian.

        Parameter:
            X: fitur terskala (n, d).
            y: kelas 0 = tidak, 1 = genangan, 2 = gerusan (n,).
        Kembali:
            self (terlatih).
        """
        n, d = X.shape
        X1 = np.hstack([np.ones((n, 1)), X])
        Y = np.eye(3)[y.astype(int)]
        w = self.mu.copy()
        presisi = (1.0 / self.sd ** 2).ravel()
        maks = int(self.params.inferensi["latih"]["maks_iterasi"])
        for it in range(maks):
            P = _softmax_dengan_nol(X1 @ w.T)
            G = (P[:, 1:] - Y[:, 1:]).T @ X1 + (w - self.mu) / self.sd ** 2  # gradien (2, d+1)
            H = self._hessian(X1, P, presisi)
            langkah = np.linalg.solve(H, G.ravel()).reshape(w.shape)
            f0, a = self._nlp(w, X1, Y), 1.0
            while a > 1e-4 and self._nlp(w - a * langkah, X1, Y) > f0:  # pencarian garis mundur
                a *= 0.5
            w = w - a * langkah
            self.iterasi = it + 1
            if np.max(np.abs(a * langkah)) < 1e-6:
                break
        P = _softmax_dengan_nol(X1 @ w.T)
        self.w_map = w
        self.kovarians = np.linalg.inv(self._hessian(X1, P, presisi))
        self.jumlah_sampel_latih = n
        self._sampel = None
        return self

    @staticmethod
    def _hessian(X1: np.ndarray, P: np.ndarray, presisi: np.ndarray) -> np.ndarray:
        """Hessian negatif log posterior untuk dua kelas non-acuan."""
        d1 = X1.shape[1]
        H = np.zeros((2 * d1, 2 * d1))
        for k in range(2):
            for m in range(2):
                bobot = P[:, k + 1] * ((k == m) - P[:, m + 1])
                H[k * d1:(k + 1) * d1, m * d1:(m + 1) * d1] = (X1 * bobot[:, None]).T @ X1
        return H + np.diag(presisi)

    # ------------------------------------------------------------ prediksi
    def _sampel_bobot(self) -> np.ndarray:
        """Sampel koefisien dari posterior Laplace (seed tetap, dibuat sekali)."""
        if self._sampel is None:
            latih = self.params.inferensi["latih"]
            rng = np.random.default_rng(latih["offset_seed"])
            s = rng.multivariate_normal(self.w_map.ravel(), self.kovarians,
                                        size=int(latih["sampel_monte_carlo"]), method="cholesky")
            self._sampel = s.reshape(-1, *self.w_map.shape)
        return self._sampel

    def prediksi(self, X: np.ndarray) -> np.ndarray:
        """Peluang prediktif (tidak, genangan, gerusan) dirata-rata atas sampel posterior.

        Parameter:
            X: fitur terskala (n, d) atau (d,).
        Kembali:
            Larik (n, 3) atau (3,).
        """
        satu = X.ndim == 1
        X1 = np.hstack([np.ones((np.atleast_2d(X).shape[0], 1)), np.atleast_2d(X)])
        logit = np.einsum("nd,skd->snk", X1, self._sampel_bobot())
        P = _softmax_dengan_nol(logit).mean(axis=0)
        return P[0] if satu else P

    def kontribusi(self, x: np.ndarray) -> dict[str, np.ndarray]:
        """Kontribusi tiap fitur pada logit tiap mekanisme (koefisien MAP x nilai fitur)."""
        return {m: self.w_map[i, 1:] * x for i, m in enumerate(MEKANISME)}


def perbarui_dengan_laporan(peluang: np.ndarray, ada_laporan: bool,
                            params: ParamsAktif | None = None) -> np.ndarray:
    """Menaikkan peluang gangguan bila ada laporan air di badan rel (rasio kemungkinan).

    odds' = odds x RK; porsi genangan:gerusan dipertahankan.
    Parameter:
        peluang: (tidak, genangan, gerusan).
        ada_laporan: True bila laporan sudah masuk pada jam keputusan.
    Kembali:
        Peluang baru (3,).
    """
    if not ada_laporan:
        return peluang
    rk = (params or muat_params()).inferensi["laporan_lapangan"]["rasio_kemungkinan_air_badan_rel"]
    total = peluang[1] + peluang[2]
    if total <= 0:
        return peluang
    odds = total / max(1e-12, 1 - total) * rk
    baru = odds / (1 + odds)
    return np.array([1 - baru, baru * peluang[1] / total, baru * peluang[2] / total])
