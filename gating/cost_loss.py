"""
Tujuan      : Model cost-loss dengan denda alarm palsu: ambang statis di batas waktu siap,
              biaya harapan bertindak/tidak, kerugian L efektif dari skenario lama tutup, dan
              biaya aktual per tindakan setelah hasil episode diketahui.
Lapis       : G (Gating).
Sumber      : Murphy (1977) cost-loss; parameter C, L, P per tindakan di params.json.
Masukan     : Peluang gangguan p, parameter C (biaya tindakan), L (kerugian tanpa persiapan),
              P (denda alarm palsu), satuan juta rupiah.
Keluaran    : Ambang (C + P) / (L + P), biaya harapan, biaya aktual.
Keterbatasan: Tindakan diasumsikan mencegah seluruh kerugian L bila dijalankan tepat waktu;
              denda P dikenakan hanya bila bertindak dan gangguan tidak terjadi.
"""

from __future__ import annotations


def ambang_statis(C: float, L: float, P: float) -> float:
    """Ambang cost-loss di batas waktu siap: bertindak lebih murah bila p > (C + P) / (L + P).

    Turunan: E[bertindak] = C + (1 - p) P; E[tidak] = p L; bertindak bila C + (1 - p) P < p L.
    """
    return (C + P) / (L + P)


def biaya_harapan_bertindak(p: float, C: float, P: float) -> float:
    """Biaya harapan bila bertindak: C + (1 - p) P (juta rupiah)."""
    return C + (1.0 - p) * P


def biaya_harapan_tidak(p: float, L: float) -> float:
    """Biaya harapan bila tidak bertindak: p L (juta rupiah)."""
    return p * L


def L_efektif(L: float, faktor_lama_tutup: float) -> float:
    """Kerugian L disesuaikan sebaran lama tutup (faktor dari inference/lama_tutup.py)."""
    return L * faktor_lama_tutup


def biaya_aktual(bertindak: bool, terganggu: bool, C: float, L: float, P: float) -> float:
    """Biaya satu tindakan setelah hasil diketahui (FR-E2).

    Parameter:
        bertindak: tindakan dijalankan sebelum batas waktunya.
        terganggu: gangguan benar terjadi.
        C: biaya tindakan saat dijalankan (sudah termasuk diskon waktu bila ada).
    Kembali:
        C (+ P bila alarm palsu) bila bertindak; L bila tidak bertindak dan terganggu; 0 selain itu.
    """
    if bertindak:
        return C + (0.0 if terganggu else P)
    return L if terganggu else 0.0


def biaya_rencana(C: float, L: float, P: float, langkah_bertindak: int | None, langkah_batas: int,
                  terganggu: bool, diskon: float) -> float:
    """Biaya aktual satu tindakan dalam satu episode (FR-E2) dengan diskon waktu bertindak.

    Parameter:
        langkah_bertindak: langkah saat tindakan dijalankan (None = tidak dijalankan).
        langkah_batas: langkah batas waktu siap tindakan.
        L: kerugian aktual (sudah dikali faktor skenario lama tutup yang terjadi).
    Kembali:
        Biaya (juta rupiah). Tindakan sesudah batas waktu dianggap tidak dijalankan.
    """
    bertindak = langkah_bertindak is not None and langkah_bertindak <= langkah_batas
    C_k = biaya_tindakan_pada_langkah(C, langkah_batas - langkah_bertindak, diskon) if bertindak else C
    return biaya_aktual(bertindak, terganggu, C_k, L, P)


def biaya_tindakan_pada_langkah(C: float, langkah_sebelum_batas: int, diskon: float) -> float:
    """Biaya tindakan bila dijalankan sejumlah langkah sebelum batas waktu: C (1 - diskon)^langkah.

    Bertindak lebih awal sedikit lebih murah (A-028); tepat di batas waktu biaya = C.
    """
    return C * (1.0 - diskon) ** max(0, langkah_sebelum_batas)
