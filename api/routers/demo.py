"""
Tujuan      : Endpoint mode demo (spesifikasi 16): POST /demo/mulai, POST /demo/{id}/langkah,
              POST /demo/{id}/jeda, GET /demo/{id}/status, POST /demo/{id}/reset (admin), serta
              POST /demo/{id}/kecepatan. Status memuat papan, lintasan peluang, dan seri sampai jam
              yang sedang diputar, serta ringkasan T-0 saat episode selesai.
Lapis       : API -> simulasi/demo (I-G-A).
Sumber      : simulation/demo.py, action/papan_tindakan.py, action/ringkasan.py.
Masukan     : id episode, kecepatan, id sesi demo.
Keluaran    : Status demo lengkap; log keputusan demo bertanda mode='demo'.
Keterbatasan: Hanya pembuat sesi atau admin yang dapat mengendalikan sesi; reset khusus admin.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from action import log_keputusan
from action.papan_tindakan import susun_papan
from action.ringkasan import ringkasan_episode
from api.deps import Konteks, ambil_konteks, ambil_sesi, keluaran
from api.schemas import DemoMulai
from auth.dependensi import pengguna_aktif, wajib_admin
from simulation import demo

router = APIRouter(prefix="/demo", tags=["mode demo"])


class Kecepatan(BaseModel):
    """Kecepatan putar demo."""

    kecepatan_detik_per_jam: float = Field(gt=0, le=60)


def _sesi_milik(sesi: Session, sesi_id: str, pengguna: dict):
    """Sesi demo yang boleh dikendalikan pengguna (pembuat atau admin)."""
    try:
        s = demo.ambil(sesi, sesi_id)
    except demo.GalatDemo as galat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(galat))
    if s.username != pengguna["username"] and pengguna["level"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sesi demo milik pengguna lain")
    return s


def status_lengkap(kt: Konteks, sesi: Session, s) -> dict:
    """Status demo: sesi, label episode, papan, lintasan sampai jam berjalan, ringkasan bila selesai."""
    params = kt.params()
    ep = kt.episode(sesi, s.episode_id)
    est = kt.estimator()
    log = log_keputusan.daftar(sesi, s.episode_id, mode="demo", sesi_demo_id=s.id)
    lintasan = []
    for k in range(params.episode.jumlah_langkah):
        j = params.episode.jam_sebelum_t0(k)
        if j < s.jam_sebelum_t0:
            break
        h = est.estimasi(ep, j)
        lintasan.append({"jam_sebelum_t0": j, "peluang": h.peluang})
    return {
        "sesi": demo.ke_dict(s, params),
        "episode": {"id": ep.id, "nama": ep.nama, "jenis": ep.jenis, "label_seri": ep.label_seri,
                    "status_hasil": ep.status_hasil},
        "papan": susun_papan(ep, s.jam_sebelum_t0, est, log, params),
        "lintasan": lintasan,
        "log": log,
        "ringkasan": ringkasan_episode(ep, est, log, params) if s.jam_sebelum_t0 == 0 else None,
    }


@router.post("/mulai", status_code=status.HTTP_201_CREATED)
def mulai(masuk: DemoMulai, sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks),
          pengguna: dict = Depends(pengguna_aktif)):
    """Memulai sesi demo pada T-horizon untuk episode nyata atau sintetis."""
    try:
        s = demo.mulai(sesi, masuk.episode_id, pengguna["username"], masuk.kecepatan_detik_per_jam, kt.params())
    except demo.GalatDemo as galat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(galat))
    sesi.commit()
    return keluaran(status_lengkap(kt, sesi, s))


@router.post("/{sesi_id}/langkah")
def langkah(sesi_id: str, sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks),
            pengguna: dict = Depends(pengguna_aktif)):
    """Lompat ke jam keputusan berikutnya (T-0 menutup episode dan memunculkan ringkasan)."""
    _sesi_milik(sesi, sesi_id, pengguna)
    try:
        s = demo.langkah(sesi, sesi_id, kt.params())
    except demo.GalatDemo as galat:
        raise HTTPException(status.HTTP_409_CONFLICT, str(galat))
    sesi.commit()
    return keluaran(status_lengkap(kt, sesi, s))


@router.post("/{sesi_id}/jeda")
def jeda(sesi_id: str, sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks),
         pengguna: dict = Depends(pengguna_aktif)):
    """Menjeda atau melanjutkan putar ulang."""
    _sesi_milik(sesi, sesi_id, pengguna)
    s = demo.jeda(sesi, sesi_id)
    sesi.commit()
    return keluaran({"sesi": demo.ke_dict(s, kt.params())})


@router.post("/{sesi_id}/kecepatan")
def kecepatan(sesi_id: str, masuk: Kecepatan, sesi: Session = Depends(ambil_sesi),
              kt: Konteks = Depends(ambil_konteks), pengguna: dict = Depends(pengguna_aktif)):
    """Mengubah kecepatan putar (detik per jam episode)."""
    _sesi_milik(sesi, sesi_id, pengguna)
    s = demo.atur_kecepatan(sesi, sesi_id, masuk.kecepatan_detik_per_jam)
    sesi.commit()
    return keluaran({"sesi": demo.ke_dict(s, kt.params())})


@router.get("/{sesi_id}/status")
def status_demo(sesi_id: str, sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks),
                pengguna: dict = Depends(pengguna_aktif)):
    """Status lengkap sesi demo pada jam yang sedang diputar (tanpa data sesudahnya)."""
    s = _sesi_milik(sesi, sesi_id, pengguna)
    return keluaran(status_lengkap(kt, sesi, s))


@router.post("/{sesi_id}/reset")
def reset(sesi_id: str, sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks),
          admin: dict = Depends(wajib_admin)):
    """Mengulang episode demo dan menghapus log demo sesi ini saja (khusus admin)."""
    try:
        s, n = demo.reset(sesi, sesi_id, kt.params())
    except demo.GalatDemo as galat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(galat))
    sesi.commit()
    hasil = status_lengkap(kt, sesi, s)
    hasil["log_demo_dihapus"] = n
    return keluaran(hasil)
