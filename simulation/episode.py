"""
Tujuan      : Struktur episode yang dapat diputar ulang (sintetis dari generator atau nyata dari data
              olahan), penyimpanan ke database, dan pemuatan kembali untuk API, simulasi, dan demo.
Lapis       : Simulasi (melintasi S-I-G-A).
Sumber      : sensing/dummy_generator.py (episode sintetis); data/processed atau database
              (hujan NASA POWER nyata, titik Glapan nyata) untuk episode nyata 24 Jan 2025.
Masukan     : Parameter preset, seed, sesi database.
Keluaran    : Objek Episode (atribut id, t0, hujan, prakiraan, muka_air, laporan, kebenaran, label_seri).
Keterbatasan: Episode nyata memakai prakiraan dan muka air sintetis berlabel karena arsip prakiraan
              dan seri muka air belum tersedia (A-034); hasil episode nyata belum terkonfirmasi.
              Hujan NASA POWER harian dibagi rata ke 24 jam.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from config import ParamsAktif, muat_params, muat_pengaturan
from inference.fitur import _jam_relatif
from sensing import dummy_generator, muka_air_sintetis
from sensing.dummy_generator import EpisodeSintetis
from sensing.standar import baca_olahan

KOLOM_LAPORAN = ["waktu", "jenis", "isi", "sumber", "is_simulated"]


@dataclass
class Episode:
    """Episode yang diputar ulang jam demi jam."""

    id: str
    nama: str
    jenis: str                      # nyata / sintetis
    t0: datetime
    hujan: pd.DataFrame
    prakiraan: pd.DataFrame
    muka_air: pd.DataFrame
    laporan: pd.DataFrame
    kebenaran: dict = field(default_factory=dict)
    is_simulated: bool = True
    status_hasil: str = "sintetis"
    keterangan: str = ""
    preset: str | None = None
    seed: int | None = None

    @property
    def label_seri(self) -> dict[str, str]:
        """Label nyata/dummy tiap seri untuk ditampilkan (NFR-2)."""
        def lab(df: pd.DataFrame) -> str:
            if df is None or df.empty:
                return "kosong"
            s = df["is_simulated"].astype(bool)
            return "dummy" if s.all() else ("nyata" if not s.any() else "campuran")
        return {"hujan": lab(self.hujan), "prakiraan": lab(self.prakiraan),
                "muka_air": lab(self.muka_air), "laporan": lab(self.laporan)}


def dari_sintetis(ep: EpisodeSintetis, nama: str | None = None) -> Episode:
    """Membungkus EpisodeSintetis menjadi Episode."""
    return Episode(id=ep.id, nama=nama or f"Episode sintetis {ep.id}", jenis="sintetis", t0=ep.t0,
                   hujan=ep.hujan, prakiraan=ep.prakiraan, muka_air=ep.muka_air, laporan=ep.laporan,
                   kebenaran=ep.kebenaran, is_simulated=True, status_hasil="sintetis",
                   keterangan="Dibangkitkan generator dummy (is_simulated = true)",
                   preset=ep.preset, seed=ep.seed)


def episode_sintetis(n: int, seed: int, preset: str | None = None, awalan: str = "SIN") -> list[Episode]:
    """n episode sintetis berseed (untuk simulasi dan demo)."""
    return [dari_sintetis(e) for e in dummy_generator.ambil(n, seed, preset, awalan=awalan)]


def episode_cadangan(params: ParamsAktif | None = None) -> Episode:
    """Skenario demo cadangan: satu episode sintetis dengan seed tetap (spesifikasi 16).

    Dipilih episode terganggu pertama dari seed_cadangan agar demo selalu memperlihatkan keputusan.
    """
    params = params or muat_params()
    d = params.demo
    for i, e in enumerate(dummy_generator.ambil(20, int(d["seed_cadangan"]), params.preset, awalan="DMC")):
        if e.kebenaran["terganggu"]:
            e.id = d["id_episode_cadangan"]
            return dari_sintetis(e, nama=f"Skenario cadangan presentasi (seed {d['seed_cadangan']}, #{i + 1})")
    raise RuntimeError("seed cadangan tidak menghasilkan episode terganggu")  # pragma: no cover


def bangun_episode_nyata(params: ParamsAktif | None = None, hujan_harian: pd.DataFrame | None = None,
                         glapan: pd.DataFrame | None = None) -> Episode:
    """Episode nyata malam 24 Jan 2025: hujan NASA POWER nyata + titik Glapan nyata, dengan
    prakiraan dan muka air sintetis berlabel.

    Parameter:
        hujan_harian: tabel standar hujan harian; bawaan IMERG Late dari
            data/processed/hujan_gpm_imerg.csv, atau NASA POWER bila IMERG belum ada.
        glapan: tabel standar Glapan nyata (bawaan data/processed/muka_air_glapan.csv).
    """
    params = params or muat_params()
    konf = params.demo["episode_nyata"]
    t0 = datetime.fromisoformat(konf["t0"])
    H, A = params.episode.horizon_jam, params.episode.antesedent_hari * 24
    sesudah = params.dummy["prakiraan"]["sesudah_t0_jam"]
    mulai = t0 - timedelta(hours=H + A)
    glapan = baca_olahan("muka_air_glapan") if glapan is None else glapan
    hari_awal = pd.Timestamp(mulai).normalize()
    batas = pd.Timestamp(t0 + timedelta(hours=sesudah))

    def _jendela(df: pd.DataFrame) -> pd.DataFrame:
        return df[(df["waktu"] >= hari_awal) & (df["waktu"] <= batas)].copy()

    if hujan_harian is None:
        # IMERG Late lebih dulu (hulu terpisah dari lokal; versi yang tersedia pada jam keputusan),
        # NASA POWER sebagai cadangan bila IMERG belum diunduh.
        imerg = baca_olahan("hujan_gpm_imerg")
        if not imerg.empty:
            imerg = _jendela(imerg[imerg["sumber"] == "gpm_imerg_late"])
        lengkap = not imerg.empty and {"lokal", "hulu"} <= set(imerg["lokasi"])
        hujan_harian = imerg if lengkap else baca_olahan("hujan_nasa_power")
    hujan = _jendela(hujan_harian)
    hujan = hujan[["waktu", "lokasi", "nilai", "satuan", "sumber", "is_simulated", "resolusi_jam"]]
    nama_sumber = {"gpm_imerg_late": "GPM IMERG Late (0,1 derajat)", "nasa_power": "NASA POWER"}
    sumber_hujan = ", ".join(sorted({nama_sumber.get(s, s) for s in hujan["sumber"]}))

    # Seri per jam (dibagi rata) untuk prakiraan sintetis dan muka air sintetis
    jam = pd.date_range(mulai, t0 + timedelta(hours=sesudah - 1), freq="h")
    jam_rel = _jam_relatif(pd.Series(jam), t0)
    per_jam = {}
    for lok in ("lokal", "hulu"):
        s = muka_air_sintetis.ke_per_jam(hujan[hujan["lokasi"] == lok])
        per_jam[lok] = s.reindex(jam, fill_value=0.0).to_numpy()
    rng = np.random.default_rng(muat_pengaturan().sim_seed)
    pk = pd.DataFrame(dummy_generator.bangkitkan_prakiraan(jam_rel, per_jam["lokal"], per_jam["hulu"],
                                                           t0, params, rng),
                      columns=["waktu_terbit", "waktu", "lokasi", "nilai"]).assign(
        satuan="mm", sumber="prakiraan_sintetis", is_simulated=True,
        resolusi_jam=params.dummy["prakiraan"]["periode_jam"])
    hulu_harian = hujan[hujan["lokasi"] == "hulu"]
    lokal_harian = hujan[hujan["lokasi"] == "lokal"]
    ma_sint = muka_air_sintetis.jalankan(hulu_harian, lokal_harian)
    ma_sint = ma_sint[(ma_sint["waktu"] >= mulai) & (ma_sint["waktu"] < t0 + timedelta(hours=sesudah))]
    ma_nyata = glapan[["waktu", "lokasi", "nilai", "satuan", "sumber", "is_simulated"]] if len(glapan) else glapan
    muka_air = pd.concat([ma_sint.drop(columns=["kualitas"], errors="ignore"), ma_nyata], ignore_index=True)
    return Episode(
        id=konf["id"], nama=konf["nama"], jenis="nyata", t0=t0, hujan=hujan.reset_index(drop=True),
        prakiraan=pk, muka_air=muka_air, laporan=pd.DataFrame(columns=KOLOM_LAPORAN),
        kebenaran={"terganggu": None, "mekanisme": None, "skenario_lama_tutup": None},
        is_simulated=False, status_hasil=konf["hasil"],
        keterangan=(f"Hujan nyata dari {sumber_hujan}; titik Glapan nyata (1970, jam tidak diketahui); "
                    "prakiraan dan muka air per jam sintetis berlabel. " + konf["status_t0"]),
        preset=params.preset,
    )


# ---------------------------------------------------------------- database

def simpan_ke_db(sesi: Session, ep: Episode) -> None:
    """Menyimpan episode dan seluruh serinya (dengan episode_id) ke database."""
    from db import repositori as repo
    k = ep.kebenaran or {}
    repo.simpan_episode(sesi, dict(
        id=ep.id, nama=ep.nama, jenis=ep.jenis, t0=ep.t0,
        horizon_jam=muat_params().episode.horizon_jam,
        interval_jam=muat_params().episode.interval_keputusan_jam,
        preset=ep.preset, seed=ep.seed, terganggu=k.get("terganggu"), mekanisme=k.get("mekanisme"),
        skenario_lama_tutup=k.get("skenario_lama_tutup"), lama_tutup_jam=k.get("lama_tutup_jam"),
        status_hasil=ep.status_hasil, is_simulated=ep.is_simulated, keterangan=ep.keterangan,
    ))
    repo.simpan_obs_hujan(sesi, ep.hujan, episode_id=ep.id)
    repo.simpan_prakiraan(sesi, ep.prakiraan, episode_id=ep.id)
    repo.simpan_muka_air(sesi, ep.muka_air.drop(columns=["kualitas"], errors="ignore"), episode_id=ep.id)
    repo.hapus_laporan_episode(sesi, ep.id)
    if len(ep.laporan):
        repo.simpan_laporan(sesi, [
            {"episode_id": ep.id, "waktu": pd.Timestamp(r["waktu"]).to_pydatetime(), "jenis": r["jenis"],
             "isi": r.get("isi"), "sumber": r.get("sumber"), "is_simulated": bool(r["is_simulated"])}
            for r in ep.laporan.to_dict("records")])


def muat_dari_db(sesi: Session, episode_id: str) -> Episode | None:
    """Memuat episode dan serinya dari database (offline, untuk API dan demo)."""
    from db import repositori as repo
    baris = repo.ambil_episode(sesi, episode_id)
    if baris is None:
        return None
    lap = repo.ambil_laporan(sesi, episode_id)
    return Episode(
        id=baris.id, nama=baris.nama, jenis=baris.jenis, t0=baris.t0,
        hujan=repo.ambil_obs_hujan(sesi, episode_id=episode_id),
        prakiraan=repo.ambil_prakiraan(sesi, episode_id=episode_id),
        muka_air=repo.ambil_muka_air(sesi, episode_id=episode_id),
        laporan=lap[KOLOM_LAPORAN] if len(lap) else pd.DataFrame(columns=KOLOM_LAPORAN),
        kebenaran={"terganggu": baris.terganggu, "mekanisme": baris.mekanisme,
                   "skenario_lama_tutup": baris.skenario_lama_tutup, "lama_tutup_jam": baris.lama_tutup_jam},
        is_simulated=baris.is_simulated, status_hasil=baris.status_hasil,
        keterangan=baris.keterangan or "", preset=baris.preset, seed=baris.seed,
    )


def siapkan_episode_demo(engine=None, params: ParamsAktif | None = None) -> list[str]:
    """Membangun episode demo (nyata 24 Jan 2025, cadangan presentasi, beberapa sintetis) dan
    menyimpannya ke database agar API/demo berjalan offline.

    Kembali:
        Daftar id episode yang disimpan.
    """
    from db.inisialisasi import inisialisasi
    from db.koneksi import buat_engine, sesi_dari
    params = params or muat_params()
    engine = engine or buat_engine()
    inisialisasi(engine)
    daftar = [episode_cadangan(params)]
    try:
        daftar.insert(0, bangun_episode_nyata(params))
    except (KeyError, ValueError):  # pragma: no cover - data olahan belum ada
        pass
    n = int(params.demo["jumlah_episode_sintetis_demo"])
    daftar += episode_sintetis(n, muat_pengaturan().sim_seed, params.preset, awalan="DEMO")
    with sesi_dari(engine) as sesi:
        for ep in daftar:
            simpan_ke_db(sesi, ep)
    return [e.id for e in daftar]


def main() -> None:
    """CLI: python -m simulation.episode muat."""
    ap = argparse.ArgumentParser(description="Episode SIGAP-KA")
    ap.add_argument("perintah", choices=["muat"], help="muat episode demo ke database")
    ap.parse_args()
    print("Episode tersimpan:", siapkan_episode_demo())


if __name__ == "__main__":
    main()
