"""
Tujuan      : CLI simulasi kebijakan: menjalankan N episode untuk enam kebijakan per preset,
              metrik deteksi leave-one-episode-out, uji sensitivitas biaya menunggu, dan menyimpan
              hasil ke data/processed/simulasi/ serta tabel hasil_simulasi/simulasi_run.
Lapis       : Simulasi/evaluasi.
Sumber      : simulation/evaluasi.py.
Masukan     : Contoh:
                python -m simulation.jalankan --preset base --n 300 --seed 42
                python -m simulation.jalankan --semua-preset --loeo 100 --sensitivitas --simpan-db
Keluaran    : CSV biaya per episode, JSON ringkasan, baris database (opsional).
Keterbatasan: Hasil memakai parameter dummy dan episode sintetis (batas atas menurut asumsi sendiri).
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime

from config import muat_pengaturan
from sensing.standar import dir_olahan
from simulation.episode import episode_sintetis
from simulation.evaluasi import HasilSimulasi, evaluasi_deteksi, sensitivitas_diskon, simulasi


def simpan_hasil_db(sesi, run_id: str, hasil: HasilSimulasi, status: str = "selesai",
                    dibuat: datetime | None = None, tambahan: dict | None = None) -> None:
    """Menyimpan biaya per episode per kebijakan dan ringkasan run ke database."""
    from db.model import HasilSimulasi as HasilDB
    from db.model import SimulasiRun
    sesi.merge(SimulasiRun(run_id=run_id, preset=hasil.preset, seed=hasil.seed,
                           jumlah_episode=hasil.jumlah_episode, status=status,
                           dibuat=dibuat or datetime.now().replace(microsecond=0),
                           selesai=datetime.now().replace(microsecond=0),
                           ringkasan={**hasil.ringkasan, **(tambahan or {})}))
    sesi.bulk_save_objects([
        HasilDB(run_id=run_id, preset=hasil.preset, seed=hasil.seed, kebijakan=r.kebijakan,
                episode_ke=int(r.episode_ke), biaya=float(r.biaya), terganggu=bool(r.terganggu))
        for r in hasil.biaya.itertuples()])


def simpan_berkas(hasil: HasilSimulasi, tambahan: dict | None = None) -> tuple[str, str]:
    """Menyimpan CSV biaya dan JSON ringkasan ke data/processed/simulasi/."""
    folder = dir_olahan() / "simulasi"
    folder.mkdir(parents=True, exist_ok=True)
    dasar = f"{hasil.preset}_n{hasil.jumlah_episode}_seed{hasil.seed}"
    csv = folder / f"biaya_{dasar}.csv"
    hasil.biaya.to_csv(csv, index=False, encoding="utf-8", lineterminator="\n")
    js = folder / f"ringkasan_{dasar}.json"
    js.write_text(json.dumps({**hasil.ringkasan, **(tambahan or {})}, ensure_ascii=False, indent=2),
                  encoding="utf-8")
    return str(csv), str(js)


def main(argv: list[str] | None = None) -> None:
    """Titik masuk CLI."""
    ap = argparse.ArgumentParser(description="Simulasi kebijakan SIGAP-KA")
    ap.add_argument("--preset", default=None, choices=["low", "base", "high"])
    ap.add_argument("--semua-preset", action="store_true")
    ap.add_argument("--n", type=int, default=None, help="jumlah episode (bawaan params: 300)")
    ap.add_argument("--seed", type=int, default=None, help="bawaan SIM_SEED")
    ap.add_argument("--loeo", type=int, default=0, help="jumlah episode untuk metrik deteksi LOEO (0 = lewati)")
    ap.add_argument("--sensitivitas", action="store_true", help="uji sensitivitas diskon biaya awal")
    ap.add_argument("--simpan-db", action="store_true")
    arg = ap.parse_args(argv)

    seed = muat_pengaturan().sim_seed if arg.seed is None else arg.seed
    daftar = ["low", "base", "high"] if arg.semua_preset else [arg.preset or muat_pengaturan().params_preset]
    for preset in daftar:
        hasil = simulasi(arg.n, seed, preset)
        tambahan = {}
        if arg.loeo:
            tambahan["metrik_deteksi"] = evaluasi_deteksi(episode_sintetis(arg.loeo, seed + 1, preset))
        if arg.sensitivitas:
            sens = sensitivitas_diskon([0.0, 0.02, 0.05, 0.10], episode_sintetis(hasil.jumlah_episode, seed, preset), preset)
            tambahan["sensitivitas_diskon"] = sens.to_dict("records")
        csv, js = simpan_berkas(hasil, tambahan)
        print(f"\n== preset {preset}, {hasil.jumlah_episode} episode, seed {seed}")
        print(hasil.tabel_ringkas().round(1).to_string())
        print(f"SIGAP vs pembanding terbaik ({hasil.ringkasan['pembanding_terbaik']}): "
              f"{hasil.ringkasan['sigap_vs_pembanding_terbaik_persen']:+.2f}%")
        if "metrik_deteksi" in tambahan:
            for nama, m in tambahan["metrik_deteksi"].items():
                print(f"  {nama:<20} POD {m['POD']:.2f} FAR {m['FAR']:.2f} CSI {m['CSI']:.2f} lead {m['lead_time_jam']:.1f} jam")
        if "sensitivitas_diskon" in tambahan:
            for r in tambahan["sensitivitas_diskon"]:
                print(f"  diskon {r['diskon']:.2f}: SIGAP {r['sigap']:.0f}, terbaik {r['pembanding_terbaik']} "
                      f"({r['sigap_vs_terbaik_persen']:+.2f}%)")
        print(f"Tersimpan: {csv}, {js}")
        if arg.simpan_db:
            from db.inisialisasi import inisialisasi
            from db.koneksi import buat_engine, sesi_dari
            engine = buat_engine()
            inisialisasi(engine)
            with sesi_dari(engine) as sesi:
                simpan_hasil_db(sesi, f"cli-{uuid.uuid4().hex[:8]}", hasil, tambahan=tambahan)


if __name__ == "__main__":
    main()
