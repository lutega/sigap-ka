"""
Tujuan      : Konteks bersama API: engine database, sesi per permintaan, estimator per preset, dan
              cache episode yang dimuat sekali dari database (latensi Docker tinggi); pembersih
              keluaran JSON dan penjaga klaim jalur aman.
Lapis       : API (lapisan tipis di atas modul S, I, G, A).
Sumber      : db/, inference/, simulation/episode.py, action/penjaga_klaim.py.
Masukan     : Objek Request FastAPI.
Keluaran    : Konteks, sesi SQLAlchemy, fungsi keluaran().
Keterbatasan: Cache episode berada di memori proses; dibersihkan saat episode dimuat ulang.
"""

from __future__ import annotations

import math
import threading
from datetime import date, datetime
from typing import Any, Iterator

import numpy as np
from fastapi import HTTPException, Request, status
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from action.penjaga_klaim import pastikan_tanpa_klaim_aman
from config import PRESET_VALID, ParamsAktif, muat_params
from db.koneksi import pabrik_sesi
from inference.estimasi import Estimator, model_bawaan
from simulation.episode import Episode, muat_dari_db


KODE_422 = 422  # konten tidak dapat diproses (nama konstanta berubah antar versi Starlette)


class Konteks:
    """Sumber daya bersama aplikasi."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.pabrik = pabrik_sesi(engine)
        self._episode: dict[str, Episode] = {}
        self._estimator: dict[str, Estimator] = {}
        self._kunci = threading.Lock()

    def params(self, preset: str | None = None) -> ParamsAktif:
        """Parameter preset (bawaan PARAMS_PRESET); 422 bila preset tidak dikenal."""
        if preset is not None and preset not in PRESET_VALID:
            raise HTTPException(KODE_422, f"preset harus salah satu dari {PRESET_VALID}")
        return muat_params(preset)

    def estimator(self, preset: str | None = None) -> Estimator:
        """Estimator lapis I per preset (model dilatih sekali)."""
        params = self.params(preset)
        with self._kunci:
            if params.preset not in self._estimator:
                self._estimator[params.preset] = Estimator(model_bawaan(params.preset), params)
            return self._estimator[params.preset]

    def episode(self, sesi: Session, episode_id: str) -> Episode:
        """Episode dari cache atau database; 404 bila tidak ada."""
        with self._kunci:
            ep = self._episode.get(episode_id)
        if ep is None:
            ep = muat_dari_db(sesi, episode_id)
            if ep is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"episode {episode_id} tidak ditemukan")
            with self._kunci:
                self._episode[episode_id] = ep
        return ep

    def lupakan_episode(self, episode_id: str | None = None) -> None:
        """Menghapus episode dari cache (semua bila None)."""
        with self._kunci:
            if episode_id is None:
                self._episode.clear()
            else:
                self._episode.pop(episode_id, None)


def ambil_konteks(request: Request) -> Konteks:
    """Dependensi: konteks aplikasi."""
    return request.app.state.konteks


def ambil_sesi(request: Request) -> Iterator[Session]:
    """Dependensi: sesi database per permintaan (commit bila sukses, rollback bila galat)."""
    sesi = request.app.state.konteks.pabrik()
    try:
        yield sesi
        sesi.commit()
    except Exception:
        sesi.rollback()
        raise
    finally:
        sesi.close()


def _bersih(obj: Any) -> Any:
    """Mengubah tipe numpy/pandas/datetime menjadi tipe JSON; NaN menjadi None."""
    if isinstance(obj, dict):
        return {str(k): _bersih(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_bersih(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_bersih(v) for v in obj.tolist()]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "isoformat") and callable(obj.isoformat):  # pandas Timestamp
        try:
            return None if str(obj) == "NaT" else obj.isoformat()
        except (ValueError, TypeError):
            return None
    return obj


def keluaran(obj: Any) -> Any:
    """Membersihkan keluaran ke JSON dan memastikan tidak ada klaim jalur aman (FR-A5)."""
    return pastikan_tanpa_klaim_aman(_bersih(obj))


def validasi_jam(params: ParamsAktif, jam_sebelum_t0: int) -> int:
    """Memastikan jam adalah jam keputusan (kelipatan interval, 0..horizon); 422 bila bukan."""
    ep = params.episode
    if jam_sebelum_t0 < 0 or jam_sebelum_t0 > ep.horizon_jam or jam_sebelum_t0 % ep.interval_keputusan_jam:
        raise HTTPException(KODE_422,
                            f"jam harus kelipatan {ep.interval_keputusan_jam} antara 0 dan {ep.horizon_jam}")
    return int(jam_sebelum_t0)
