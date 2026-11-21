"""
Tujuan      : Endpoint lapis A: papan tindakan pada jam keputusan, simpan keputusan operator
              (Setujui/Tolak/Batalkan), log keputusan, dan ringkasan biaya di T-0.
Lapis       : API -> A (Aksi).
Sumber      : action/papan_tindakan.py, action/log_keputusan.py, action/ringkasan.py.
Masukan     : id episode, jam keputusan, keputusan operator, sesi demo (opsional).
Keluaran    : Papan 9 tindakan, baris log, ringkasan T-0.
Keterbatasan: Tidak ada endpoint yang menetapkan atau mengembalikan status jalur aman; keputusan
              tetap pada operator (human in the loop).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from action import log_keputusan
from action.papan_tindakan import susun_papan
from action.ringkasan import ringkasan_episode
from api.deps import Konteks, ambil_konteks, ambil_sesi, keluaran, validasi_jam
from api.schemas import KeputusanMasuk
from auth.dependensi import pengguna_aktif
from db.model import SesiDemo

router = APIRouter(prefix="/episode", tags=["papan tindakan"])


def _log(sesi: Session, episode_id: str, sesi_demo_id: str | None) -> list[dict]:
    """Log keputusan: mode demo per sesi, atau log normal (tanpa sesi demo)."""
    if sesi_demo_id:
        return log_keputusan.daftar(sesi, episode_id, mode="demo", sesi_demo_id=sesi_demo_id)
    return log_keputusan.daftar(sesi, episode_id, mode="normal")


def _cek_sesi_demo(sesi: Session, sesi_demo_id: str | None, episode_id: str) -> None:
    """Sesi demo harus ada dan milik episode yang sama."""
    if not sesi_demo_id:
        return
    s = sesi.get(SesiDemo, sesi_demo_id)
    if s is None or s.episode_id != episode_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sesi demo tidak ditemukan untuk episode ini")


@router.get("/{episode_id}/papan")
def papan(episode_id: str, jam: int = Query(..., description="jam keputusan sebagai jam sebelum T-0"),
          preset: str | None = None, sesi_demo_id: str | None = None,
          sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks),
          pengguna: dict = Depends(pengguna_aktif)):
    """Papan tindakan: status SIGAP per tindakan (Putuskan sekarang, Tunggu, Terlambat, Sudah disetujui)."""
    params = kt.params(preset)
    validasi_jam(params, jam)
    _cek_sesi_demo(sesi, sesi_demo_id, episode_id)
    ep = kt.episode(sesi, episode_id)
    return keluaran(susun_papan(ep, jam, kt.estimator(preset), _log(sesi, episode_id, sesi_demo_id), params))


@router.post("/{episode_id}/keputusan", status_code=status.HTTP_201_CREATED)
def keputusan(episode_id: str, masuk: KeputusanMasuk, preset: str | None = None,
              sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks),
              pengguna: dict = Depends(pengguna_aktif)):
    """Menyimpan Setujui/Tolak/Batalkan beserta status SIGAP saat itu dan username pelaku."""
    params = kt.params(preset)
    validasi_jam(params, masuk.jam_sebelum_t0)
    _cek_sesi_demo(sesi, masuk.sesi_demo_id, episode_id)
    if masuk.sesi_demo_id:
        s = sesi.get(SesiDemo, masuk.sesi_demo_id)
        if masuk.jam_sebelum_t0 != s.jam_sebelum_t0:
            raise HTTPException(status.HTTP_409_CONFLICT, "keputusan demo hanya pada jam yang sedang diputar")
    ep = kt.episode(sesi, episode_id)
    log = _log(sesi, episode_id, masuk.sesi_demo_id)
    p = susun_papan(ep, masuk.jam_sebelum_t0, kt.estimator(preset), log, params)
    baris = next(b for b in p["tindakan"] if b["tindakan"] == masuk.tindakan)
    try:
        catatan = log_keputusan.catat(
            sesi, episode_id, masuk.tindakan, masuk.jam_sebelum_t0, masuk.keputusan, pengguna["username"],
            baris["status"], peluang=baris["peluang"], nilai_kurva=baris["ambang"], alasan=masuk.alasan,
            mode="demo" if masuk.sesi_demo_id else "normal", sesi_demo_id=masuk.sesi_demo_id)
    except log_keputusan.KeputusanTidakValid as galat:
        raise HTTPException(status.HTTP_409_CONFLICT, str(galat))
    return keluaran(catatan)


@router.get("/{episode_id}/log")
def log(episode_id: str, sesi_demo_id: str | None = None, sesi: Session = Depends(ambil_sesi),
        pengguna: dict = Depends(pengguna_aktif)):
    """Log keputusan operator untuk episode (normal atau satu sesi demo)."""
    return keluaran(_log(sesi, episode_id, sesi_demo_id))


@router.get("/{episode_id}/ringkasan")
def ringkasan(episode_id: str, preset: str | None = None, sesi_demo_id: str | None = None,
              sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks),
              pengguna: dict = Depends(pengguna_aktif)):
    """Biaya keputusan operator vs saran SIGAP di T-0, dengan label terlalu awal/terlambat/sia-sia/tepat."""
    params = kt.params(preset)
    _cek_sesi_demo(sesi, sesi_demo_id, episode_id)
    ep = kt.episode(sesi, episode_id)
    return keluaran(ringkasan_episode(ep, kt.estimator(preset), _log(sesi, episode_id, sesi_demo_id), params))
