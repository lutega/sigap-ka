"""
Tujuan      : Fungsi baca-tulis database untuk semua lapis (upsert tabel standar, ambil seri,
              ambil prakiraan yang sudah terbit pada jam keputusan, catatan asal data).
Lapis       : Infrastruktur data.
Sumber      : Tabel di db/model.py.
Masukan     : Sesi SQLAlchemy dan DataFrame berformat tabel standar
              (waktu, lokasi, nilai, satuan, sumber, is_simulated).
Keluaran    : Jumlah baris tersimpan atau DataFrame hasil query.
Keterbatasan: Upsert memakai dialek PostgreSQL atau SQLite; dialek lain tidak didukung.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Iterable, Sequence

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.model import (
    Episode,
    JadwalKA,
    Kejadian,
    LaporanLapangan,
    LogPengambilan,
    ObsHujan,
    ObsMukaAir,
    PrakiraanHujan,
    SumberData,
)

KOLOM_STANDAR = ["waktu", "lokasi", "nilai", "satuan", "sumber", "is_simulated"]
UKURAN_POTONGAN = 500  # batasi jumlah parameter per pernyataan (SQLite)


def _bersihkan(nilai: Any) -> Any:
    """Mengubah tipe pandas/numpy ke tipe Python biasa; NaN/NaT menjadi None."""
    if nilai is None:
        return None
    if isinstance(nilai, pd.Timestamp):
        return None if pd.isna(nilai) else nilai.to_pydatetime().replace(tzinfo=None)
    if isinstance(nilai, float) and math.isnan(nilai):
        return None
    if hasattr(nilai, "item"):  # skalar numpy
        nilai = nilai.item()
        if isinstance(nilai, float) and math.isnan(nilai):
            return None
    if nilai is pd.NaT:
        return None
    return nilai


def _df_ke_baris(df: pd.DataFrame, kolom: Iterable[str]) -> list[dict]:
    """Mengubah DataFrame menjadi daftar dict hanya untuk kolom yang dikenal tabel."""
    kolom = [k for k in kolom if k in df.columns]
    return [{k: _bersihkan(v) for k, v in zip(kolom, baris)}
            for baris in df[kolom].itertuples(index=False, name=None)]


def _bawaan_kolom(kolom) -> Any:
    """Nilai bawaan skalar sebuah kolom ORM (None bila tidak ada atau berupa fungsi)."""
    bawaan = kolom.default
    if bawaan is None or callable(getattr(bawaan, "arg", None)):
        return None
    return bawaan.arg


def _upsert(sesi: Session, model: type, baris: Sequence[dict]) -> int:
    """Menyisipkan baris; bila kunci primer sudah ada, nilainya diperbarui (tidak menggandakan).

    Parameter:
        sesi: sesi SQLAlchemy.
        model: kelas ORM tujuan.
        baris: daftar dict kolom -> nilai.
    Kembali:
        Jumlah baris yang dikirim.
    """
    if not baris:
        return 0
    tabel = model.__table__
    dialek = sesi.get_bind().dialect.name
    if dialek == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialek == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:  # pragma: no cover
        raise NotImplementedError(f"upsert belum didukung untuk dialek {dialek}")
    pk = [c.name for c in tabel.primary_key.columns]
    for i in range(0, len(baris), UKURAN_POTONGAN):
        potongan = list(baris[i:i + UKURAN_POTONGAN])
        # Samakan kunci tiap dict agar satu pernyataan VALUES valid.
        semua_kunci = sorted({k for b in potongan for k in b})
        potongan = [{k: b[k] if k in b else _bawaan_kolom(tabel.c[k]) for k in semua_kunci}
                    for b in potongan]
        stmt = insert(tabel).values(potongan)
        perbarui = {k: stmt.excluded[k] for k in semua_kunci if k not in pk}
        stmt = stmt.on_conflict_do_update(index_elements=pk, set_=perbarui) if perbarui \
            else stmt.on_conflict_do_nothing(index_elements=pk)
        sesi.execute(stmt)
    return len(baris)


def _filter_episode(kolom, episode_id: str | Sequence[str] | None):
    """Membuat syarat filter episode_id ('' = observasi umum; None = semua)."""
    if episode_id is None:
        return None
    if isinstance(episode_id, str):
        return kolom == episode_id
    return kolom.in_(list(episode_id))


def _query_df(sesi: Session, stmt) -> pd.DataFrame:
    """Menjalankan select ORM dan mengembalikan DataFrame."""
    hasil = sesi.execute(stmt)
    kolom = list(hasil.keys())  # pertahankan urutan kolom select
    return pd.DataFrame(hasil.fetchall(), columns=kolom)


# ---------------------------------------------------------------- observasi hujan

def simpan_obs_hujan(sesi: Session, df: pd.DataFrame, episode_id: str | None = None,
                     waktu_ambil: datetime | None = None) -> int:
    """Menyimpan tabel standar hujan ke hypertable obs_hujan (upsert).

    Parameter:
        df: kolom wajib waktu, lokasi, nilai, satuan, sumber, is_simulated;
            opsional resolusi_jam (bawaan 24), kualitas, episode_id.
        episode_id: menimpa kolom episode_id bila diberikan.
        waktu_ambil: waktu pengambilan data (bawaan: sekarang).
    Kembali:
        Jumlah baris.
    """
    d = df.copy()
    if episode_id is not None or "episode_id" not in d:
        d["episode_id"] = episode_id or ""
    d["waktu_ambil"] = waktu_ambil or datetime.now()
    if "resolusi_jam" not in d:
        d["resolusi_jam"] = 24
    kolom = [c.name for c in ObsHujan.__table__.columns]
    return _upsert(sesi, ObsHujan, _df_ke_baris(d, kolom))


def ambil_obs_hujan(sesi: Session, lokasi: str | None = None, dari: datetime | None = None,
                    sampai: datetime | None = None, sumber: str | None = None,
                    episode_id: str | Sequence[str] | None = "") -> pd.DataFrame:
    """Mengambil seri hujan berformat standar (ditambah resolusi_jam, episode_id, kualitas).

    Parameter:
        lokasi: 'lokal', 'hulu', 'gundih', atau None untuk semua.
        dari, sampai: rentang waktu (inklusif).
        sumber: nama sumber atau None.
        episode_id: '' observasi umum, id episode, daftar id, atau None untuk semua.
    Kembali:
        DataFrame terurut waktu.
    """
    stmt = select(ObsHujan.waktu, ObsHujan.lokasi, ObsHujan.nilai, ObsHujan.satuan,
                  ObsHujan.sumber, ObsHujan.is_simulated, ObsHujan.resolusi_jam,
                  ObsHujan.episode_id, ObsHujan.kualitas)
    syarat = []
    if lokasi:
        syarat.append(ObsHujan.lokasi == lokasi)
    if dari:
        syarat.append(ObsHujan.waktu >= dari)
    if sampai:
        syarat.append(ObsHujan.waktu <= sampai)
    if sumber:
        syarat.append(ObsHujan.sumber == sumber)
    f = _filter_episode(ObsHujan.episode_id, episode_id)
    if f is not None:
        syarat.append(f)
    if syarat:
        stmt = stmt.where(*syarat)
    df = _query_df(sesi, stmt.order_by(ObsHujan.waktu))
    return df if not df.empty else pd.DataFrame(
        columns=KOLOM_STANDAR + ["resolusi_jam", "episode_id", "kualitas"])


# ---------------------------------------------------------------- prakiraan

def simpan_prakiraan(sesi: Session, df: pd.DataFrame, episode_id: str | None = None,
                     waktu_ambil: datetime | None = None) -> int:
    """Menyimpan prakiraan hujan (upsert).

    Parameter:
        df: kolom waktu_terbit, waktu (= waktu valid, awal periode), lokasi, nilai, satuan,
            sumber, is_simulated; opsional resolusi_jam (bawaan 3), episode_id.
    Kembali:
        Jumlah baris.
    """
    d = df.copy()
    if "waktu_valid" not in d:
        d["waktu_valid"] = d["waktu"]
    if episode_id is not None or "episode_id" not in d:
        d["episode_id"] = episode_id or ""
    d["waktu_ambil"] = waktu_ambil or datetime.now()
    if "resolusi_jam" not in d:
        d["resolusi_jam"] = 3
    kolom = [c.name for c in PrakiraanHujan.__table__.columns]
    return _upsert(sesi, PrakiraanHujan, _df_ke_baris(d, kolom))


def ambil_prakiraan(sesi: Session, lokasi: str | None = None,
                    episode_id: str | Sequence[str] | None = "",
                    terbit_sampai: datetime | None = None, sumber: str | None = None) -> pd.DataFrame:
    """Mengambil semua prakiraan yang terbit paling lambat `terbit_sampai`.

    Kembali:
        DataFrame kolom waktu_terbit, waktu (valid), lokasi, nilai, satuan, sumber,
        is_simulated, resolusi_jam, episode_id.
    """
    stmt = select(PrakiraanHujan.waktu_terbit, PrakiraanHujan.waktu_valid.label("waktu"),
                  PrakiraanHujan.lokasi, PrakiraanHujan.nilai, PrakiraanHujan.satuan,
                  PrakiraanHujan.sumber, PrakiraanHujan.is_simulated,
                  PrakiraanHujan.resolusi_jam, PrakiraanHujan.episode_id)
    syarat = []
    if lokasi:
        syarat.append(PrakiraanHujan.lokasi == lokasi)
    if terbit_sampai:
        syarat.append(PrakiraanHujan.waktu_terbit <= terbit_sampai)
    if sumber:
        syarat.append(PrakiraanHujan.sumber == sumber)
    f = _filter_episode(PrakiraanHujan.episode_id, episode_id)
    if f is not None:
        syarat.append(f)
    if syarat:
        stmt = stmt.where(*syarat)
    df = _query_df(sesi, stmt.order_by(PrakiraanHujan.waktu_terbit, PrakiraanHujan.waktu_valid))
    return df if not df.empty else pd.DataFrame(
        columns=["waktu_terbit"] + KOLOM_STANDAR + ["resolusi_jam", "episode_id"])


def ambil_prakiraan_tersedia(sesi: Session, jam_keputusan: datetime, lokasi: str,
                             episode_id: str | Sequence[str] | None = "",
                             sumber: str | None = None) -> pd.DataFrame:
    """Prakiraan terbitan terakhir yang SUDAH terbit pada jam keputusan (tanpa intip masa depan).

    Parameter:
        jam_keputusan: waktu keputusan (WIB).
        lokasi: lokasi prakiraan.
    Kembali:
        DataFrame berisi baris dari satu waktu terbit (terakhir <= jam_keputusan); kosong bila belum ada.
    """
    df = ambil_prakiraan(sesi, lokasi=lokasi, episode_id=episode_id,
                         terbit_sampai=jam_keputusan, sumber=sumber)
    if df.empty:
        return df
    terakhir = df["waktu_terbit"].max()
    return df[df["waktu_terbit"] == terakhir].reset_index(drop=True)


# ---------------------------------------------------------------- muka air

def simpan_muka_air(sesi: Session, df: pd.DataFrame, episode_id: str | None = None,
                    waktu_ambil: datetime | None = None) -> int:
    """Menyimpan tabel standar muka air (lokasi -> titik, nilai -> elevasi) ke obs_muka_air."""
    d = df.copy().rename(columns={"lokasi": "titik", "nilai": "elevasi"})
    if episode_id is not None or "episode_id" not in d:
        d["episode_id"] = episode_id or ""
    d["waktu_ambil"] = waktu_ambil or datetime.now()
    kolom = [c.name for c in ObsMukaAir.__table__.columns]
    return _upsert(sesi, ObsMukaAir, _df_ke_baris(d, kolom))


def ambil_muka_air(sesi: Session, titik: str | None = None, dari: datetime | None = None,
                   sampai: datetime | None = None, sumber: str | None = None,
                   episode_id: str | Sequence[str] | None = "") -> pd.DataFrame:
    """Mengambil seri muka air dalam format standar (titik -> lokasi, elevasi -> nilai)."""
    stmt = select(ObsMukaAir.waktu, ObsMukaAir.titik.label("lokasi"),
                  ObsMukaAir.elevasi.label("nilai"), ObsMukaAir.satuan, ObsMukaAir.sumber,
                  ObsMukaAir.is_simulated, ObsMukaAir.episode_id, ObsMukaAir.kualitas)
    syarat = []
    if titik:
        syarat.append(ObsMukaAir.titik == titik)
    if dari:
        syarat.append(ObsMukaAir.waktu >= dari)
    if sampai:
        syarat.append(ObsMukaAir.waktu <= sampai)
    if sumber:
        syarat.append(ObsMukaAir.sumber == sumber)
    f = _filter_episode(ObsMukaAir.episode_id, episode_id)
    if f is not None:
        syarat.append(f)
    if syarat:
        stmt = stmt.where(*syarat)
    df = _query_df(sesi, stmt.order_by(ObsMukaAir.waktu))
    return df if not df.empty else pd.DataFrame(columns=KOLOM_STANDAR + ["episode_id", "kualitas"])


# ---------------------------------------------------------------- asal data

def catat_pengambilan(sesi: Session, sumber: str, status: str,
                      rentang_mulai: datetime | None = None,
                      rentang_selesai: datetime | None = None,
                      versi_atau_tautan: str | None = None, jumlah_baris: int = 0,
                      pesan: str | None = None,
                      waktu_ambil: datetime | None = None) -> LogPengambilan:
    """Mencatat satu pengambilan data dan memperbarui status sumber.

    Parameter:
        sumber: nama sumber (kunci di params.json sumber_data).
        status: 'sukses', 'gagal', 'dilewati', atau 'cadangan'.
    Kembali:
        Baris LogPengambilan yang baru.
    """
    waktu_ambil = waktu_ambil or datetime.now()
    log = LogPengambilan(sumber=sumber, waktu_ambil=waktu_ambil, rentang_mulai=rentang_mulai,
                         rentang_selesai=rentang_selesai, versi_atau_tautan=versi_atau_tautan,
                         status=status, jumlah_baris=jumlah_baris, pesan=pesan)
    sesi.add(log)
    sd = sesi.get(SumberData, sumber)
    if sd is not None:
        sd.status_terakhir = status
        sd.waktu_ambil_terakhir = waktu_ambil
    sesi.flush()
    return log


def daftar_sumber(sesi: Session) -> list[dict]:
    """Daftar sumber data beserta status dan waktu ambil terakhir."""
    hasil = []
    for s in sesi.scalars(select(SumberData).order_by(SumberData.nama)):
        hasil.append({
            "nama": s.nama, "jenis": s.jenis, "cara_akses": s.cara_akses,
            "kelompok": s.kelompok, "opsional": s.opsional,
            "status_terakhir": s.status_terakhir, "waktu_ambil_terakhir": s.waktu_ambil_terakhir,
        })
    return hasil


# ---------------------------------------------------------------- kejadian, jadwal

def simpan_kejadian(sesi: Session, df: pd.DataFrame) -> int:
    """Menyimpan katalog kejadian (upsert per id)."""
    kolom = [c.name for c in Kejadian.__table__.columns]
    return _upsert(sesi, Kejadian, _df_ke_baris(df, kolom))


def ambil_kejadian(sesi: Session) -> pd.DataFrame:
    """Mengambil katalog kejadian terurut id."""
    kolom = [c for c in Kejadian.__table__.columns]
    df = _query_df(sesi, select(*kolom).order_by(Kejadian.id))
    return df if not df.empty else pd.DataFrame(columns=[c.name for c in kolom])


def simpan_jadwal(sesi: Session, df: pd.DataFrame) -> int:
    """Menyimpan jadwal KA (upsert per nomor)."""
    kolom = [c.name for c in JadwalKA.__table__.columns]
    return _upsert(sesi, JadwalKA, _df_ke_baris(df, kolom))


def ambil_jadwal(sesi: Session) -> pd.DataFrame:
    """Mengambil jadwal KA terurut jam lewat Gubug."""
    kolom = [c for c in JadwalKA.__table__.columns]
    df = _query_df(sesi, select(*kolom).order_by(JadwalKA.jam_lewat_gubug))
    return df if not df.empty else pd.DataFrame(columns=[c.name for c in kolom])


# ---------------------------------------------------------------- episode, laporan lapangan

def simpan_episode(sesi: Session, data: dict) -> Episode:
    """Menyimpan atau memperbarui satu episode."""
    ep = sesi.merge(Episode(**data))
    sesi.flush()
    return ep


def ambil_episode(sesi: Session, episode_id: str) -> Episode | None:
    """Mengambil satu episode menurut id."""
    return sesi.get(Episode, episode_id)


def daftar_episode(sesi: Session, jenis: str | None = None) -> list[Episode]:
    """Daftar episode (nyata lebih dulu, lalu sintetis), opsional difilter jenis."""
    stmt = select(Episode)
    if jenis:
        stmt = stmt.where(Episode.jenis == jenis)
    return list(sesi.scalars(stmt.order_by(Episode.jenis, Episode.id)))


def simpan_laporan(sesi: Session, baris: Iterable[dict]) -> int:
    """Menyimpan laporan lapangan (air_badan_rel / jalan_putus)."""
    n = 0
    for b in baris:
        sesi.add(LaporanLapangan(**b))
        n += 1
    sesi.flush()
    return n


def hapus_laporan_episode(sesi: Session, episode_id: str) -> None:
    """Menghapus laporan lapangan satu episode (dipakai saat episode dibangun ulang)."""
    sesi.execute(delete(LaporanLapangan).where(LaporanLapangan.episode_id == episode_id))


def ambil_laporan(sesi: Session, episode_id: str | Sequence[str] | None = "",
                  sampai: datetime | None = None, jenis: str | None = None) -> pd.DataFrame:
    """Mengambil laporan lapangan sampai waktu tertentu (tanpa intip masa depan)."""
    stmt = select(LaporanLapangan.waktu, LaporanLapangan.jenis, LaporanLapangan.isi,
                  LaporanLapangan.sumber, LaporanLapangan.is_simulated, LaporanLapangan.episode_id)
    syarat = []
    f = _filter_episode(LaporanLapangan.episode_id, episode_id)
    if f is not None:
        syarat.append(f)
    if sampai:
        syarat.append(LaporanLapangan.waktu <= sampai)
    if jenis:
        syarat.append(LaporanLapangan.jenis == jenis)
    if syarat:
        stmt = stmt.where(*syarat)
    df = _query_df(sesi, stmt.order_by(LaporanLapangan.waktu))
    return df if not df.empty else pd.DataFrame(
        columns=["waktu", "jenis", "isi", "sumber", "is_simulated", "episode_id"])
