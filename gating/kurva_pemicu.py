"""
Tujuan      : Menghitung kurva pemicu tiap tindakan dengan pemrograman dinamis mundur dari batas
              waktu siap: pada tiap jam keputusan dibandingkan biaya bertindak sekarang dengan nilai
              harapan menunggu prakiraan berikutnya (nilai informasi).
Lapis       : G (Gating, inti).
Sumber      : Cost-loss Murphy (1977), nilai informasi Howard (1966), pola keputusan dinamis
              Regnier & Harr (2006). Parameter C, L, P, waktu siap, konsentrasi Beta, diskon biaya
              di params.json.
Masukan     : C, L (efektif), P, jumlah langkah sampai batas waktu, parameter gating.
Keluaran    : Ambang peluang per jam keputusan; di batas waktu tepat (C + P) / (L + P).
Keterbatasan: Evolusi peluang antarprakiraan dimodelkan martingale Beta(k p, k (1 - p)) dengan
              k tetap (A-028); L efektif dianggap tetap sepanjang sisa horizon saat kurva dihitung.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache

import numpy as np
from scipy import stats

from config import ParamsAktif, muat_params
from config.pengaturan import Tindakan
from gating.cost_loss import ambang_statis, biaya_tindakan_pada_langkah


@lru_cache(maxsize=16)
def matriks_transisi(jumlah_grid: int, konsentrasi: float) -> tuple[np.ndarray, np.ndarray]:
    """Matriks transisi peluang satu langkah (prakiraan berikutnya) pada grid [0, 1].

    Baris i: sebaran Beta(k g_i, k (1 - g_i)) yang didiskretkan ke sel grid (tepi = titik tengah
    antar-grid). p = 0 dan p = 1 menyerap. Rerata tiap baris kira-kira g_i (martingale).
    Kembali:
        (grid (n,), T (n, n)).
    """
    grid = np.linspace(0.0, 1.0, jumlah_grid)
    tepi = np.concatenate([[0.0], (grid[:-1] + grid[1:]) / 2, [1.0]])
    T = np.zeros((jumlah_grid, jumlah_grid))
    T[0, 0] = 1.0
    T[-1, -1] = 1.0
    for i in range(1, jumlah_grid - 1):
        g = grid[i]
        cdf = stats.beta.cdf(tepi, konsentrasi * g, konsentrasi * (1 - g))
        baris = np.diff(cdf)
        T[i] = baris / baris.sum()
    T.setflags(write=False)
    return grid, T


def _titik_potong(grid: np.ndarray, selisih: np.ndarray) -> float:
    """Peluang terkecil di mana bertindak tidak lebih mahal dari menunggu (selisih <= 0).

    selisih = biaya bertindak - nilai menunggu. Interpolasi linear antar-grid; 1.0 bila tidak
    pernah lebih murah bertindak, 0.0 bila selalu.
    """
    idx = np.nonzero(selisih <= 1e-12)[0]
    if idx.size == 0:
        return 1.0
    i = idx[0]
    if i == 0:
        return 0.0
    s0, s1 = selisih[i - 1], selisih[i]
    return float(grid[i - 1] + (grid[i] - grid[i - 1]) * s0 / (s0 - s1))


def hitung_kurva(C: float, L: float, P: float, langkah_sampai_batas: int,
                 konsentrasi: float, diskon: float, jumlah_grid: int) -> np.ndarray:
    """Pemrograman dinamis mundur untuk satu tindakan.

    V_K(p) = min(C + (1 - p) P, p L)                       (di batas waktu)
    V_k(p) = min(C_k + (1 - p) P, E[V_(k+1)(p') | p])      (sebelum batas waktu)
    dengan C_k = C (1 - diskon)^(K - k).
    Parameter:
        C, L, P: parameter tindakan (L sudah efektif).
        langkah_sampai_batas: K, jumlah langkah keputusan dari sekarang sampai batas waktu.
    Kembali:
        Ambang per langkah k = 0..K (indeks 0 = sekarang, K = batas waktu).
    """
    grid, T = matriks_transisi(jumlah_grid, konsentrasi)
    K = int(langkah_sampai_batas)
    ambang = np.empty(K + 1)
    bertindak_K = C + (1 - grid) * P
    V = np.minimum(bertindak_K, grid * L)
    ambang[K] = ambang_statis(C, L, P)  # solusi eksak di batas waktu
    for k in range(K - 1, -1, -1):
        lanjut = T @ V
        bertindak = biaya_tindakan_pada_langkah(C, K - k, diskon) + (1 - grid) * P
        ambang[k] = _titik_potong(grid, bertindak - lanjut)
        V = np.minimum(bertindak, lanjut)
    return ambang


@dataclass
class KurvaTindakan:
    """Kurva pemicu satu tindakan sepanjang horizon episode."""

    tindakan: str
    nama: str
    C: float
    L: float
    P: float
    waktu_siap_jam: int
    ambang_statis: float
    jam_sebelum_t0: list[int]
    ambang: list[float]

    def ambang_pada(self, jam_sebelum_t0: int) -> float | None:
        """Ambang pada jam keputusan; None bila batas waktu sudah lewat."""
        try:
            return self.ambang[self.jam_sebelum_t0.index(int(jam_sebelum_t0))]
        except ValueError:
            return None

    def ke_dict(self) -> dict:
        """Representasi dict (untuk API dan dashboard)."""
        return asdict(self)


def kurva_untuk_tindakan(tindakan: Tindakan, params: ParamsAktif | None = None,
                         faktor_L: float = 1.0, C: float | None = None, L: float | None = None,
                         P: float | None = None, waktu_siap_jam: int | None = None,
                         mulai_jam_sebelum_t0: int | None = None) -> KurvaTindakan:
    """Kurva pemicu tindakan dari awal horizon (atau jam tertentu) sampai batas waktu siapnya.

    Parameter:
        tindakan: tindakan dari params.
        faktor_L: pengali L dari sebaran lama tutup (lapis I); 1.0 = skenario sedang.
        C, L, P, waktu_siap_jam: pengganti nilai params (slider, FR-G4); tidak disimpan.
        mulai_jam_sebelum_t0: jam keputusan pertama; bawaan horizon episode.
    """
    params = params or muat_params()
    ep, g = params.episode, params.gating
    C = tindakan.param.C if C is None else C
    L = (tindakan.param.L if L is None else L) * faktor_L
    P = tindakan.param.P if P is None else P
    w = tindakan.param.waktu_siap_jam if waktu_siap_jam is None else int(waktu_siap_jam)
    mulai = ep.horizon_jam if mulai_jam_sebelum_t0 is None else int(mulai_jam_sebelum_t0)
    jam = list(range(mulai, w - 1, -ep.interval_keputusan_jam)) if mulai >= w else []
    ambang = hitung_kurva(C, L, P, len(jam) - 1, g.konsentrasi_beta,
                          g.diskon_biaya_awal_per_langkah, g.jumlah_grid_peluang) if jam else np.zeros(0)
    return KurvaTindakan(tindakan=tindakan.id, nama=tindakan.nama, C=C, L=L, P=P, waktu_siap_jam=w,
                         ambang_statis=ambang_statis(C, L, P), jam_sebelum_t0=jam,
                         ambang=[round(float(a), 6) for a in ambang])


def semua_kurva(params: ParamsAktif | None = None, faktor_L: float = 1.0) -> dict[str, KurvaTindakan]:
    """Kurva pemicu T1-T9 untuk preset aktif."""
    params = params or muat_params()
    return {t.id: kurva_untuk_tindakan(t, params, faktor_L) for t in params.daftar_tindakan()}


@lru_cache(maxsize=20000)
def ambang_sekarang(C: float, L: float, P: float, langkah_sampai_batas: int, konsentrasi: float,
                    diskon: float, jumlah_grid: int) -> float:
    """Ambang pada langkah sekarang (indeks 0) dengan cache; dipakai papan dan simulasi."""
    return float(hitung_kurva(C, L, P, langkah_sampai_batas, konsentrasi, diskon, jumlah_grid)[0])
