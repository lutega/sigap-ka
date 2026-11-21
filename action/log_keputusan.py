"""
Tujuan      : Mencatat dan membaca keputusan operator (Setujui, Tolak, Batalkan) beserta waktu,
              status SIGAP saat itu, identitas operator, dan alasan; menentukan tindakan yang
              sedang berlaku disetujui pada jam keputusan.
Lapis       : A (Aksi).
Sumber      : Tabel keputusan_operator (db/model.py); spesifikasi 12.1, 15, 16.
Masukan     : Sesi database, data keputusan.
Keluaran    : Baris log; peta tindakan -> jam disetujui.
Keterbatasan: Keputusan diikat ke jam episode (jam sebelum T-0), bukan jam dinding; pembatalan
              menghapus efek persetujuan sebelumnya. Log demo ditandai mode='demo'.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from config import ID_TINDAKAN
from db.model import KeputusanOperator
from gating.status import DISETUJUI, TERLAMBAT

KEPUTUSAN_VALID = ("setujui", "tolak", "batalkan")


class KeputusanTidakValid(ValueError):
    """Keputusan tidak dapat dicatat (mis. batas waktu lewat, belum disetujui untuk dibatalkan)."""


def _ke_dict(k: KeputusanOperator) -> dict:
    """Baris ORM menjadi dict."""
    return {
        "id": k.id, "episode_id": k.episode_id, "tindakan_id": k.tindakan_id,
        "jam_sebelum_t0": k.jam_sebelum_t0, "waktu_dicatat": k.waktu_dicatat,
        "status_sigap": k.status_sigap, "keputusan": k.keputusan, "alasan": k.alasan,
        "username": k.username, "mode": k.mode, "sesi_demo_id": k.sesi_demo_id,
        "peluang": k.peluang, "nilai_kurva": k.nilai_kurva,
    }


def tindakan_disetujui(log: list[dict], sampai_jam_sebelum_t0: int | None = None) -> dict[str, int]:
    """Tindakan yang berlaku disetujui pada jam keputusan tertentu.

    Hanya keputusan yang dibuat pada jam yang sama atau lebih awal (jam sebelum T-0 >= jam ini)
    yang dihitung, diproses berurutan waktu episode: 'setujui' menetapkan, 'batalkan' menghapus.
    Kembali:
        dict id tindakan -> jam sebelum T-0 saat disetujui.
    """
    urut = sorted(log, key=lambda r: (-r["jam_sebelum_t0"], r.get("id") or 0))
    aktif: dict[str, int] = {}
    for r in urut:
        if sampai_jam_sebelum_t0 is not None and r["jam_sebelum_t0"] < sampai_jam_sebelum_t0:
            continue
        if r["keputusan"] == "setujui":
            aktif.setdefault(r["tindakan_id"], r["jam_sebelum_t0"])
        elif r["keputusan"] == "batalkan":
            aktif.pop(r["tindakan_id"], None)
    return aktif


def daftar(sesi: Session, episode_id: str, mode: str | None = None,
           sesi_demo_id: str | None = None, username: str | None = None) -> list[dict]:
    """Log keputusan satu episode, opsional difilter mode/sesi demo/username."""
    stmt = select(KeputusanOperator).where(KeputusanOperator.episode_id == episode_id)
    if mode:
        stmt = stmt.where(KeputusanOperator.mode == mode)
    if sesi_demo_id is not None:
        stmt = stmt.where(KeputusanOperator.sesi_demo_id == sesi_demo_id)
    elif mode == "normal":
        stmt = stmt.where(KeputusanOperator.sesi_demo_id.is_(None))
    if username:
        stmt = stmt.where(KeputusanOperator.username == username)
    return [_ke_dict(k) for k in sesi.scalars(stmt.order_by(KeputusanOperator.id))]


def catat(sesi: Session, episode_id: str, tindakan_id: str, jam_sebelum_t0: int, keputusan: str,
          username: str, status_sigap: str, peluang: float | None = None,
          nilai_kurva: float | None = None, alasan: str | None = None, mode: str = "normal",
          sesi_demo_id: str | None = None) -> dict:
    """Mencatat satu keputusan operator setelah divalidasi.

    Galat:
        KeputusanTidakValid bila keputusan/tindakan tidak dikenal, menyetujui tindakan yang batas
        waktunya lewat atau sudah disetujui, atau membatalkan yang belum disetujui.
    """
    if keputusan not in KEPUTUSAN_VALID:
        raise KeputusanTidakValid(f"keputusan harus salah satu dari {KEPUTUSAN_VALID}")
    if tindakan_id not in ID_TINDAKAN:
        raise KeputusanTidakValid(f"tindakan tidak dikenal: {tindakan_id}")
    log = daftar(sesi, episode_id, mode=mode, sesi_demo_id=sesi_demo_id)
    aktif = tindakan_disetujui(log, jam_sebelum_t0)
    if keputusan == "setujui":
        if status_sigap == TERLAMBAT:
            raise KeputusanTidakValid("batas waktu siap tindakan sudah lewat")
        if tindakan_id in aktif or status_sigap == DISETUJUI:
            raise KeputusanTidakValid("tindakan sudah disetujui; batalkan dulu bila ingin mengubah")
    if keputusan == "batalkan" and tindakan_id not in aktif:
        raise KeputusanTidakValid("tindakan belum disetujui sehingga tidak dapat dibatalkan")
    baris = KeputusanOperator(
        episode_id=episode_id, tindakan_id=tindakan_id, jam_sebelum_t0=int(jam_sebelum_t0),
        waktu_dicatat=datetime.now().replace(microsecond=0), status_sigap=status_sigap,
        keputusan=keputusan, alasan=alasan, username=username, mode=mode,
        sesi_demo_id=sesi_demo_id, peluang=peluang, nilai_kurva=nilai_kurva,
    )
    sesi.add(baris)
    sesi.flush()
    return _ke_dict(baris)


def hapus_log_demo(sesi: Session, sesi_demo_id: str) -> int:
    """Menghapus log bertanda mode='demo' milik satu sesi demo saja (spesifikasi 16)."""
    hasil = sesi.execute(delete(KeputusanOperator).where(
        KeputusanOperator.mode == "demo", KeputusanOperator.sesi_demo_id == sesi_demo_id))
    return int(hasil.rowcount or 0)
