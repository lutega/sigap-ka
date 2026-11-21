"""
Tujuan      : Membuat engine dan sesi SQLAlchemy untuk database SIGAP-KA.
Lapis       : Infrastruktur data (dipakai S, A, simulasi, API).
Sumber      : DATABASE_URL di .env (PostgreSQL + TimescaleDB dari docker compose);
              SQLite di memori untuk tes unit.
Masukan     : URL database.
Keluaran    : Engine, sessionmaker, dan context manager sesi.
Keterbatasan: SQLite tidak punya fitur TimescaleDB; hanya untuk tes dan pengembangan cepat.
"""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from config import muat_pengaturan


def normalisasi_url(url: str) -> str:
    """Memastikan URL PostgreSQL memakai driver psycopg versi 3.

    Parameter:
        url: URL dari .env, misalnya 'postgresql://user:pw@host:5432/db'.
    Kembali:
        URL dengan skema 'postgresql+psycopg://' bila belum menyebut driver.
    """
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


def buat_engine(url: str | None = None, echo: bool = False, tanpa_pool: bool = False) -> Engine:
    """Membuat engine SQLAlchemy.

    Parameter:
        url: URL database; bila kosong memakai DATABASE_URL dari .env.
             'sqlite://' membuat database di memori yang dibagi satu koneksi.
        echo: cetak SQL (untuk debug).
        tanpa_pool: buka koneksi baru untuk tiap pemakaian (NullPool). Dipakai tes integrasi
             karena penerus port Docker Desktop di Windows dapat meninggalkan koneksi
             "setengah terbuka" yang membuat ping pool menunggu tanpa batas.
    Kembali:
        Engine SQLAlchemy.
    """
    url = normalisasi_url(url or muat_pengaturan().database_url)
    if url.startswith("sqlite"):
        if url in ("sqlite://", "sqlite:///:memory:"):
            return create_engine(
                url,
                echo=echo,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,  # satu koneksi agar database memori tetap hidup
            )
        # berkas SQLite (cadangan demo): pool biasa agar permintaan paralel konsol aman
        return create_engine(url, echo=echo, connect_args={"check_same_thread": False, "timeout": 30})
    # Batas waktu koneksi agar tidak menggantung bila database tidak menjawab; koneksi pool didaur
    # ulang tiap 60 detik agar koneksi lama yang mungkin sudah diputus penerus port tidak dipakai.
    opsi = {"connect_args": {"connect_timeout": 10}}
    if tanpa_pool:
        return create_engine(url, echo=echo, poolclass=NullPool, **opsi)
    return create_engine(url, echo=echo, pool_pre_ping=True, pool_recycle=60, **opsi)


def adalah_postgres(engine: Engine) -> bool:
    """True bila engine terhubung ke PostgreSQL (fitur TimescaleDB tersedia)."""
    return engine.dialect.name == "postgresql"


def pabrik_sesi(engine: Engine) -> sessionmaker[Session]:
    """Membuat pabrik sesi untuk engine tertentu."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def sesi_dari(engine: Engine) -> Iterator[Session]:
    """Context manager sesi: commit bila sukses, rollback bila galat.

    Parameter:
        engine: engine SQLAlchemy.
    Kembali:
        Sesi yang otomatis ditutup.
    """
    sesi = pabrik_sesi(engine)()
    try:
        yield sesi
        sesi.commit()
    except Exception:
        sesi.rollback()
        raise
    finally:
        sesi.close()


@lru_cache(maxsize=1)
def engine_bawaan() -> Engine:
    """Engine dari DATABASE_URL di .env, dibuat sekali."""
    return buat_engine()
