"""
Tujuan      : Enam kebijakan pembanding (FR-E1): SIGAP, jam tetap 24 jam, ambang tetap 0,5,
              cost-loss di batas, reaktif, dan informasi sempurna. Setiap kebijakan menghasilkan
              langkah bertindak per tindakan untuk satu episode.
Lapis       : Simulasi/evaluasi.
Sumber      : Lintasan lapis I (peluang, faktor L, laporan per jam keputusan); kurva pemicu lapis G.
Masukan     : Lintasan episode, hasil episode (hanya untuk informasi sempurna), parameter.
Keluaran    : dict id tindakan -> langkah bertindak (None = tidak bertindak).
Keterbatasan: Semua kebijakan menerima peluang yang sama pada jam yang sama (informasi setara).
              Definisi operasional "jam tetap 24 jam" dan "reaktif" adalah tafsiran (A-035).
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from config import ParamsAktif, muat_params
from gating.cost_loss import ambang_statis
from gating.status import langkah_putuskan

NAMA_KEBIJAKAN = {
    "sigap": "SIGAP (kurva pemicu)",
    "jam_tetap_24": "Jam tetap 24 jam",
    "ambang_tetap_05": "Ambang tetap 0,5",
    "cost_loss_batas": "Cost-loss di batas waktu",
    "reaktif": "Reaktif (tunggu bukti lapangan)",
    "informasi_sempurna": "Informasi sempurna (batas bawah)",
}


def _batas(t, params: ParamsAktif) -> int:
    """Langkah batas waktu siap tindakan."""
    return params.episode.langkah_dari_jam(t.param.waktu_siap_jam)


def _statis(t, faktor: float) -> float:
    """Ambang cost-loss statis dengan L efektif."""
    return ambang_statis(t.param.C, t.param.L * faktor, t.param.P)


def sigap(lintasan: dict, terganggu: bool, params: ParamsAktif) -> dict[str, int | None]:
    """Bertindak pada langkah pertama p >= kurva pemicu (sama dengan papan tindakan)."""
    return {t.id: langkah_putuskan(t, lintasan["peluang"], lintasan["faktor_L"], params)
            for t in params.daftar_tindakan()}


def jam_tetap_24(lintasan: dict, terganggu: bool, params: ParamsAktif) -> dict[str, int | None]:
    """Diputuskan sekali pada T-24 (atau di batas waktu bila batasnya lebih awal) dengan ambang statis."""
    ep = params.episode
    jam_tetap = int(params.simulasi["jam_tetap_sebelum_t0"])
    hasil = {}
    for t in params.daftar_tindakan():
        k = ep.langkah_dari_jam(max(jam_tetap, t.param.waktu_siap_jam))
        p, f = lintasan["peluang"][k], lintasan["faktor_L"][k]
        hasil[t.id] = k if p >= _statis(t, f) else None
    return hasil


def ambang_tetap_05(lintasan: dict, terganggu: bool, params: ParamsAktif) -> dict[str, int | None]:
    """Bertindak begitu p >= 0,5 sebelum batas waktu."""
    a = float(params.simulasi["ambang_tetap"])
    hasil = {}
    for t in params.daftar_tindakan():
        k_ok = np.nonzero(lintasan["peluang"][:_batas(t, params) + 1] >= a)[0]
        hasil[t.id] = int(k_ok[0]) if k_ok.size else None
    return hasil


def cost_loss_batas(lintasan: dict, terganggu: bool, params: ParamsAktif) -> dict[str, int | None]:
    """Diputuskan tepat di batas waktu siap dengan ambang statis (C + P) / (L + P)."""
    hasil = {}
    for t in params.daftar_tindakan():
        k = _batas(t, params)
        hasil[t.id] = k if lintasan["peluang"][k] >= _statis(t, lintasan["faktor_L"][k]) else None
    return hasil


def reaktif(lintasan: dict, terganggu: bool, params: ParamsAktif) -> dict[str, int | None]:
    """Bertindak hanya setelah ada bukti gangguan teramati (laporan air di badan rel), sebelum batas."""
    hasil = {}
    for t in params.daftar_tindakan():
        k_ok = np.nonzero(lintasan["laporan"][:_batas(t, params) + 1])[0]
        hasil[t.id] = int(k_ok[0]) if k_ok.size else None
    return hasil


def informasi_sempurna(lintasan: dict, terganggu: bool, params: ParamsAktif) -> dict[str, int | None]:
    """Mengetahui hasil: bertindak paling awal (termurah) hanya bila gangguan terjadi (batas bawah)."""
    return {t.id: (0 if terganggu else None) for t in params.daftar_tindakan()}


KEBIJAKAN: dict[str, Callable] = {
    "sigap": sigap,
    "jam_tetap_24": jam_tetap_24,
    "ambang_tetap_05": ambang_tetap_05,
    "cost_loss_batas": cost_loss_batas,
    "reaktif": reaktif,
    "informasi_sempurna": informasi_sempurna,
}


def rencana(nama: str, lintasan: dict, terganggu: bool, params: ParamsAktif | None = None) -> dict[str, int | None]:
    """Rencana langkah bertindak satu kebijakan untuk satu episode."""
    return KEBIJAKAN[nama](lintasan, terganggu, params or muat_params())
