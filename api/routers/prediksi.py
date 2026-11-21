"""
Tujuan      : Endpoint episode dan lapis I: daftar episode untuk diputar ulang, detail seri episode
              sampai jam tertentu, prediksi (peluang, mekanisme, lama tutup) pada jam keputusan, dan
              lintasan peluang sampai jam berjalan.
Lapis       : API -> I (Inferensi).
Sumber      : Tabel episode, simulation/episode.py, inference/estimasi.py.
Masukan     : id episode, jam keputusan (jam sebelum T-0), preset.
Keluaran    : JSON hasil lapis I dan seri episode berlabel nyata/dummy.
Keterbatasan: Data dan lintasan dipotong pada jam yang diminta sehingga tidak ada intip masa depan.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import Konteks, ambil_konteks, ambil_sesi, keluaran, validasi_jam
from auth.dependensi import pengguna_aktif
from db import repositori as repo

router = APIRouter(prefix="/episode", tags=["episode dan prediksi"], dependencies=[Depends(pengguna_aktif)])


@router.get("")
def daftar_episode(sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks)):
    """Daftar episode yang dapat diputar ulang (nyata lebih dulu), dengan label nyata/sintetis."""
    p = kt.params()
    jam = [p.episode.jam_sebelum_t0(k) for k in range(p.episode.jumlah_langkah)]
    hasil = [{
        "id": e.id, "nama": e.nama, "jenis": e.jenis, "t0": e.t0, "status_hasil": e.status_hasil,
        "is_simulated": e.is_simulated, "keterangan": e.keterangan,
        "label": "nyata (sebagian seri sintetis)" if e.jenis == "nyata" else "sintetis",
        "jam_keputusan": jam,
    } for e in sorted(repo.daftar_episode(sesi), key=lambda e: (e.jenis != "nyata", e.id))]
    return keluaran(hasil)


def _potong(df: pd.DataFrame, kolom_waktu: str, batas) -> pd.DataFrame:
    """Baris dengan waktu <= batas (tanpa intip masa depan)."""
    if df is None or df.empty or batas is None:
        return df
    return df[pd.to_datetime(df[kolom_waktu]) <= pd.Timestamp(batas)]


@router.get("/{episode_id}")
def detail_episode(episode_id: str, sampai_jam: int | None = Query(None, description="jam sebelum T-0; data sesudahnya disembunyikan"),
                   sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks)):
    """Seri episode (hujan, prakiraan terbitan terakhir, muka air, laporan) sampai jam tertentu."""
    ep = kt.episode(sesi, episode_id)
    batas = None
    if sampai_jam is not None:
        validasi_jam(kt.params(), sampai_jam)
        batas = ep.t0 - timedelta(hours=sampai_jam)
    hujan = _potong(ep.hujan, "waktu", batas)
    pk = _potong(ep.prakiraan, "waktu_terbit", batas)
    if pk is not None and len(pk):
        pk = pk[pk["waktu_terbit"] == pk["waktu_terbit"].max()]
    ma = _potong(ep.muka_air, "waktu", batas)
    lap = _potong(ep.laporan, "waktu", batas)
    kol = ["waktu", "lokasi", "nilai", "sumber", "is_simulated"]
    return keluaran({
        "id": ep.id, "nama": ep.nama, "jenis": ep.jenis, "t0": ep.t0, "status_hasil": ep.status_hasil,
        "keterangan": ep.keterangan, "label_seri": ep.label_seri,
        "hujan": hujan[kol + ["resolusi_jam"]].to_dict("records") if len(hujan) else [],
        "prakiraan_terakhir": pk[["waktu_terbit"] + kol].to_dict("records") if pk is not None and len(pk) else [],
        "muka_air": ma[kol].to_dict("records") if len(ma) else [],
        "laporan": lap.to_dict("records") if len(lap) else [],
        "sampai_jam": sampai_jam,
    })


@router.get("/{episode_id}/prediksi")
def prediksi(episode_id: str, jam: int = Query(..., description="jam keputusan sebagai jam sebelum T-0, mis. 24"),
             preset: str | None = None, sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks)):
    """Peluang gangguan, peluang per mekanisme, sebaran lama tutup, dan bukti utama pada jam keputusan."""
    validasi_jam(kt.params(preset), jam)
    ep = kt.episode(sesi, episode_id)
    return keluaran(kt.estimator(preset).estimasi(ep, jam).ke_dict())


@router.get("/{episode_id}/lintasan")
def lintasan(episode_id: str, sampai_jam: int = Query(0, description="lintasan dari awal horizon sampai jam ini"),
             preset: str | None = None, sesi: Session = Depends(ambil_sesi), kt: Konteks = Depends(ambil_konteks)):
    """Peluang gangguan per jam keputusan sampai jam berjalan (untuk grafik peluang vs kurva)."""
    params = kt.params(preset)
    validasi_jam(params, sampai_jam)
    ep = kt.episode(sesi, episode_id)
    est = kt.estimator(preset)
    hasil = []
    for k in range(params.episode.jumlah_langkah):
        j = params.episode.jam_sebelum_t0(k)
        if j < sampai_jam:
            break
        h = est.estimasi(ep, j)
        hasil.append({"jam_sebelum_t0": j, "peluang": h.peluang, "peluang_genangan": h.peluang_genangan,
                      "peluang_gerusan": h.peluang_gerusan, "faktor_L": h.lama_tutup["faktor_L"]})
    return keluaran(hasil)
