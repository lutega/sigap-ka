"""
Tujuan      : Membuat skema database SIGAP-KA secara idempoten: tabel, hypertable TimescaleDB,
              continuous aggregate hujan harian, view akumulasi 1/3/5 hari, dan isi awal
              tabel sumber_data serta tindakan dari params.json.
Lapis       : Infrastruktur data.
Sumber      : db/model.py, config/params.json.
Masukan     : Engine database (PostgreSQL + TimescaleDB atau SQLite untuk tes).
Keluaran    : Skema siap pakai. Jalankan: python -m db.inisialisasi
Keterbatasan: Pada SQLite hanya tabel yang dibuat (tanpa hypertable dan agregat).
              Continuous aggregate memakai real-time aggregation agar data baru langsung
              terhitung tanpa menunggu refresh.
"""

from __future__ import annotations

import argparse

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config import muat_params
from db.koneksi import adalah_postgres, buat_engine, sesi_dari
from db.model import HYPERTABLE, Base, SumberData, TindakanDB

SQL_CAGG_HUJAN_HARIAN = """
CREATE MATERIALIZED VIEW IF NOT EXISTS hujan_harian
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket(INTERVAL '1 day', waktu) AS hari,
       lokasi, sumber, episode_id,
       sum(nilai) AS total_mm,
       max(CASE WHEN is_simulated THEN 1 ELSE 0 END) AS ada_simulasi,
       count(*) AS jumlah_baris
FROM obs_hujan
GROUP BY hari, lokasi, sumber, episode_id
WITH NO DATA
"""

# Akumulasi 3 dan 5 hari memakai jendela RANGE berbasis interval agar hari yang kosong
# tidak membuat jendela melebar.
SQL_VIEW_AKUMULASI = """
CREATE OR REPLACE VIEW hujan_akumulasi AS
SELECT hari, lokasi, sumber, episode_id,
       total_mm AS akumulasi_1h,
       sum(total_mm) OVER (PARTITION BY lokasi, sumber, episode_id ORDER BY hari
                           RANGE BETWEEN INTERVAL '2 days' PRECEDING AND CURRENT ROW) AS akumulasi_3h,
       sum(total_mm) OVER (PARTITION BY lokasi, sumber, episode_id ORDER BY hari
                           RANGE BETWEEN INTERVAL '4 days' PRECEDING AND CURRENT ROW) AS akumulasi_5h,
       ada_simulasi
FROM hujan_harian
"""


def _siapkan_timescale(engine: Engine) -> None:
    """Membuat ekstensi, hypertable, continuous aggregate, dan view akumulasi (PostgreSQL saja)."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as kon:
        kon.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        for tabel, kolom in HYPERTABLE.items():
            kon.execute(text(
                f"SELECT create_hypertable('{tabel}', by_range('{kolom}', INTERVAL '30 days'), "
                "if_not_exists => TRUE, migrate_data => TRUE)"
            ))
        kon.execute(text(SQL_CAGG_HUJAN_HARIAN))
        kon.execute(text(SQL_VIEW_AKUMULASI))


def _isi_tabel_acuan(engine: Engine) -> None:
    """Mengisi/menyegarkan tabel sumber_data dan tindakan dari params.json (tanpa C, L, P)."""
    params = muat_params()
    with sesi_dari(engine) as sesi:
        for nama, s in params.sumber_data.items():
            baris = sesi.get(SumberData, nama) or SumberData(nama=nama)
            baris.jenis = s["jenis"]
            baris.cara_akses = s["akses"]
            baris.kelompok = s["kelompok"]
            baris.opsional = bool(s["opsional"])
            sesi.merge(baris)
        for t in params.daftar_tindakan():
            sesi.merge(TindakanDB(
                id=t.id,
                nama=t.nama,
                batas_waktu_siap=t.keputusan_sebelum,
                terkonfirmasi=t.terkonfirmasi,
            ))


def inisialisasi(engine: Engine | None = None) -> dict:
    """Membuat seluruh skema secara idempoten.

    Parameter:
        engine: engine tujuan; bila kosong memakai DATABASE_URL dari .env.
    Kembali:
        Ringkasan: dialek, jumlah tabel, dan apakah fitur TimescaleDB disiapkan.
    """
    engine = engine or buat_engine()
    Base.metadata.create_all(engine)
    timescale = adalah_postgres(engine)
    if timescale:
        _siapkan_timescale(engine)
    _isi_tabel_acuan(engine)
    return {
        "dialek": engine.dialect.name,
        "jumlah_tabel": len(Base.metadata.tables),
        "timescale": timescale,
    }


def segarkan_agregat(engine: Engine) -> None:
    """Me-refresh continuous aggregate hujan_harian (opsional; real-time aggregation sudah aktif)."""
    if not adalah_postgres(engine):
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as kon:
        kon.execute(text("CALL refresh_continuous_aggregate('hujan_harian', NULL, NULL)"))


def hapus_semua(engine: Engine) -> None:
    """Menghapus view, agregat, dan semua tabel (dipakai tes dan reset total)."""
    if adalah_postgres(engine):
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as kon:
            kon.execute(text("DROP VIEW IF EXISTS hujan_akumulasi"))
            kon.execute(text("DROP MATERIALIZED VIEW IF EXISTS hujan_harian CASCADE"))
    Base.metadata.drop_all(engine)


def main() -> None:
    """Titik masuk CLI: python -m db.inisialisasi [--url URL] [--reset]."""
    ap = argparse.ArgumentParser(description="Inisialisasi skema database SIGAP-KA")
    ap.add_argument("--url", help="URL database (bawaan: DATABASE_URL di .env)")
    ap.add_argument("--reset", action="store_true", help="hapus semua tabel lebih dulu")
    arg = ap.parse_args()
    engine = buat_engine(arg.url)
    if arg.reset:
        hapus_semua(engine)
    hasil = inisialisasi(engine)
    print(f"Skema siap: {hasil}")


if __name__ == "__main__":
    main()
