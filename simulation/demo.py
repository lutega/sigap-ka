"""
Tujuan      : Mesin status mode demo (spesifikasi 16): memutar ulang satu episode jam demi jam
              (mulai, langkah ke jam keputusan berikutnya, jeda, kecepatan, reset) untuk ujian dan
              presentasi, sepenuhnya offline dari database lokal.
Lapis       : Simulasi (melintasi I-G-A).
Sumber      : Tabel sesi_demo dan keputusan_operator (log bertanda mode='demo').
Masukan     : Sesi database, id episode, pengguna, kecepatan (detik per jam episode).
Keluaran    : Objek SesiDemo dan ringkasan statusnya.
Keterbatasan: Laju otomatis diatur klien (pewaktu memanggil langkah); server menyimpan jam berjalan
              sehingga hasil tidak bergantung jam dinding dan dapat diulang.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from action.log_keputusan import hapus_log_demo
from config import ParamsAktif, muat_params
from db.model import Episode as EpisodeDB
from db.model import SesiDemo

BERJALAN, JEDA, SELESAI = "berjalan", "jeda", "selesai"


class GalatDemo(ValueError):
    """Operasi demo tidak valid (sesi/episode tidak ada, sesi sudah selesai, dsb.)."""


def _sekarang() -> datetime:
    """Waktu lokal tanpa mikrodetik."""
    return datetime.now().replace(microsecond=0)


def ambil(sesi: Session, sesi_id: str) -> SesiDemo:
    """Sesi demo menurut id; galat bila tidak ada."""
    s = sesi.get(SesiDemo, sesi_id)
    if s is None:
        raise GalatDemo("sesi demo tidak ditemukan")
    return s


def mulai(sesi: Session, episode_id: str, username: str, kecepatan: float | None = None,
          params: ParamsAktif | None = None) -> SesiDemo:
    """Membuat sesi demo baru pada awal horizon (T-horizon), status berjalan."""
    params = params or muat_params()
    if sesi.get(EpisodeDB, episode_id) is None:
        raise GalatDemo(f"episode {episode_id} tidak ditemukan")
    s = SesiDemo(id=f"demo-{uuid.uuid4().hex[:10]}", episode_id=episode_id, username=username,
                 jam_sebelum_t0=params.episode.horizon_jam, status=BERJALAN,
                 kecepatan_detik_per_jam=float(kecepatan or params.demo["kecepatan_detik_per_jam"]),
                 dibuat=_sekarang(), diperbarui=_sekarang())
    sesi.add(s)
    sesi.flush()
    return s


def langkah(sesi: Session, sesi_id: str, params: ParamsAktif | None = None) -> SesiDemo:
    """Lompat ke jam keputusan berikutnya; di T-0 status menjadi selesai."""
    params = params or muat_params()
    s = ambil(sesi, sesi_id)
    if s.status == SELESAI:
        raise GalatDemo("episode demo sudah selesai; gunakan reset untuk mengulang")
    s.jam_sebelum_t0 = max(0, s.jam_sebelum_t0 - params.episode.interval_keputusan_jam)
    s.status = SELESAI if s.jam_sebelum_t0 == 0 else BERJALAN
    s.diperbarui = _sekarang()
    sesi.flush()
    return s


def jeda(sesi: Session, sesi_id: str) -> SesiDemo:
    """Menjeda atau melanjutkan sesi (tidak berlaku bila sudah selesai)."""
    s = ambil(sesi, sesi_id)
    if s.status != SELESAI:
        s.status = JEDA if s.status == BERJALAN else BERJALAN
        s.diperbarui = _sekarang()
        sesi.flush()
    return s


def atur_kecepatan(sesi: Session, sesi_id: str, kecepatan: float) -> SesiDemo:
    """Mengubah kecepatan putar (detik per jam episode)."""
    if kecepatan <= 0:
        raise GalatDemo("kecepatan harus > 0")
    s = ambil(sesi, sesi_id)
    s.kecepatan_detik_per_jam = float(kecepatan)
    s.diperbarui = _sekarang()
    sesi.flush()
    return s


def reset(sesi: Session, sesi_id: str, params: ParamsAktif | None = None) -> tuple[SesiDemo, int]:
    """Mengulang episode dari awal dan menghapus log demo sesi ini saja (log lain tidak tersentuh).

    Kembali:
        (sesi, jumlah log demo yang dihapus).
    """
    params = params or muat_params()
    s = ambil(sesi, sesi_id)
    n = hapus_log_demo(sesi, sesi_id)
    s.jam_sebelum_t0 = params.episode.horizon_jam
    s.status = BERJALAN
    s.diperbarui = _sekarang()
    sesi.flush()
    return s, n


def ke_dict(s: SesiDemo, params: ParamsAktif | None = None) -> dict:
    """Ringkasan sesi demo untuk API."""
    params = params or muat_params()
    interval = params.episode.interval_keputusan_jam
    return {
        "id": s.id, "episode_id": s.episode_id, "username": s.username,
        "jam_sebelum_t0": s.jam_sebelum_t0, "status": s.status, "mode": "demo",
        "kecepatan_detik_per_jam": s.kecepatan_detik_per_jam,
        "detik_per_langkah": s.kecepatan_detik_per_jam * interval,
        "jam_berikutnya": None if s.jam_sebelum_t0 == 0 else s.jam_sebelum_t0 - interval,
        "dibuat": s.dibuat, "diperbarui": s.diperbarui,
    }
