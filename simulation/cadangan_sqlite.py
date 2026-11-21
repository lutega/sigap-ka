"""
Tujuan      : Cadangan presentasi tanpa Docker: membangun satu berkas SQLite berisi data olahan
              nyata, episode demo, dan hasil simulasi ketiga preset, sehingga API dan konsol tetap
              dapat didemokan bila PostgreSQL/TimescaleDB atau jaringan Docker bermasalah.
Lapis       : Simulasi/infrastruktur (cadangan mode demo, spesifikasi 16).
Sumber      : data/processed (NASA POWER, Glapan, kejadian, jadwal), simulation/episode.py,
              simulation/evaluasi.py.
Masukan     : python -m simulation.cadangan_sqlite [--berkas data/demo_cadangan.sqlite] [--n 300]
Keluaran    : Berkas SQLite; jalankan API dengan DATABASE_URL=sqlite:///data/demo_cadangan.sqlite
Keterbatasan: SQLite tidak punya hypertable/continuous aggregate (tidak dipakai API); hanya untuk
              cadangan demo, bukan pengganti TimescaleDB.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from config import AKAR_REPO, PRESET_VALID, muat_pengaturan

BERKAS_BAWAAN = AKAR_REPO / "data" / "demo_cadangan.sqlite"


def bangun(berkas: Path = BERKAS_BAWAAN, n: int = 300) -> dict:
    """Membuat berkas SQLite cadangan lengkap.

    Parameter:
        berkas: lokasi berkas (ditimpa bila sudah ada).
        n: jumlah episode simulasi per preset.
    Kembali:
        Ringkasan isi (jumlah baris, episode, run simulasi).
    """
    from sqlalchemy import create_engine

    from db.inisialisasi import inisialisasi
    from db.koneksi import sesi_dari
    from sensing.jalankan import muat_ke_db
    from simulation.episode import siapkan_episode_demo
    from simulation.evaluasi import simulasi
    from simulation.jalankan import simpan_hasil_db

    berkas = Path(berkas)
    berkas.parent.mkdir(parents=True, exist_ok=True)
    if berkas.exists():
        berkas.unlink()
    engine = create_engine(f"sqlite:///{berkas.as_posix()}")
    inisialisasi(engine)
    jumlah = muat_ke_db(engine)
    episode = siapkan_episode_demo(engine)
    runs = []
    seed = muat_pengaturan().sim_seed
    for preset in PRESET_VALID:
        h = simulasi(n, seed, preset)
        run_id = f"cadangan-{preset}-{uuid.uuid4().hex[:6]}"
        with sesi_dari(engine) as sesi:
            simpan_hasil_db(sesi, run_id, h)
        runs.append(run_id)
    engine.dispose()
    return {"berkas": str(berkas), "data": jumlah, "episode": episode, "simulasi": runs}


def main(argv: list[str] | None = None) -> None:
    """CLI."""
    ap = argparse.ArgumentParser(description="Bangun basis data SQLite cadangan presentasi")
    ap.add_argument("--berkas", type=Path, default=BERKAS_BAWAAN)
    ap.add_argument("--n", type=int, default=300)
    arg = ap.parse_args(argv)
    hasil = bangun(arg.berkas, arg.n)
    print(f"Cadangan SQLite siap: {hasil['berkas']}")
    print(f"  data: {hasil['data']}")
    print(f"  episode: {hasil['episode']}")
    print(f"Jalankan: DATABASE_URL=sqlite:///{Path(hasil['berkas']).as_posix()} "
          "python -m uvicorn api.main:app --host 127.0.0.1 --port 8765")


if __name__ == "__main__":
    main()
