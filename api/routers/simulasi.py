"""
Tujuan      : Endpoint simulasi: menjalankan N episode untuk enam kebijakan sebagai tugas latar
              belakang (khusus admin) dan mengambil hasilnya.
Lapis       : API -> evaluasi.
Sumber      : simulation/evaluasi.py, simulation/jalankan.py, tabel simulasi_run dan hasil_simulasi.
Masukan     : preset, jumlah episode, seed.
Keluaran    : run_id; status dan ringkasan biaya per kebijakan.
Keterbatasan: Tugas latar belakang berjalan di proses API (bukan antrean terpisah); cocok untuk
              prototipe. Angka memakai parameter dummy.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import Konteks, ambil_konteks, ambil_sesi, keluaran
from api.schemas import SimulasiMasuk
from auth.dependensi import pengguna_aktif, wajib_admin
from config import muat_pengaturan
from db.model import HasilSimulasi, SimulasiRun
from simulation.evaluasi import simulasi as jalankan_simulasi
from simulation.jalankan import simpan_hasil_db

router = APIRouter(prefix="/simulasi", tags=["simulasi"])


def _kerjakan(kt: Konteks, run_id: str, preset: str, n: int, seed: int) -> None:
    """Tugas latar belakang: jalankan simulasi lalu simpan hasil; status gagal bila galat."""
    with kt.pabrik() as sesi:
        run = sesi.get(SimulasiRun, run_id)
        run.status = "berjalan"
        sesi.commit()
        dibuat = run.dibuat
    try:
        hasil = jalankan_simulasi(n, seed, preset, estimator=kt.estimator(preset))
        with kt.pabrik() as sesi:
            simpan_hasil_db(sesi, run_id, hasil, dibuat=dibuat)
            sesi.commit()
    except Exception as galat:  # dicatat agar admin melihat penyebabnya
        with kt.pabrik() as sesi:
            run = sesi.get(SimulasiRun, run_id)
            run.status, run.pesan = "gagal", f"{galat.__class__.__name__}: {galat}"
            run.selesai = datetime.now().replace(microsecond=0)
            sesi.commit()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def mulai(masuk: SimulasiMasuk, latar: BackgroundTasks, sesi: Session = Depends(ambil_sesi),
          kt: Konteks = Depends(ambil_konteks), admin: dict = Depends(wajib_admin)):
    """Menjalankan simulasi N episode untuk enam kebijakan (tugas latar belakang)."""
    params = kt.params(masuk.preset)
    seed = muat_pengaturan().sim_seed if masuk.seed is None else masuk.seed
    run_id = f"run-{uuid.uuid4().hex[:10]}"
    sesi.add(SimulasiRun(run_id=run_id, preset=params.preset, seed=seed, jumlah_episode=masuk.n,
                         status="antre", dibuat=datetime.now().replace(microsecond=0)))
    sesi.commit()
    latar.add_task(_kerjakan, kt, run_id, params.preset, masuk.n, seed)
    return keluaran({"run_id": run_id, "status": "antre", "preset": params.preset, "seed": seed, "n": masuk.n})


@router.get("")
def daftar(sesi: Session = Depends(ambil_sesi), pengguna: dict = Depends(pengguna_aktif)):
    """Daftar run simulasi (terbaru lebih dulu)."""
    runs = sesi.scalars(select(SimulasiRun).order_by(SimulasiRun.dibuat.desc())).all()
    return keluaran([{"run_id": r.run_id, "preset": r.preset, "seed": r.seed, "n": r.jumlah_episode,
                      "status": r.status, "dibuat": r.dibuat, "selesai": r.selesai} for r in runs])


@router.get("/{run_id}")
def hasil(run_id: str, sesi: Session = Depends(ambil_sesi), pengguna: dict = Depends(pengguna_aktif)):
    """Status dan hasil simulasi: rerata/median biaya per kebijakan dan ringkasan."""
    run = sesi.get(SimulasiRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run simulasi tidak ditemukan")
    statistik = sesi.execute(
        select(HasilSimulasi.kebijakan, func.avg(HasilSimulasi.biaya), func.min(HasilSimulasi.biaya),
               func.max(HasilSimulasi.biaya), func.count())
        .where(HasilSimulasi.run_id == run_id).group_by(HasilSimulasi.kebijakan)).all()
    return keluaran({
        "run_id": run.run_id, "preset": run.preset, "seed": run.seed, "n": run.jumlah_episode,
        "status": run.status, "dibuat": run.dibuat, "selesai": run.selesai, "pesan": run.pesan,
        "ringkasan": run.ringkasan,
        "per_kebijakan": [{"kebijakan": k, "rerata": a, "minimum": mn, "maksimum": mx, "jumlah_episode": c}
                          for k, a, mn, mx, c in statistik],
    })
