"""
Tujuan      : Endpoint informasi konsol: empat batas klaim wajib (spesifikasi 6), catatan
              kewenangan KAI, preset aktif, dan status parameter (dummy).
Lapis       : API (pendukung lapis A).
Sumber      : params.json (blok _nyata, _meta), simulation/episode.py (muka air sintetis episode
              nyata dihitung, bukan ditulis tangan).
Masukan     : -
Keluaran    : JSON informasi untuk header/footer dashboard.
Keterbatasan: Nilai muka air sintetis dihitung dari data olahan; bila data belum ada, ditandai kosong.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends

from api.deps import keluaran
from auth.dependensi import pengguna_aktif
from config import muat_params

router = APIRouter(prefix="/info", tags=["info"], dependencies=[Depends(pengguna_aktif)])


@lru_cache(maxsize=1)
def _glapan_sintetis_24jan() -> float | None:
    """Elevasi maksimum muka air sintetis pada 24 Jan 2025 dari model saat ini."""
    try:
        from simulation.episode import bangun_episode_nyata
        ep = bangun_episode_nyata()
        ma = ep.muka_air
        sel = (ma["sumber"] == "muka_air_sintetis") & (ma["lokasi"] == "glapan") & \
              (ma["waktu"].astype(str).str.startswith("2025-01-24"))
        return round(float(ma.loc[sel, "nilai"].max()), 0) if sel.any() else None
    except Exception:  # data olahan belum ada
        return None


@router.get("")
def info():
    """Batas klaim, catatan kewenangan, dan status parameter."""
    p = muat_params()
    n = p.nyata
    nyata, lama, awas = (n["glapan_24jan2025"]["nilai"], n["glapan_model_sintetis_lama_24jan2025"]["nilai"],
                         n["glapan_ambang_awas"]["nilai"])
    baru = _glapan_sintetis_24jan()
    return keluaran({
        "preset": p.preset,
        "versi_parameter": p.mentah["_meta"]["versi"],
        "status_parameter": "dummy",
        "batas_klaim": [
            "Keunggulan SIGAP adalah batas atas menurut asumsi model sendiri; uji penentu butuh prakiraan nyata.",
            (f"Muka air dummy meleset: model lama {lama} dan model sintetis saat ini "
             f"{'belum dihitung' if baru is None else int(baru)} vs nyata {nyata} pada 24 Jan 2025 (Awas {awas})."),
            "Dua kejadian (E3, E6) terjadi dengan hujan lokal rendah, sehingga perlu bukti dari hulu.",
            "Laporan memakai satu definisi episode hujan lebat (horizon 72 jam, keputusan tiap 6 jam).",
        ],
        "catatan_kewenangan": [
            "Usulan SIGAP-KA bersifat saran; setiap tindakan diputuskan operator.",
            "Status jalur ditetapkan pihak berwenang KAI berdasarkan pemeriksaan lapangan.",
        ],
    })
