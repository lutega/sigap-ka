"""
Tujuan      : Satu perintah untuk membangun ulang konsol (npm run build) dan memeriksa bahwa angka
              yang ditampilkan konsol lewat API sama dengan keluaran model Python untuk tiap preset
              (NFR-3, FR-E3): ambang statis dan kurva pemicu T1-T9, prediksi lapis I, dan ringkasan
              simulasi dengan seed sama.
Lapis       : A (konsol) + QA kesesuaian angka.
Sumber      : dashboard/ (React + Vite), api/main.py (TestClient, SQLite di memori), modul model.
Masukan     : python dashboard/export_dashboard.py [--tanpa-build] [--n 30] [--preset base]
Keluaran    : dashboard/dist/ (disajikan FastAPI di /), laporan kesesuaian; kode keluar 1 bila
              ada angka yang berbeda.
Keterbatasan: Pemeriksaan simulasi memakai jumlah episode kecil agar cepat; seed sama menjamin
              hasil identik untuk N berapa pun.
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
if str(AKAR) not in sys.path:
    sys.path.insert(0, str(AKAR))

TOLERANSI = 1e-6


def bangun(dir_dashboard: Path = AKAR / "dashboard") -> None:
    """Memasang dependensi (bila perlu) dan menjalankan npm run build."""
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm is None:
        raise SystemExit("npm tidak ditemukan; pasang Node.js 20+")
    if not (dir_dashboard / "node_modules").exists():
        subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=dir_dashboard, check=True)
    subprocess.run([npm, "run", "build"], cwd=dir_dashboard, check=True)


def _sama(a: float | None, b: float | None, tol: float = TOLERANSI) -> bool:
    """Perbandingan angka dengan toleransi (None hanya sama dengan None)."""
    if a is None or b is None:
        return a is b
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def cek_kesesuaian(daftar_preset: list[str], n_simulasi: int = 30, seed: int = 7) -> list[dict]:
    """Membandingkan angka API (yang dipakai konsol) dengan model untuk tiap preset.

    Kembali:
        Daftar baris {preset, cek, sesuai, model, api}.
    """
    from fastapi.testclient import TestClient

    from api.main import buat_aplikasi
    from config import muat_params
    from db.koneksi import sesi_dari
    from gating.kurva_pemicu import kurva_untuk_tindakan
    from inference.estimasi import Estimator, model_bawaan
    from simulation.episode import episode_cadangan, simpan_ke_db
    from simulation.evaluasi import simulasi

    hasil = []
    app = buat_aplikasi("sqlite://")
    with TestClient(app) as c:
        ep = episode_cadangan()
        with sesi_dari(app.state.konteks.engine) as s:
            simpan_ke_db(s, ep)
        user, sandi = _admin()
        tok = c.post("/auth/login", json={"username": user, "password": sandi}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        for preset in daftar_preset:
            p = muat_params(preset)
            api_t = {t["id"]: t for t in c.get(f"/tindakan?preset={preset}", headers=h).json()["tindakan"]}
            for t in p.daftar_tindakan():
                ok = _sama(api_t[t.id]["ambang_statis"], t.param.ambang_statis)
                hasil.append({"preset": preset, "cek": f"ambang statis {t.id}", "sesuai": ok,
                              "model": t.param.ambang_statis, "api": api_t[t.id]["ambang_statis"]})
                km = kurva_untuk_tindakan(t, p).ambang
                ka = c.get(f"/kurva/{t.id}?preset={preset}", headers=h).json()["ambang"]
                ok = len(km) == len(ka) and all(_sama(x, y) for x, y in zip(km, ka))
                hasil.append({"preset": preset, "cek": f"kurva pemicu {t.id}", "sesuai": ok,
                              "model": km[0] if km else None, "api": ka[0] if ka else None})
            est = Estimator(model_bawaan(preset), p)
            pm = est.estimasi(ep, 24).peluang
            pa = c.get(f"/episode/{ep.id}/prediksi?jam=24&preset={preset}", headers=h).json()["peluang"]
            hasil.append({"preset": preset, "cek": "prediksi DEMO-CADANGAN T-24", "sesuai": _sama(pm, pa), "model": pm, "api": pa})
            sm = simulasi(n_simulasi, seed, preset).ringkasan["rerata_biaya"]
            run = c.post("/simulasi", json={"preset": preset, "n": n_simulasi, "seed": seed}, headers=h).json()["run_id"]
            sa = c.get(f"/simulasi/{run}", headers=h).json()["ringkasan"]["rerata_biaya"]
            for k in sm:
                hasil.append({"preset": preset, "cek": f"simulasi rerata {k}", "sesuai": _sama(sm[k], sa.get(k), 1e-9),
                              "model": sm[k], "api": sa.get(k)})
    return hasil


def _admin() -> tuple[str, str]:
    """Akun admin dari .env (akun awal database baru)."""
    from config import muat_pengaturan
    p = muat_pengaturan()
    return p.admin_user, p.admin_password


def main(argv: list[str] | None = None) -> int:
    """Titik masuk CLI."""
    ap = argparse.ArgumentParser(description="Bangun konsol SIGAP-KA dan cek kesesuaian angka")
    ap.add_argument("--tanpa-build", action="store_true", help="lewati npm run build")
    ap.add_argument("--preset", nargs="+", default=["low", "base", "high"])
    ap.add_argument("--n", type=int, default=30, help="jumlah episode cek simulasi")
    arg = ap.parse_args(argv)
    if not arg.tanpa_build:
        bangun()
        print("Konsol dibangun: dashboard/dist (disajikan FastAPI di /)")
    laporan = cek_kesesuaian(arg.preset, arg.n)
    beda = [r for r in laporan if not r["sesuai"]]
    for preset in arg.preset:
        baris = [r for r in laporan if r["preset"] == preset]
        print(f"preset {preset}: {sum(r['sesuai'] for r in baris)}/{len(baris)} angka konsol = model")
    for r in beda:
        print(f"  BEDA {r['preset']} {r['cek']}: model={r['model']} api={r['api']}")
    return 1 if beda else 0


if __name__ == "__main__":
    raise SystemExit(main())
