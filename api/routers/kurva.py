"""
Tujuan      : Endpoint lapis G: daftar tindakan beserta parameter C, L, P, waktu siap; kurva pemicu
              satu tindakan; hitung ulang kurva dengan parameter slider (FR-G4).
Lapis       : API -> G (Gating).
Sumber      : config/params.json (satu sumber parameter), gating/kurva_pemicu.py.
Masukan     : id tindakan, preset, parameter pengganti.
Keluaran    : Kurva pemicu per jam keputusan dan ambang statis (C + P) / (L + P).
Keterbatasan: Parameter dari slider hanya untuk perhitungan; params.json tidak diubah.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import Konteks, ambil_konteks, keluaran
from api.schemas import KurvaHitungMasuk
from auth.dependensi import pengguna_aktif
from config import ID_TINDAKAN
from gating.kurva_pemicu import kurva_untuk_tindakan

KODE_422 = 422  # konten tidak dapat diproses (nama konstanta berubah antar versi Starlette)
router = APIRouter(tags=["tindakan dan kurva"], dependencies=[Depends(pengguna_aktif)])


@router.get("/tindakan")
def daftar_tindakan(preset: str | None = None, kt: Konteks = Depends(ambil_konteks)):
    """Tindakan T1-T9 dengan parameter preset (satuan juta rupiah) dan ambang statisnya."""
    p = kt.params(preset)
    return keluaran({
        "preset": p.preset,
        "satuan_biaya": p.mentah["_meta"]["satuan_biaya"],
        "tindakan": [{
            "id": t.id, "nama": t.nama, "keputusan_sebelum": t.keputusan_sebelum,
            "terkonfirmasi": t.terkonfirmasi, "label_parameter": t.status,
            "C": t.param.C, "L": t.param.L, "P": t.param.P, "waktu_siap_jam": t.param.waktu_siap_jam,
            "ambang_statis": t.param.ambang_statis,
        } for t in p.daftar_tindakan()],
    })


@router.get("/kurva/{tindakan}")
def kurva(tindakan: str, preset: str | None = None, faktor_L: float = 1.0, kt: Konteks = Depends(ambil_konteks)):
    """Kurva pemicu satu tindakan dari awal horizon sampai batas waktu siapnya."""
    if tindakan not in ID_TINDAKAN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"tindakan {tindakan} tidak dikenal")
    if faktor_L <= 0:
        raise HTTPException(KODE_422, "faktor_L harus > 0")
    p = kt.params(preset)
    return keluaran(kurva_untuk_tindakan(p.tindakan[tindakan], p, faktor_L).ke_dict())


@router.post("/kurva/hitung")
def hitung_ulang(masuk: KurvaHitungMasuk, kt: Konteks = Depends(ambil_konteks)):
    """Hitung ulang kurva dengan parameter slider; dikembalikan bersama kurva bawaan sebagai pembanding."""
    p = kt.params(masuk.preset)
    t = p.tindakan[masuk.tindakan]
    w = masuk.waktu_siap_jam
    if w is not None and (w % p.episode.interval_keputusan_jam or w > p.episode.horizon_jam):
        raise HTTPException(KODE_422,
                            f"waktu_siap_jam harus kelipatan {p.episode.interval_keputusan_jam} dan <= horizon")
    L_dasar = masuk.L if masuk.L is not None else t.param.L
    C = masuk.C if masuk.C is not None else t.param.C
    if C >= L_dasar * masuk.faktor_L:
        raise HTTPException(KODE_422, "C harus lebih kecil dari L efektif")
    baru = kurva_untuk_tindakan(t, p, masuk.faktor_L, C=masuk.C, L=masuk.L, P=masuk.P, waktu_siap_jam=w)
    bawaan = kurva_untuk_tindakan(t, p, 1.0)
    return keluaran({"kurva": baru.ke_dict(), "kurva_bawaan": bawaan.ke_dict(),
                     "catatan": "Parameter slider tidak disimpan; params.json tetap satu-satunya sumber parameter."})
