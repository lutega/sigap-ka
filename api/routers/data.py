"""
Tujuan      : Endpoint lapis S: daftar sumber data (status nyata/dummy, waktu ambil terakhir), seri
              hujan, seri muka air, katalog kejadian, dan ringkasan evaluasi pada data nyata
              (validasi IMERG, kejadian kandidat, uji balik).
Lapis       : API -> S (Sensing).
Sumber      : Database (obs_hujan, obs_muka_air, kejadian, sumber_data, log_pengambilan) dan
              sensing/registri.py.
Masukan     : Parameter kueri lokasi, rentang waktu, episode.
Keluaran    : JSON seri berformat standar dengan label is_simulated.
Keterbatasan: Data dibaca dari database lokal (tanpa unduh ulang), sehingga berjalan offline.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import ambil_sesi, keluaran
from auth.dependensi import pengguna_aktif
from config import muat_params
from db import repositori as repo
from db.model import LogPengambilan
from sensing.registri import status_sumber
from simulation.ringkasan_nyata import muat_ringkasan

router = APIRouter(prefix="/data", tags=["data"], dependencies=[Depends(pengguna_aktif)])


def _baris(df, kolom: list[str]) -> list[dict]:
    """DataFrame menjadi daftar dict untuk kolom yang ada."""
    if df is None or df.empty:
        return []
    kolom = [k for k in kolom if k in df.columns]
    return df[kolom].to_dict("records")


@router.get("/sumber")
def sumber(sesi: Session = Depends(ambil_sesi)):
    """Daftar sumber data: kelompok inti/tambahan, kesiapan, status dan waktu ambil terakhir."""
    db = {s["nama"]: s for s in repo.daftar_sumber(sesi)}
    jumlah_log = dict(sesi.execute(select(LogPengambilan.sumber, func.count()).group_by(LogPengambilan.sumber)).all())
    hasil = []
    for s in status_sumber():
        d = db.get(s["nama"], {})
        hasil.append({**s, "status_terakhir": d.get("status_terakhir"),
                      "waktu_ambil_terakhir": d.get("waktu_ambil_terakhir"),
                      "jumlah_pengambilan": int(jumlah_log.get(s["nama"], 0)),
                      "label": "dummy" if s["nama"] in ("dummy_generator", "muka_air_sintetis") else "nyata"})
    return keluaran(hasil)


@router.get("/hujan")
def hujan(lokasi: str | None = Query(None, description="lokal, hulu, atau gundih"),
          dari: datetime | None = None, sampai: datetime | None = None, sumber: str | None = None,
          episode_id: str = Query("", description="'' = observasi umum (nyata), atau id episode"),
          sesi: Session = Depends(ambil_sesi)):
    """Seri hujan lokal/hulu/Gundih (mm) berlabel is_simulated."""
    df = repo.ambil_obs_hujan(sesi, lokasi=lokasi, dari=dari, sampai=sampai, sumber=sumber, episode_id=episode_id)
    return keluaran(_baris(df, ["waktu", "lokasi", "nilai", "satuan", "sumber", "is_simulated", "resolusi_jam"]))


@router.get("/muka-air")
def muka_air(titik: str | None = Query(None, description="glapan atau badan_rel"),
             episode_id: str | None = Query(None, description="id episode untuk muka air sintetisnya"),
             sesi: Session = Depends(ambil_sesi)):
    """Muka air Glapan nyata (rilis BNPB) dan, bila diminta, muka air sintetis episode."""
    daftar = [""] if not episode_id else ["", episode_id]
    df = repo.ambil_muka_air(sesi, titik=titik, episode_id=daftar)
    awas = muat_params().muka_air["ambang_awas"]
    return keluaran({
        "seri": _baris(df, ["waktu", "lokasi", "nilai", "satuan", "sumber", "is_simulated", "episode_id"]),
        "ambang_awas": awas,
        "catatan": f"Ambang Awas {awas} dan titik nyata Glapan dari rilis BNPB; seri bersumber muka_air_sintetis adalah sintetis.",
    })


@router.get("/kejadian")
def kejadian(sesi: Session = Depends(ambil_sesi)):
    """Katalog kejadian gangguan (E1-E6 dst.)."""
    df = repo.ambil_kejadian(sesi)
    return keluaran(_baris(df, ["id", "tanggal", "jam_tutup", "jam_buka", "lokasi_km", "mekanisme",
                                "ka_terdampak", "sumber", "metode", "status_konfirmasi", "kode_periksa",
                                "is_simulated", "catatan"]))


@router.get("/jadwal")
def jadwal(sesi: Session = Depends(ambil_sesi)):
    """Jadwal KA yang melewati Gubug (placeholder dummy sampai jadwal publik diisi)."""
    return keluaran(_baris(repo.ambil_jadwal(sesi), ["nomor", "relasi", "jam_lewat_gubug", "sumber", "is_simulated"]))


@router.get("/evaluasi-nyata")
def evaluasi_nyata():
    """Ringkasan evaluasi pada data nyata: validasi IMERG vs BMKG, kejadian kandidat dari berita
    (tanpa tautan lengkap), uji balik, AUC dengan selang 95%, kepekaan bias, realisme generator."""
    return keluaran(muat_ringkasan())
