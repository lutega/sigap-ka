"""
Tujuan      : Menjaga agar tidak ada keluaran sistem (papan, ringkasan, API, dashboard) yang
              menyatakan jalur aman. Status jalur hanya ditetapkan KAI dari pemeriksaan lapangan.
Lapis       : A (Aksi), dipakai juga oleh API.
Sumber      : Spesifikasi FR-A5, bagian 13, CLAUDE.md ("Sistem TIDAK PERNAH menyatakan jalur aman").
Masukan     : Teks atau struktur data (dict/list/dataclass) yang akan dikirim ke pengguna.
Keluaran    : Daftar temuan, atau galat KlaimAmanTerlarang bila ada pernyataan terlarang.
Keterbatasan: Aturan sengaja ketat: kata utuh "aman" atau "safe" dalam keluaran ditolak, termasuk
              dalam negasi; kata turunan seperti "keamanan" tidak terkena. Teks keluaran sistem
              ditulis tanpa kata tersebut.
"""

from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from typing import Any

POLA_TERLARANG = re.compile(r"\b(aman|safe)\b", flags=re.IGNORECASE)


class KlaimAmanTerlarang(ValueError):
    """Keluaran memuat pernyataan yang dapat dibaca sebagai klaim jalur aman."""


def periksa_teks(teks: str) -> list[str]:
    """Mengembalikan potongan teks yang melanggar (kosong bila bersih)."""
    return [m.group(0) for m in POLA_TERLARANG.finditer(teks or "")]


def _semua_teks(obj: Any):
    """Menelusuri seluruh string (kunci dan nilai) dalam struktur data."""
    if is_dataclass(obj) and not isinstance(obj, type):
        obj = asdict(obj)
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _semua_teks(k)
            yield from _semua_teks(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            yield from _semua_teks(v)


def pastikan_tanpa_klaim_aman(obj: Any) -> Any:
    """Memeriksa seluruh teks dalam obj; galat bila ada klaim jalur aman.

    Kembali:
        obj yang sama (agar dapat dipakai berantai).
    Galat:
        KlaimAmanTerlarang.
    """
    for teks in _semua_teks(obj):
        temuan = periksa_teks(teks)
        if temuan:
            raise KlaimAmanTerlarang(f"keluaran memuat kata terlarang {temuan!r}: {teks[:80]!r}")
    return obj
