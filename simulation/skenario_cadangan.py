"""
Tujuan      : Skenario cadangan presentasi (spesifikasi 16): satu episode demo dengan seed tetap yang
              hasilnya selalu sama setiap kali diputar. Modul ini membangun cuplikan lengkap
              (peluang, kurva, status SIGAP per jam, ringkasan T-0 tanpa keputusan operator) dan
              menyimpannya beserta sidik SHA-256 agar keterulangan dapat dibuktikan.
Lapis       : Simulasi (melintasi S-I-G-A).
Sumber      : simulation/episode.episode_cadangan, inference, gating, action.
Masukan     : python -m simulation.skenario_cadangan [--periksa]
Keluaran    : data/processed/demo/skenario_cadangan.json; kode keluar 1 bila --periksa menemukan beda.
Keterbatasan: Sidik berubah bila params.json atau kode model berubah; jalankan ulang tanpa
              --periksa untuk memperbarui cuplikan setelah perubahan yang disengaja.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from action.papan_tindakan import susun_papan
from action.ringkasan import ringkasan_episode
from config import muat_params
from inference.estimasi import Estimator, model_bawaan
from sensing.standar import dir_olahan
from simulation.episode import episode_cadangan


def _bulat(obj):
    """Membulatkan angka ke 6 desimal agar sidik tidak terpengaruh derau titik mengambang."""
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _bulat(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_bulat(v) for v in obj]
    return obj


def bangun_cuplikan(preset: str | None = None) -> dict:
    """Cuplikan deterministik skenario cadangan untuk semua jam keputusan.

    Kembali:
        dict {episode, per_jam[{jam, peluang, status per tindakan, ambang}], ringkasan_t0, sidik}.
    """
    params = muat_params(preset)
    ep = episode_cadangan(params)
    est = Estimator(model_bawaan(params.preset), params)
    per_jam = []
    for k in range(params.episode.jumlah_langkah):
        j = params.episode.jam_sebelum_t0(k)
        p = susun_papan(ep, j, est, [], params)
        per_jam.append({
            "jam_sebelum_t0": j,
            "peluang": p["inferensi"]["peluang"],
            "mekanisme_dominan": p["inferensi"]["mekanisme_dominan"],
            "tindakan": {b["tindakan"]: {"status": b["status"], "ambang": b["ambang"]} for b in p["tindakan"]},
        })
    isi = _bulat({
        "episode": {"id": ep.id, "nama": ep.nama, "t0": ep.t0.isoformat(), "seed": params.demo["seed_cadangan"],
                    "preset": params.preset, "kebenaran": {k: ep.kebenaran[k] for k in ("terganggu", "mekanisme", "skenario_lama_tutup")}},
        "per_jam": per_jam,
        "ringkasan_t0_tanpa_keputusan": ringkasan_episode(ep, est, [], params)["skenario"][0],
    })
    teks = json.dumps(isi, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    isi["sidik_sha256"] = hashlib.sha256(teks.encode("utf-8")).hexdigest()
    return isi


def path_cuplikan() -> Path:
    """Lokasi berkas cuplikan."""
    return dir_olahan() / "demo" / "skenario_cadangan.json"


def simpan(isi: dict) -> Path:
    """Menyimpan cuplikan ke data/processed/demo/skenario_cadangan.json."""
    p = path_cuplikan()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(isi, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return p


def periksa() -> tuple[bool, str, str]:
    """Membangun ulang cuplikan dan membandingkan sidiknya dengan berkas tersimpan.

    Kembali:
        (sama, sidik_baru, sidik_tersimpan).
    """
    baru = bangun_cuplikan()["sidik_sha256"]
    p = path_cuplikan()
    lama = json.loads(p.read_text(encoding="utf-8"))["sidik_sha256"] if p.exists() else ""
    return baru == lama, baru, lama


def main(argv: list[str] | None = None) -> int:
    """CLI: bangun dan simpan cuplikan, atau --periksa keterulangannya."""
    ap = argparse.ArgumentParser(description="Skenario cadangan presentasi SIGAP-KA")
    ap.add_argument("--periksa", action="store_true", help="bandingkan dengan cuplikan tersimpan")
    arg = ap.parse_args(argv)
    if arg.periksa:
        sama, baru, lama = periksa()
        print(f"sidik baru {baru[:16]}..., tersimpan {lama[:16] or '(tidak ada)'}... -> {'SAMA' if sama else 'BERBEDA'}")
        return 0 if sama else 1
    isi = bangun_cuplikan()
    p = simpan(isi)
    print(f"Cuplikan tersimpan: {p} (sidik {isi['sidik_sha256'][:16]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
