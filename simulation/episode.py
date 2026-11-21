"""
Tujuan      : Struktur episode yang dapat diputar ulang (sintetis dari generator atau nyata dari data
              olahan), penyimpanan ke database, dan pemuatan kembali untuk API, simulasi, dan demo.
Lapis       : Simulasi (melintasi S-I-G-A).
Sumber      : sensing/dummy_generator.py (episode sintetis); data/processed atau database
              (hujan IMERG Late nyata, cadangan NASA POWER; titik Glapan nyata) untuk episode nyata
              dengan T-0 sembarang (demo 24 Jan 2025 dan uji balik kejadian kandidat).
Masukan     : Parameter preset, seed, sesi database.
Keluaran    : Objek Episode (atribut id, t0, hujan, prakiraan, muka_air, laporan, kebenaran, label_seri).
Keterbatasan: Episode nyata memakai muka air sintetis berlabel dan prakiraan sintetis (memuat
              informasi masa depan) atau persistensi (A-058) karena arsip prakiraan dan seri muka
              air belum tersedia (A-034); hasil episode nyata belum terkonfirmasi. Hujan harian
              dibagi rata ke 24 jam.
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


MODE_PRAKIRAAN = ("sintetis", "persistensi", "kosong")
LOKASI_KORIDOR = ("lokal", "hulu", "gundih")
NAMA_SUMBER_HUJAN = {"gpm_imerg_late": "GPM IMERG Late (0,1 derajat)", "nasa_power": "NASA POWER"}
KOLOM_PRAKIRAAN = ["waktu_terbit", "waktu", "lokasi", "nilai", "satuan", "sumber", "is_simulated", "resolusi_jam"]


def muat_hujan_imerg_late() -> pd.DataFrame:
    """Hujan harian IMERG Late titik koridor (lokal, hulu, Gundih) dari data/processed; kosong bila belum ada."""
    imerg = baca_olahan("hujan_gpm_imerg")
    if imerg.empty:
        return imerg
    return imerg[(imerg["sumber"] == "gpm_imerg_late") & imerg["lokasi"].isin(LOKASI_KORIDOR)].copy()


def prakiraan_persistensi(hujan: pd.DataFrame, t0: datetime, params: ParamsAktif) -> pd.DataFrame:
    """Prakiraan persistensi tanpa informasi masa depan.

    Pada tiap jam keputusan, laju hujan per jam = nilai TERAKHIR yang sudah tersedia (akhir periode +
    latensi sumber) dibagi resolusinya, untuk setiap periode prakiraan dari jam terbit sampai
    T-0 + sesudah_t0_jam. Dipakai uji balik pada data nyata sebagai pengganti prakiraan sintetis
    (yang dibangkitkan dari hujan aktual sehingga memuat informasi masa depan).
    Kembali:
        Tabel prakiraan standar; is_simulated True karena bukan prakiraan resmi.
    """
    pk = params.dummy["prakiraan"]
    H, interval = params.episode.horizon_jam, params.episode.interval_keputusan_jam
    periode, sesudah = pk["periode_jam"], pk["sesudah_t0_jam"]
    lat = params.inferensi["latensi_jam"]
    baris = []
    for lok in ("lokal", "hulu"):
        d = hujan[hujan["lokasi"] == lok].sort_values("waktu")
        if d.empty:
            continue
        res = d["resolusi_jam"].astype(float).to_numpy() if "resolusi_jam" in d else np.full(len(d), 24.0)
        latensi = d["sumber"].map(lambda s: lat.get(s, 0)).to_numpy(dtype=float)
        tersedia = d["waktu"].to_numpy(dtype="datetime64[ns]") + ((res + latensi) * 3600).astype("timedelta64[s]")
        nilai = d["nilai"].to_numpy(dtype=float)
        for h_terbit in range(-H, 1, interval):
            terbit = pd.Timestamp(t0) + pd.Timedelta(hours=h_terbit)
            ada = np.flatnonzero(tersedia <= terbit.to_datetime64())
            if not len(ada):
                continue
            laju = nilai[ada[-1]] / res[ada[-1]]
            for awal in range(h_terbit, sesudah, periode):
                baris.append((terbit.to_pydatetime(), (pd.Timestamp(t0) + pd.Timedelta(hours=awal)).to_pydatetime(),
                              lok, float(laju * periode)))
    df = pd.DataFrame(baris, columns=["waktu_terbit", "waktu", "lokasi", "nilai"])
    return df.assign(satuan="mm", sumber="prakiraan_persistensi", is_simulated=True, resolusi_jam=periode)


def bangun_episode_hujan_nyata(t0: datetime, id_episode: str, nama: str, params: ParamsAktif | None = None,
                               hujan_harian: pd.DataFrame | None = None, glapan: pd.DataFrame | None = None,
                               skala_hujan: float = 1.0, prakiraan: str = "sintetis",
                               status_hasil: str = "belum terkonfirmasi", keterangan: str = "") -> Episode:
    """Episode nyata untuk T-0 sembarang.

    Isi: hujan harian nyata (IMERG Late; NASA POWER sebagai cadangan), muka air per jam sintetis dari
    hujan itu, titik Glapan nyata yang jatuh dalam jendela episode, dan prakiraan menurut mode.
    Parameter:
        t0: jam acuan T-0 (WIB naif).
        hujan_harian: tabel standar hujan harian (bawaan IMERG Late, cadangan NASA POWER).
        glapan: tabel standar Glapan nyata (bawaan data/processed/muka_air_glapan.csv).
        skala_hujan: pengali seluruh nilai hujan (uji kepekaan bias satelit); 1 = apa adanya.
        prakiraan: 'sintetis' (dari hujan aktual + galat; memuat informasi masa depan),
            'persistensi' (hanya informasi yang tersedia), atau 'kosong'.
    """
    if prakiraan not in MODE_PRAKIRAAN:
        raise ValueError(f"mode prakiraan tidak dikenal: {prakiraan}")
    params = params or muat_params()
    H, A = params.episode.horizon_jam, params.episode.antesedent_hari * 24
    sesudah = params.dummy["prakiraan"]["sesudah_t0_jam"]
    mulai = t0 - timedelta(hours=H + A)
    glapan = baca_olahan("muka_air_glapan") if glapan is None else glapan
    hari_awal = pd.Timestamp(mulai).normalize()
    batas = pd.Timestamp(t0 + timedelta(hours=sesudah))

    def _jendela(df: pd.DataFrame) -> pd.DataFrame:
        """Baris dalam jendela episode, hanya titik koridor (lokal, hulu, Gundih)."""
        pilih = (df["waktu"] >= hari_awal) & (df["waktu"] <= batas) & df["lokasi"].isin(LOKASI_KORIDOR)
        return df[pilih].copy()

    if hujan_harian is None:
        # IMERG Late lebih dulu (hulu terpisah dari lokal; versi yang tersedia pada jam keputusan),
        # NASA POWER sebagai cadangan bila IMERG belum diunduh.
        hujan_harian = muat_hujan_imerg_late()
        if hujan_harian.empty or not {"lokal", "hulu"} <= set(_jendela(hujan_harian)["lokasi"]):
            hujan_harian = baca_olahan("hujan_nasa_power")
    hujan = _jendela(hujan_harian)
    hujan = hujan[["waktu", "lokasi", "nilai", "satuan", "sumber", "is_simulated", "resolusi_jam"]]
    if skala_hujan != 1.0:
        hujan["nilai"] = hujan["nilai"] * float(skala_hujan)
    sumber_hujan = ", ".join(sorted({NAMA_SUMBER_HUJAN.get(s, s) for s in hujan["sumber"]}))

    if prakiraan == "sintetis":
        # Seri per jam (dibagi rata) sebagai "kebenaran" prakiraan sintetis. Grid jam bulat agar
        # sejajar dengan seri per jam hujan walau T-0 bermenit (mis. 22.25).
        jam = pd.date_range(pd.Timestamp(mulai).floor("h"),
                            pd.Timestamp(t0 + timedelta(hours=sesudah)).ceil("h") - pd.Timedelta(hours=1), freq="h")
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
    elif prakiraan == "persistensi":
        pk = prakiraan_persistensi(hujan, t0, params)
    else:
        pk = pd.DataFrame(columns=KOLOM_PRAKIRAAN)
    ma_sint = muka_air_sintetis.jalankan(hujan[hujan["lokasi"] == "hulu"], hujan[hujan["lokasi"] == "lokal"])
    ma_sint = ma_sint[(ma_sint["waktu"] >= mulai) & (ma_sint["waktu"] < t0 + timedelta(hours=sesudah))]
    kolom_ma = ["waktu", "lokasi", "nilai", "satuan", "sumber", "is_simulated"]
    ma_nyata = glapan[(glapan["waktu"] >= pd.Timestamp(mulai)) & (glapan["waktu"] <= batas)][kolom_ma] \
        if len(glapan) else glapan
    bagian = [ma_sint.drop(columns=["kualitas"], errors="ignore")] + ([ma_nyata] if len(ma_nyata) else [])
    muka_air = pd.concat(bagian, ignore_index=True)
    nama_pk = {"sintetis": "prakiraan sintetis berlabel",
               "persistensi": "prakiraan persistensi (tanpa informasi masa depan)",
               "kosong": "tanpa prakiraan"}[prakiraan]
    ket_glapan = "; titik Glapan nyata dalam jendela (rilis BNPB)" if len(ma_nyata) else ""
    ket_skala = f"; hujan dikali {skala_hujan:.3f} (uji kepekaan)" if skala_hujan != 1.0 else ""
    return Episode(
        id=id_episode, nama=nama, jenis="nyata", t0=t0, hujan=hujan.reset_index(drop=True),
        prakiraan=pk, muka_air=muka_air, laporan=pd.DataFrame(columns=KOLOM_LAPORAN),
        kebenaran={"terganggu": None, "mekanisme": None, "skenario_lama_tutup": None},
        is_simulated=False, status_hasil=status_hasil,
        keterangan=(f"Hujan nyata dari {sumber_hujan}{ket_skala}{ket_glapan}; {nama_pk}; "
                    f"muka air per jam sintetis berlabel. {keterangan}").strip(),
        preset=params.preset,
    )


def bangun_episode_nyata(params: ParamsAktif | None = None, hujan_harian: pd.DataFrame | None = None,
                         glapan: pd.DataFrame | None = None) -> Episode:
    """Episode nyata demo (params demo.episode_nyata, malam 24 Jan 2025).

    Hujan IMERG Late nyata (cadangan NASA POWER), titik Glapan nyata, prakiraan dan muka air
    sintetis berlabel.
    Parameter:
        hujan_harian: tabel standar hujan harian; bawaan IMERG Late dari
            data/processed/hujan_gpm_imerg.csv, atau NASA POWER bila IMERG belum ada.
        glapan: tabel standar Glapan nyata (bawaan data/processed/muka_air_glapan.csv).
    """
    params = params or muat_params()
    konf = params.demo["episode_nyata"]
    return bangun_episode_hujan_nyata(
        datetime.fromisoformat(konf["t0"]), konf["id"], konf["nama"], params, hujan_harian, glapan,
        status_hasil=konf["hasil"], keterangan=konf["status_t0"])


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
    repo.hapus_seri_episode(sesi, ep.id)
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
