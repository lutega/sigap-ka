"""
Tujuan      : Definisi tabel database SIGAP-KA (spesifikasi 14.5) dengan SQLAlchemy 2.0.
Lapis       : Infrastruktur data.
Sumber      : Spesifikasi 14.5 dan 15-16. Tabel tambahan di luar 14.5: pengguna (bagian 15),
              episode, laporan_lapangan, simulasi_run, sesi_demo (bagian 16).
Masukan     : -
Keluaran    : Kelas ORM dan metadata Base.
Keterbatasan: Parameter C, L, P sengaja TIDAK disimpan di database (satu sumber: params.json).
              Waktu disimpan sebagai WIB tanpa zona waktu (asumsi A-006).
              Kolom episode_id = '' berarti observasi umum (bukan milik episode tertentu).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nama tabel hypertable TimescaleDB beserta kolom waktunya.
HYPERTABLE = {
    "obs_hujan": "waktu",
    "prakiraan_hujan": "waktu_terbit",
    "obs_muka_air": "waktu",
}


class Base(DeclarativeBase):
    """Basis deklaratif semua tabel."""


# ---------------------------------------------------------------- hypertable (time series)

class ObsHujan(Base):
    """Observasi hujan (mm) per periode. `waktu` = awal periode, `resolusi_jam` = panjang periode."""

    __tablename__ = "obs_hujan"
    waktu: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    lokasi: Mapped[str] = mapped_column(String(32), primary_key=True)  # lokal / hulu / gundih
    sumber: Mapped[str] = mapped_column(String(32), primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(40), primary_key=True, default="")
    nilai: Mapped[float | None] = mapped_column(Float)
    satuan: Mapped[str] = mapped_column(String(16), default="mm")
    resolusi_jam: Mapped[int] = mapped_column(Integer, default=24)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    kualitas: Mapped[str] = mapped_column(String(16), default="baik")
    waktu_ambil: Mapped[datetime | None] = mapped_column(DateTime)


class PrakiraanHujan(Base):
    """Prakiraan hujan; disimpan dengan waktu terbit agar model hanya memakai prakiraan yang sudah ada."""

    __tablename__ = "prakiraan_hujan"
    waktu_terbit: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    waktu_valid: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    lokasi: Mapped[str] = mapped_column(String(32), primary_key=True)
    sumber: Mapped[str] = mapped_column(String(32), primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(40), primary_key=True, default="")
    nilai: Mapped[float | None] = mapped_column(Float)
    satuan: Mapped[str] = mapped_column(String(16), default="mm")
    resolusi_jam: Mapped[int] = mapped_column(Integer, default=3)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    waktu_ambil: Mapped[datetime | None] = mapped_column(DateTime)


class ObsMukaAir(Base):
    """Observasi muka air (Glapan, sintetis, BBWS)."""

    __tablename__ = "obs_muka_air"
    waktu: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    titik: Mapped[str] = mapped_column(String(32), primary_key=True)  # glapan / badan_rel / ...
    sumber: Mapped[str] = mapped_column(String(32), primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(40), primary_key=True, default="")
    elevasi: Mapped[float | None] = mapped_column(Float)
    satuan: Mapped[str] = mapped_column(String(32), default="cm")
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    kualitas: Mapped[str] = mapped_column(String(16), default="baik")
    waktu_ambil: Mapped[datetime | None] = mapped_column(DateTime)


# ---------------------------------------------------------------- relasional

class SumberData(Base):
    """Daftar sumber data dan statusnya."""

    __tablename__ = "sumber_data"
    nama: Mapped[str] = mapped_column(String(40), primary_key=True)
    jenis: Mapped[str] = mapped_column(String(20))
    cara_akses: Mapped[str] = mapped_column(Text)
    kelompok: Mapped[str] = mapped_column(String(12))  # inti / tambahan
    opsional: Mapped[bool] = mapped_column(Boolean, default=False)
    status_terakhir: Mapped[str | None] = mapped_column(String(20))
    waktu_ambil_terakhir: Mapped[datetime | None] = mapped_column(DateTime)


class LogPengambilan(Base):
    """Catatan asal data tiap pengambilan (waktu ambil, rentang, versi/tautan, status)."""

    __tablename__ = "log_pengambilan"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sumber: Mapped[str] = mapped_column(String(40), index=True)
    waktu_ambil: Mapped[datetime] = mapped_column(DateTime)
    rentang_mulai: Mapped[datetime | None] = mapped_column(DateTime)
    rentang_selesai: Mapped[datetime | None] = mapped_column(DateTime)
    versi_atau_tautan: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))  # sukses / gagal / dilewati / cadangan
    jumlah_baris: Mapped[int] = mapped_column(Integer, default=0)
    pesan: Mapped[str | None] = mapped_column(Text)


class Kejadian(Base):
    """Katalog kejadian gangguan E1-E6 (dan seterusnya)."""

    __tablename__ = "kejadian"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    tanggal: Mapped[date | None] = mapped_column(Date)
    jam_tutup: Mapped[datetime | None] = mapped_column(DateTime)
    jam_buka: Mapped[datetime | None] = mapped_column(DateTime)
    lokasi_km: Mapped[str | None] = mapped_column(String(40))
    mekanisme: Mapped[str | None] = mapped_column(String(20))  # genangan / gerusan
    ka_terdampak: Mapped[str | None] = mapped_column(Text)
    sumber: Mapped[str | None] = mapped_column(Text)
    metode: Mapped[str] = mapped_column(String(12), default="manual")  # manual / ocr_llm
    status_konfirmasi: Mapped[str] = mapped_column(String(30), default="belum terkonfirmasi")
    kode_periksa: Mapped[str | None] = mapped_column(String(4))  # K1-K3 (metode ocr_llm)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    catatan: Mapped[str | None] = mapped_column(Text)


class JadwalKA(Base):
    """Jadwal KA yang melewati Gubug."""

    __tablename__ = "jadwal_ka"
    nomor: Mapped[str] = mapped_column(String(20), primary_key=True)
    relasi: Mapped[str] = mapped_column(String(80))
    jam_lewat_gubug: Mapped[str] = mapped_column(String(5))  # HH:MM WIB
    sumber: Mapped[str | None] = mapped_column(Text)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)


class TindakanDB(Base):
    """Daftar tindakan T1-T9 (tanpa C, L, P: parameter tetap di params.json)."""

    __tablename__ = "tindakan"
    id: Mapped[str] = mapped_column(String(4), primary_key=True)
    nama: Mapped[str] = mapped_column(String(80))
    batas_waktu_siap: Mapped[str] = mapped_column(String(80))
    terkonfirmasi: Mapped[bool] = mapped_column(Boolean, default=True)


class Episode(Base):
    """Episode hujan lebat yang dapat diputar ulang (nyata atau sintetis)."""

    __tablename__ = "episode"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nama: Mapped[str] = mapped_column(String(120))
    jenis: Mapped[str] = mapped_column(String(12))  # nyata / sintetis
    t0: Mapped[datetime] = mapped_column(DateTime)
    horizon_jam: Mapped[int] = mapped_column(Integer)
    interval_jam: Mapped[int] = mapped_column(Integer)
    preset: Mapped[str | None] = mapped_column(String(8))
    seed: Mapped[int | None] = mapped_column(Integer)
    terganggu: Mapped[bool | None] = mapped_column(Boolean)
    mekanisme: Mapped[str | None] = mapped_column(String(20))
    skenario_lama_tutup: Mapped[str | None] = mapped_column(String(10))
    lama_tutup_jam: Mapped[float | None] = mapped_column(Float)
    status_hasil: Mapped[str] = mapped_column(String(30))  # sintetis / terkonfirmasi / belum terkonfirmasi
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    keterangan: Mapped[str | None] = mapped_column(Text)


class LaporanLapangan(Base):
    """Laporan petugas lapangan dan laporan jalan putus (bukti untuk lapis I dan peringatan maladaptasi)."""

    __tablename__ = "laporan_lapangan"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[str] = mapped_column(String(40), index=True, default="")
    waktu: Mapped[datetime] = mapped_column(DateTime)
    jenis: Mapped[str] = mapped_column(String(20))  # air_badan_rel / jalan_putus
    isi: Mapped[str | None] = mapped_column(Text)
    sumber: Mapped[str | None] = mapped_column(String(40))
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)


class KeputusanOperator(Base):
    """Log keputusan operator (Setujui/Tolak/Batalkan) beserta status SIGAP saat itu."""

    __tablename__ = "keputusan_operator"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[str] = mapped_column(String(40), index=True)
    tindakan_id: Mapped[str] = mapped_column(String(4))
    jam_sebelum_t0: Mapped[int] = mapped_column(Integer)
    waktu_dicatat: Mapped[datetime] = mapped_column(DateTime)
    status_sigap: Mapped[str] = mapped_column(String(40))
    keputusan: Mapped[str] = mapped_column(String(10))  # setujui / tolak / batalkan
    alasan: Mapped[str | None] = mapped_column(Text)
    username: Mapped[str] = mapped_column(String(40))
    mode: Mapped[str] = mapped_column(String(8), default="normal")  # normal / demo
    sesi_demo_id: Mapped[str | None] = mapped_column(String(40), index=True)
    peluang: Mapped[float | None] = mapped_column(Float)
    nilai_kurva: Mapped[float | None] = mapped_column(Float)


class SimulasiRun(Base):
    """Status satu run simulasi (dijalankan sebagai tugas latar belakang)."""

    __tablename__ = "simulasi_run"
    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    preset: Mapped[str] = mapped_column(String(8))
    seed: Mapped[int] = mapped_column(Integer)
    jumlah_episode: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12))  # antre / berjalan / selesai / gagal
    dibuat: Mapped[datetime] = mapped_column(DateTime)
    selesai: Mapped[datetime | None] = mapped_column(DateTime)
    ringkasan: Mapped[dict | None] = mapped_column(JSON)
    pesan: Mapped[str | None] = mapped_column(Text)


class HasilSimulasi(Base):
    """Biaya per episode per kebijakan untuk satu run simulasi."""

    __tablename__ = "hasil_simulasi"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    preset: Mapped[str] = mapped_column(String(8))
    seed: Mapped[int] = mapped_column(Integer)
    kebijakan: Mapped[str] = mapped_column(String(24))
    episode_ke: Mapped[int] = mapped_column(Integer)
    biaya: Mapped[float] = mapped_column(Float)
    terganggu: Mapped[bool] = mapped_column(Boolean)


class Pengguna(Base):
    """Akun dashboard (password disimpan sebagai hash bcrypt)."""

    __tablename__ = "pengguna"
    __table_args__ = (UniqueConstraint("username"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(40))
    hash_password: Mapped[str] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(10))  # admin / operator
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    dibuat: Mapped[datetime] = mapped_column(DateTime)
    diperbarui: Mapped[datetime | None] = mapped_column(DateTime)


class SesiDemo(Base):
    """Sesi mode demo (spesifikasi 16)."""

    __tablename__ = "sesi_demo"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(40))
    username: Mapped[str] = mapped_column(String(40))
    jam_sebelum_t0: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))  # berjalan / jeda / selesai
    kecepatan_detik_per_jam: Mapped[float] = mapped_column(Float)
    dibuat: Mapped[datetime] = mapped_column(DateTime)
    diperbarui: Mapped[datetime | None] = mapped_column(DateTime)
