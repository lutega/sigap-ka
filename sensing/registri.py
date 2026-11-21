"""
Tujuan      : Daftar sumber data lapis S, pemilihan sumber aktif dan cadangan dari konfigurasi,
              serta pemilih metode katalog kejadian (KEJADIAN_METODE).
Lapis       : S (Sensing).
Sumber      : params.json (sumber_data, urutan_cadangan_hujan_hulu) dan .env (SUMBER_HUJAN_HULU,
              KEJADIAN_METODE, kredensial).
Masukan     : Nama sumber atau rentang waktu.
Keluaran    : Modul sumber, status kesiapan tiap sumber, dan hasil ambil hujan hulu beserta
              jejak percobaan (sumber mana yang gagal dan mengapa).
Keterbatasan: Kesiapan sumber jaringan (NASA POWER, BMKG) hanya diketahui saat diambil.
              Cadangan terakhir adalah data dummy berlabel is_simulated = True (NFR-5).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from datetime import date, datetime, time
from types import ModuleType

import numpy as np
import pandas as pd

from config import muat_params, muat_pengaturan
from sensing.standar import DIR_MANUAL, SumberTidakTersedia, validasi_standar

MODUL = {
    "nasa_power": "sensing.hujan_nasa_power",
    "gpm_imerg": "sensing.hujan_gpm_imerg",
    "gsmap": "sensing.hujan_gsmap",
    "bmkg_prakiraan": "sensing.prakiraan_bmkg",
    "bmkg_stasiun": "sensing.hujan_bmkg_stasiun",
    "glapan_bnpb": "sensing.muka_air_glapan",
    "muka_air_sintetis": "sensing.muka_air_sintetis",
    "bbws": "sensing.muka_air_bbws",
    "kejadian_manual": "sensing.kejadian_manual",
    "kejadian_ocr_llm": "sensing.kejadian_ocr_llm",
    "jadwal_ka": "sensing.jadwal_ka",
    "dummy_generator": "sensing.dummy_generator",
}


@dataclass
class HasilAmbil:
    """Hasil pengambilan dengan rantai cadangan."""

    data: pd.DataFrame
    sumber: str
    percobaan: list[dict] = field(default_factory=list)

    @property
    def memakai_cadangan(self) -> bool:
        """True bila sumber yang dipakai bukan pilihan pertama."""
        return len(self.percobaan) > 1


def modul(nama: str) -> ModuleType:
    """Mengimpor modul sumber menurut nama di params.json."""
    if nama not in MODUL:
        raise KeyError(f"sumber tidak dikenal: {nama}")
    return importlib.import_module(MODUL[nama])


def urutan_hujan_hulu() -> list[str]:
    """Urutan sumber hujan hulu: SUMBER_HUJAN_HULU lebih dulu, lalu cadangan dari params.json."""
    utama = muat_pengaturan().sumber_hujan_hulu
    urutan = [utama] + [s for s in muat_params().urutan_cadangan_hujan_hulu if s != utama]
    return urutan


def hujan_harian_dummy(lokasi: str, mulai: date, selesai: date, seed: int) -> pd.DataFrame:
    """Seri hujan harian dummy (cadangan terakhir), selalu is_simulated = True.

    Hari basah berpeluang 0,5; jumlah hujan gamma dengan rerata dari antesedent_median_mm/5.
    """
    rng = np.random.default_rng(seed)
    hari = pd.date_range(mulai, selesai, freq="D")
    rerata = muat_params().dummy["antesedent_median_mm"] / 5.0
    basah = rng.random(len(hari)) < 0.5
    nilai = np.where(basah, rng.gamma(0.8, rerata / 0.8 * 2, len(hari)), 0.0)
    return validasi_standar(pd.DataFrame({
        "waktu": hari, "lokasi": lokasi, "nilai": nilai, "satuan": "mm",
        "sumber": "dummy_generator", "is_simulated": True, "resolusi_jam": 24,
    }))


def ambil_hujan_hulu(mulai: date, selesai: date, **kw) -> HasilAmbil:
    """Mengambil hujan hulu dengan rantai cadangan (IMERG -> GSMaP -> NASA POWER -> dummy).

    Parameter:
        mulai, selesai: rentang tanggal.
        kw: diteruskan ke fungsi jalankan() modul (mis. sesi_http untuk tes).
    Kembali:
        HasilAmbil; percobaan mencatat status tiap sumber.
    """
    percobaan = []
    for nama in urutan_hujan_hulu():
        if nama == "dummy_generator":
            df = hujan_harian_dummy("hulu", mulai, selesai, muat_pengaturan().sim_seed)
            percobaan.append({"sumber": nama, "status": "cadangan", "pesan": "data dummy berlabel"})
            return HasilAmbil(df, nama, percobaan)
        try:
            m = modul(nama)
            if nama == "gsmap":
                df, _ = m.jalankan("hulu", datetime.combine(mulai, time()),
                                   datetime.combine(selesai, time(23)), **kw)
            else:
                df, _ = m.jalankan("hulu", mulai, selesai, **kw)
            percobaan.append({"sumber": nama, "status": "sukses", "pesan": f"{len(df)} baris"})
            return HasilAmbil(df, nama, percobaan)
        except SumberTidakTersedia as galat:
            percobaan.append({"sumber": nama, "status": "dilewati", "pesan": str(galat)})
    raise SumberTidakTersedia("tidak ada sumber hujan hulu yang tersedia")  # pragma: no cover


def modul_kejadian() -> tuple[ModuleType, str]:
    """Modul katalog kejadian sesuai KEJADIAN_METODE; ocr_llm tanpa berkas periksa jatuh ke manual.

    Kembali:
        (modul, catatan).
    """
    metode = muat_pengaturan().kejadian_metode
    if metode == "ocr_llm":
        m = modul("kejadian_ocr_llm")
        if (DIR_MANUAL / m.BERKAS_PERIKSA).exists():
            return m, "metode ocr_llm"
        return modul("kejadian_manual"), "ocr_llm belum punya berkas periksa; memakai manual"
    return modul("kejadian_manual"), "metode manual"


def _siap(nama: str) -> tuple[bool, str]:
    """Kesiapan statis satu sumber (kredensial/berkas), tanpa akses jaringan."""
    peng = muat_pengaturan()
    berkas = {
        "glapan_bnpb": "muka_air_glapan.csv", "bbws": "bbws.csv",
        "bmkg_stasiun": "bmkg_stasiun.csv", "kejadian_manual": "kejadian.csv",
    }
    if nama in berkas:
        ada = (DIR_MANUAL / berkas[nama]).exists()
        return ada, "berkas tersedia" if ada else f"berkas {berkas[nama]} belum ada"
    if nama == "gpm_imerg":
        return bool(peng.earthdata_token), "token Earthdata ada" if peng.earthdata_token else "EARTHDATA_TOKEN kosong"
    if nama == "gsmap":
        ok = bool(peng.jaxa_user and peng.jaxa_password)
        return ok, "kredensial JAXA ada" if ok else "JAXA_USER/JAXA_PASSWORD kosong"
    if nama == "kejadian_ocr_llm":
        ada = (DIR_MANUAL / "kejadian_ocr_periksa.csv").exists()
        return ada, "berkas periksa ada" if ada else "belum ada hasil OCR+LLM yang diperiksa"
    if nama == "jadwal_ka":
        ada = (DIR_MANUAL / "jadwal_ka.csv").exists()
        return True, "jadwal nyata" if ada else "placeholder dummy KA-A s.d. KA-F"
    if nama in ("nasa_power", "bmkg_prakiraan"):
        return True, "API publik (butuh internet saat diambil)"
    return True, "dibangkitkan lokal"


def status_sumber() -> list[dict]:
    """Status kesiapan semua sumber di params.json (untuk tab Data dan /data/sumber)."""
    hasil = []
    for nama, s in muat_params().sumber_data.items():
        siap, alasan = _siap(nama)
        hasil.append({"nama": nama, "jenis": s["jenis"], "kelompok": s["kelompok"],
                      "opsional": s["opsional"], "akses": s["akses"], "siap": siap, "alasan": alasan})
    return hasil
