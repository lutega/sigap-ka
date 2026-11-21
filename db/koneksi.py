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
from sqlalchemy.pool import StaticPool

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


def buat_engine(url: str | None = None, echo: bool = False) -> Engine:
    """Membuat engine SQLAlchemy.

    Parameter:
        url: URL database; bila kosong memakai DATABASE_URL dari .env.
             'sqlite://' membuat database di memori yang dibagi satu koneksi.
        echo: cetak SQL (untuk debug).
    Kembali:
        Engine SQLAlchemy.
    """
    url = normalisasi_url(url or muat_pengaturan().database_url)
    if url.startswith("sqlite"):
        return create_engine(
            url,
            echo=echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,  # satu koneksi agar database memori tetap hidup
        )
    # Batas waktu koneksi agar tes/API tidak menggantung bila database tidak menjawab.
    return create_engine(url, echo=echo, pool_pre_ping=True, connect_args={"connect_timeout": 10})


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
