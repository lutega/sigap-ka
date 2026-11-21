"""
Tujuan      : Menentukan status tiap tindakan pada jam keputusan: Putuskan sekarang, Tunggu
              prakiraan berikutnya, Terlambat, atau Sudah disetujui (aturan spesifikasi 10.3).
Lapis       : G (Gating).
Sumber      : Kurva pemicu (gating/kurva_pemicu.py), peluang lapis I, keputusan operator.
Masukan     : Peluang gangguan, tindakan, jam sebelum T-0, faktor L, status persetujuan.
Keluaran    : StatusTindakan (status, ambang, selisih, sisa jam ke batas waktu).
Keterbatasan: Status adalah usulan; keputusan tetap pada operator dan status jalur tetap
              ditetapkan KAI. Tidak ada status yang menyatakan jalur aman.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from config import ParamsAktif, muat_params
from config.pengaturan import Tindakan
from gating.cost_loss import ambang_statis
from gating.kurva_pemicu import ambang_sekarang

PUTUSKAN = "Putuskan sekarang"
TUNGGU = "Tunggu prakiraan berikutnya"
TERLAMBAT = "Terlambat"
DISETUJUI = "Sudah disetujui"
SEMUA_STATUS = (PUTUSKAN, TUNGGU, TERLAMBAT, DISETUJUI)


@dataclass
class StatusTindakan:
    """Status satu tindakan pada satu jam keputusan."""

    tindakan: str
    status: str
    peluang: float
    ambang: float | None
    selisih: float | None
    sisa_jam: int
    waktu_siap_jam: int
    L_efektif: float

    def ke_dict(self) -> dict:
        """Representasi dict."""
        return asdict(self)


def ambang_pada_jam(tindakan: Tindakan, jam_sebelum_t0: int, params: ParamsAktif | None = None,
                    faktor_L: float = 1.0) -> float | None:
    """Ambang kurva pemicu tindakan pada jam keputusan; None bila batas waktu sudah lewat.

    Kurva dihitung mundur dari batas waktu siap dengan L efektif saat ini (rolling horizon).
    """
    params = params or muat_params()
    ep, g = params.episode, params.gating
    w = tindakan.param.waktu_siap_jam
    if jam_sebelum_t0 < w:
        return None
    langkah = (jam_sebelum_t0 - w) // ep.interval_keputusan_jam
    L = tindakan.param.L * faktor_L
    if langkah == 0:
        return ambang_statis(tindakan.param.C, L, tindakan.param.P)
    return ambang_sekarang(tindakan.param.C, round(L, 6), tindakan.param.P, int(langkah),
                           g.konsentrasi_beta, g.diskon_biaya_awal_per_langkah, g.jumlah_grid_peluang)


def tentukan_status(tindakan: Tindakan, peluang: float, jam_sebelum_t0: int,
                    params: ParamsAktif | None = None, faktor_L: float = 1.0,
                    disetujui: bool = False) -> StatusTindakan:
    """Status tindakan menurut aturan 10.3.

    - Sudah disetujui operator -> tidak dihitung ulang (kecuali dibatalkan).
    - Batas waktu siap lewat tanpa tindakan -> Terlambat.
    - p >= kurva -> Putuskan sekarang; p < kurva -> Tunggu prakiraan berikutnya.
    """
    params = params or muat_params()
    w = tindakan.param.waktu_siap_jam
    ambang = ambang_pada_jam(tindakan, jam_sebelum_t0, params, faktor_L)
    if disetujui:
        status = DISETUJUI
    elif ambang is None:
        status = TERLAMBAT
    elif peluang >= ambang:
        status = PUTUSKAN
    else:
        status = TUNGGU
    return StatusTindakan(
        tindakan=tindakan.id, status=status, peluang=float(peluang),
        ambang=None if ambang is None else float(ambang),
        selisih=None if ambang is None else float(peluang - ambang),
        sisa_jam=int(jam_sebelum_t0 - w), waktu_siap_jam=w,
        L_efektif=float(tindakan.param.L * faktor_L),
    )
