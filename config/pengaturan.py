"""
Tujuan      : Memuat pengaturan dari .env dan parameter dari config/params.json, lalu
              memilih preset (low/base/high) dan memvalidasinya dengan Pydantic.
Lapis       : Lintas lapis (dipakai S, I, G, A, simulasi, API).
Sumber      : File .env di akar repo (pilihan preset, metode katalog, kredensial) dan
              config/params.json (satu-satunya sumber parameter model).
Masukan     : Variabel lingkungan / .env; nama preset opsional.
Keluaran    : Objek Pengaturan (env) dan ParamsAktif (parameter preset terpilih).
Keterbatasan: .env lama yang ditulis PowerShell bisa memuat BOM; dibaca dengan utf-8-sig.
              Nilai parameter sebagian besar dummy (lihat docs/asumsi.md).
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AKAR_REPO = Path(__file__).resolve().parent.parent
PRESET_VALID = ("low", "base", "high")
ID_TINDAKAN = tuple(f"T{i}" for i in range(1, 10))


class Pengaturan(BaseSettings):
    """Pengaturan dari file .env (pilihan preset, lokasi data, kredensial, akun awal)."""

    params_file: str = "config/params.json"
    params_preset: Literal["low", "base", "high"] = "base"
    kejadian_metode: Literal["manual", "ocr_llm"] = "manual"
    sumber_hujan_hulu: str = "gpm_imerg"
    data_dir: str = "data/processed"
    sim_seed: int = 42

    admin_user: str = "admin"
    admin_password: str = "admin"

    database_url: str = "postgresql://sigap:sigap@localhost:5432/sigap"
    database_url_test: str = "postgresql://sigap:sigap@localhost:5432/sigap_test"

    jwt_secret: str = "sigap-dev-rahasia-ganti-di-luar-demo"
    jwt_menit_kedaluwarsa: int = 480
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    earthdata_token: str = ""
    jaxa_user: str = ""
    jaxa_password: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5-5"
    tesseract_cmd: str = ""

    model_config = SettingsConfigDict(
        env_file=str(AKAR_REPO / ".env"),
        env_file_encoding="utf-8-sig",  # tahan BOM dari PowerShell
        extra="ignore",
    )

    def path_mutlak(self, relatif: str) -> Path:
        """Mengubah path relatif (terhadap akar repo) menjadi path mutlak.

        Parameter:
            relatif: path dari .env, misalnya 'config/params.json'.
        Kembali:
            Path mutlak; path yang sudah mutlak dikembalikan apa adanya.
        """
        p = Path(relatif)
        return p if p.is_absolute() else AKAR_REPO / p

    @property
    def daftar_cors(self) -> list[str]:
        """Daftar origin CORS dari string dipisah koma."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


class ParamTindakan(BaseModel):
    """Parameter satu tindakan pada satu preset (satuan biaya: juta rupiah)."""

    C: float = Field(gt=0, description="Biaya tindakan bila dijalankan")
    L: float = Field(gt=0, description="Kerugian bila gangguan terjadi tanpa persiapan")
    P: float = Field(ge=0, description="Denda alarm palsu")
    waktu_siap_jam: int = Field(gt=0, description="Batas waktu siap, jam sebelum T-0")

    @model_validator(mode="after")
    def _c_lebih_kecil_dari_l(self) -> "ParamTindakan":
        if self.C >= self.L:
            raise ValueError("C harus lebih kecil dari L agar tindakan bisa bernilai")
        return self

    @property
    def ambang_statis(self) -> float:
        """Ambang cost-loss di batas waktu: (C + P) / (L + P)."""
        return (self.C + self.P) / (self.L + self.P)


class Tindakan(BaseModel):
    """Satu tindakan kontinjensi beserta parameter preset aktif."""

    id: str
    nama: str
    keputusan_sebelum: str
    terkonfirmasi: bool
    status: Literal["dummy", "nyata"]
    param: ParamTindakan


class ParamEpisode(BaseModel):
    """Kerangka waktu episode keputusan."""

    horizon_jam: int = Field(gt=0)
    interval_keputusan_jam: int = Field(gt=0)
    antesedent_hari: int = Field(gt=0)

    @model_validator(mode="after")
    def _horizon_kelipatan_interval(self) -> "ParamEpisode":
        if self.horizon_jam % self.interval_keputusan_jam:
            raise ValueError("horizon_jam harus kelipatan interval_keputusan_jam")
        return self

    @property
    def jumlah_langkah(self) -> int:
        """Jumlah jam keputusan termasuk T-horizon dan T-0."""
        return self.horizon_jam // self.interval_keputusan_jam + 1

    def jam_sebelum_t0(self, langkah: int) -> int:
        """Mengubah indeks langkah keputusan (0 = awal horizon) menjadi jam sebelum T-0."""
        return self.horizon_jam - langkah * self.interval_keputusan_jam

    def langkah_dari_jam(self, jam_sebelum_t0: int) -> int:
        """Mengubah jam sebelum T-0 menjadi indeks langkah keputusan."""
        if jam_sebelum_t0 % self.interval_keputusan_jam:
            raise ValueError("jam harus kelipatan interval keputusan")
        return (self.horizon_jam - jam_sebelum_t0) // self.interval_keputusan_jam


class ParamGating(BaseModel):
    """Parameter pemrograman dinamis kurva pemicu."""

    jumlah_grid_peluang: int = Field(ge=11)
    konsentrasi_beta: float = Field(gt=0)
    diskon_biaya_awal_per_langkah: float = Field(ge=0, lt=1)


class SkenarioLamaTutup(BaseModel):
    """Rentang jam dan faktor kerugian satu skenario lama tutup."""

    jam_min: float = Field(ge=0)
    jam_maks: float = Field(gt=0)
    faktor_L: float = Field(gt=0)


class ParamLamaTutup(BaseModel):
    """Tiga skenario lama tutup dan peluang bersyarat mekanisme."""

    skenario: dict[str, SkenarioLamaTutup]
    peluang_bersyarat: dict[str, dict[str, float]]
    campuran_mekanisme_bawaan: dict[str, float]

    @field_validator("peluang_bersyarat")
    @classmethod
    def _jumlah_satu(cls, v: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
        for mek, sebaran in v.items():
            if abs(sum(sebaran.values()) - 1.0) > 1e-9:
                raise ValueError(f"peluang skenario untuk {mek} harus berjumlah 1")
        return v


class ParamsAktif(BaseModel):
    """Parameter lengkap untuk satu preset. Bagian bertingkat preset sudah diselesaikan."""

    preset: Literal["low", "base", "high"]
    tindakan: dict[str, Tindakan]
    episode: ParamEpisode
    gating: ParamGating
    lama_tutup: ParamLamaTutup
    inferensi: dict[str, Any]
    prior: dict[str, float]
    muka_air: dict[str, Any]
    dummy: dict[str, Any]
    simulasi: dict[str, Any]
    lokasi: dict[str, Any]
    sumber_data: dict[str, Any]
    urutan_cadangan_hujan_hulu: list[str]
    jadwal_dummy: dict[str, Any]
    demo: dict[str, Any]
    nyata: dict[str, Any]
    mentah: dict[str, Any] = Field(repr=False)

    @model_validator(mode="after")
    def _waktu_siap_valid(self) -> "ParamsAktif":
        ep = self.episode
        for tid, t in self.tindakan.items():
            w = t.param.waktu_siap_jam
            if w % ep.interval_keputusan_jam or w > ep.horizon_jam:
                raise ValueError(
                    f"{tid}: waktu_siap_jam {w} harus kelipatan interval dan <= horizon"
                )
        return self

    def daftar_tindakan(self) -> list[Tindakan]:
        """Tindakan T1-T9 berurutan."""
        return [self.tindakan[t] for t in ID_TINDAKAN]


def muat_params_mentah(path: str | Path | None = None) -> dict[str, Any]:
    """Membaca config/params.json apa adanya.

    Parameter:
        path: lokasi file; bila kosong memakai PARAMS_FILE dari .env.
    Kembali:
        dict isi params.json.
    """
    if path is None:
        peng = muat_pengaturan()
        path = peng.path_mutlak(peng.params_file)
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def selesaikan_preset(mentah: dict[str, Any], preset: str) -> ParamsAktif:
    """Memilih nilai preset untuk bagian yang bertingkat low/base/high dan memvalidasinya.

    Parameter:
        mentah: isi params.json.
        preset: 'low', 'base', atau 'high'.
    Kembali:
        ParamsAktif tervalidasi.
    """
    if preset not in PRESET_VALID:
        raise ValueError(f"preset harus salah satu dari {PRESET_VALID}, bukan {preset!r}")
    m = copy.deepcopy(mentah)

    tindakan = {}
    for tid in ID_TINDAKAN:
        t = m["tindakan"][tid]
        tindakan[tid] = Tindakan(
            id=tid,
            nama=t["nama"],
            keputusan_sebelum=t["keputusan_sebelum"],
            terkonfirmasi=t["terkonfirmasi"],
            status=t["status"],
            param=ParamTindakan(**t[preset]),
        )

    dummy = {k: v for k, v in m["dummy"].items() if k not in PRESET_VALID}
    dummy.update(m["dummy"][preset])  # nilai generator untuk preset aktif

    return ParamsAktif(
        preset=preset,
        tindakan=tindakan,
        episode=ParamEpisode(**{k: v for k, v in m["episode"].items() if k in ParamEpisode.model_fields}),
        gating=ParamGating(**{k: v for k, v in m["gating"].items() if k in ParamGating.model_fields}),
        lama_tutup=ParamLamaTutup(**{k: v for k, v in m["lama_tutup"].items() if k in ParamLamaTutup.model_fields}),
        inferensi=m["inferensi"],
        prior=m["inferensi"]["prior_preset"][preset],
        muka_air=m["muka_air"],
        dummy=dummy,
        simulasi=m["simulasi"],
        lokasi=m["lokasi"],
        sumber_data=m["sumber_data"],
        urutan_cadangan_hujan_hulu=m["urutan_cadangan_hujan_hulu"],
        jadwal_dummy=m["jadwal_dummy"],
        demo=m["demo"],
        nyata=m["_nyata"],
        mentah=mentah,
    )


@lru_cache(maxsize=1)
def muat_pengaturan() -> Pengaturan:
    """Memuat pengaturan .env sekali (di-cache)."""
    return Pengaturan()


@lru_cache(maxsize=8)
def muat_params(preset: str | None = None, path: str | None = None) -> ParamsAktif:
    """Memuat parameter untuk preset tertentu (di-cache per preset dan path).

    Parameter:
        preset: 'low', 'base', 'high'; bila kosong memakai PARAMS_PRESET dari .env.
        path: lokasi params.json; bila kosong memakai PARAMS_FILE dari .env.
    Kembali:
        ParamsAktif.
    """
    preset = preset or muat_pengaturan().params_preset
    return selesaikan_preset(muat_params_mentah(path), preset)


def reset_cache() -> None:
    """Mengosongkan cache pengaturan dan parameter (dipakai tes)."""
    muat_pengaturan.cache_clear()
    muat_params.cache_clear()
