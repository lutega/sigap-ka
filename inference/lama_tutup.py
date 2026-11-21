"""
Tujuan      : Memperkirakan lama penutupan jalur sebagai tiga skenario (pendek, sedang, panjang)
              yang peluangnya bergantung pada mekanisme; menjadi masukan lapis G untuk kerugian L.
Lapis       : I (Inferensi).
Sumber      : params.json blok lama_tutup (rentang jam, peluang bersyarat, faktor L).
Masukan     : Peluang (tidak, genangan, gerusan).
Keluaran    : Sebaran skenario bila terjadi gangguan, harapan lama tutup (jam), faktor L efektif.
Keterbatasan: Rentang, peluang bersyarat, dan faktor L adalah dummy (A-011); harapan jam memakai
              titik tengah rentang tiap skenario.
"""

from __future__ import annotations

import numpy as np

from config import ParamsAktif, muat_params


def sebaran(peluang: np.ndarray, params: ParamsAktif | None = None) -> dict[str, float]:
    """Sebaran skenario lama tutup bersyarat terjadi gangguan.

    P(s | terganggu) = [p_genangan P(s|genangan) + p_gerusan P(s|gerusan)] / (p_genangan + p_gerusan);
    bila peluang gangguan nol, dipakai campuran mekanisme bawaan.
    """
    lt = (params or muat_params()).lama_tutup
    pg, ps = float(peluang[1]), float(peluang[2])
    total = pg + ps
    if total <= 1e-12:
        bawaan = lt.campuran_mekanisme_bawaan
        pg, ps, total = bawaan["genangan"], bawaan["gerusan"], 1.0
    return {s: (pg * lt.peluang_bersyarat["genangan"][s] + ps * lt.peluang_bersyarat["gerusan"][s]) / total
            for s in lt.skenario}


def harapan_jam(sebaran_skenario: dict[str, float], params: ParamsAktif | None = None) -> float:
    """Harapan lama tutup (jam) dengan titik tengah rentang tiap skenario."""
    lt = (params or muat_params()).lama_tutup
    return float(sum(p * (lt.skenario[s].jam_min + lt.skenario[s].jam_maks) / 2
                     for s, p in sebaran_skenario.items()))


def faktor_L(sebaran_skenario: dict[str, float], params: ParamsAktif | None = None) -> float:
    """Faktor pengali L efektif: sum P(s) x faktor_L(s)."""
    lt = (params or muat_params()).lama_tutup
    return float(sum(p * lt.skenario[s].faktor_L for s, p in sebaran_skenario.items()))


def ringkas(peluang: np.ndarray, params: ParamsAktif | None = None) -> dict:
    """Ringkasan lapis I tentang lama tutup untuk API dan lapis G."""
    sb = sebaran(peluang, params)
    return {"sebaran": sb, "harapan_jam": harapan_jam(sb, params), "faktor_L": faktor_L(sb, params)}
