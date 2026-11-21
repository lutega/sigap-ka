"""
Tujuan      : Membangkitkan episode hujan lebat sintetis (hujan lokal/hulu/Gundih per jam,
              prakiraan per terbitan, muka air sintetis, laporan lapangan, dan "kebenaran"
              gangguan) untuk simulasi kebijakan, pelatihan lapis I, dan mode demo.
Lapis       : S (Sensing), sintetis berlabel.
Sumber      : Parameter preset di params.json (blok dummy, episode, muka_air, lama_tutup).
Masukan     : Jumlah episode, seed, preset.
Keluaran    : Daftar EpisodeSintetis; ke_format_standar() menghasilkan tabel standar hujan,
              prakiraan, dan muka air. Semua baris is_simulated = True.
Keterbatasan: Proses hujan, galat prakiraan, dan model kebenaran gangguan adalah rancangan
              pengembang (A-010, A-021), bukan hasil kalibrasi. Tanggal episode sintetis
              sengaja di tahun 2100 agar tidak tertukar dengan kejadian nyata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from config import ParamsAktif, muat_params
from sensing import muka_air_sintetis
from sensing.standar import batas_kualitas, tandai_kualitas, validasi_standar

NAMA_SUMBER = "dummy_generator"
KELAS = ("tidak", "genangan", "gerusan")


@dataclass
class EpisodeSintetis:
    """Satu episode sintetis lengkap beserta kebenarannya (hanya dipakai untuk evaluasi)."""

    id: str
    t0: datetime
    preset: str
    seed: int
    hujan: pd.DataFrame
    prakiraan: pd.DataFrame
    muka_air: pd.DataFrame
    laporan: pd.DataFrame
    kebenaran: dict = field(default_factory=dict)


def _sebar(total: float, n: int, rng: np.random.Generator, bentuk: float = 0.6) -> np.ndarray:
    """Membagi total hujan ke n jam secara acak (bobot gamma ternormalisasi)."""
    if n <= 0:
        return np.zeros(0)
    w = rng.gamma(bentuk, 1.0, n)
    return total * w / w.sum()


def _badai(total: float, jam_relatif: np.ndarray, puncak: float, lebar: float,
           rng: np.random.Generator) -> np.ndarray:
    """Hujan badai per jam: amplop Gauss di sekitar puncak dikali derau gamma, berjumlah total.

    Parameter:
        jam_relatif: jam relatif terhadap T-0 (negatif = sebelum T-0).
        puncak: jam relatif puncak badai.
    """
    amplop = np.exp(-0.5 * ((jam_relatif - puncak) / lebar) ** 2)
    w = amplop * rng.gamma(1.5, 1.0, len(jam_relatif))
    return total * w / w.sum()


def _lognormal_berkorelasi(rng: np.random.Generator, rho: float, z_dasar: float) -> float:
    """Variabel normal baku berkorelasi rho dengan z_dasar."""
    return rho * z_dasar + np.sqrt(1.0 - rho ** 2) * rng.standard_normal()


def _softmax3(eta_g: float, eta_s: float) -> np.ndarray:
    """Peluang (tidak, genangan, gerusan) dari dua logit terhadap kelas 'tidak'."""
    e = np.exp(np.array([0.0, eta_g, eta_s]) - max(0.0, eta_g, eta_s))
    return e / e.sum()


def fitur_kebenaran(hujan_lokal: np.ndarray, hujan_hulu: np.ndarray, elevasi: np.ndarray,
                    jam_relatif: np.ndarray, awas: float) -> dict[str, float]:
    """Fitur model kebenaran dari data teramati sampai T-0 (tidak dipakai lapis I).

    Kembali:
        dict hujan_lokal_3h (mm/100), hujan_lokal_5h (mm/150), hujan_hulu_3h (mm/100),
        glapan_puncak_relatif ((elevasi maks 72 jam - Awas)/100).
    """
    sblm = jam_relatif < 0
    j3 = sblm & (jam_relatif >= -72)
    j5 = sblm & (jam_relatif >= -120)
    return {
        "hujan_lokal_3h": hujan_lokal[j3].sum() / 100.0,
        "hujan_lokal_5h": hujan_lokal[j5].sum() / 150.0,
        "hujan_hulu_3h": hujan_hulu[j3].sum() / 100.0,
        "glapan_puncak_relatif": (elevasi[j3].max() - awas) / 100.0,
    }


def bangkitkan_prakiraan(jam_rel: np.ndarray, lokal: np.ndarray, hulu: np.ndarray, t0: datetime,
                         params: ParamsAktif, rng: np.random.Generator) -> list[tuple]:
    """Prakiraan sintetis dari hujan "benar" per jam: terbit tiap jam keputusan, periode 3 jam.

    Galat lognormal per terbitan mengecil linear terhadap lead time (sigma lead maks -> lead nol),
    berkorelasi antarterbitan (AR-1) dan antara lokal-hulu, ditambah derau per periode; dipakai
    untuk episode sintetis dan untuk prakiraan sintetis episode nyata (arsip prakiraan tidak ada).
    Parameter:
        jam_rel: jam relatif T-0 untuk tiap nilai seri (per jam).
        lokal, hulu: hujan per jam (mm).
    Kembali:
        Daftar (waktu_terbit, waktu awal periode, lokasi, nilai mm).
    """
    pk = params.dummy["prakiraan"]
    H = params.episode.horizon_jam
    interval = params.episode.interval_keputusan_jam
    periode, sesudah = pk["periode_jam"], pk["sesudah_t0_jam"]
    baris = []
    e_lok = e_hulu = 0.0
    for k, h_terbit in enumerate(range(-H, 1, interval)):
        lead = -h_terbit
        sig = pk["sigma_log_lead_nol"] + (pk["sigma_log_lead_maks"] - pk["sigma_log_lead_nol"]) * lead / H
        r = pk["korelasi_antarterbitan"] if k else 0.0
        z1 = rng.standard_normal()
        e_lok = r * e_lok + np.sqrt(1 - r ** 2) * z1
        e_hulu = r * e_hulu + np.sqrt(1 - r ** 2) * _lognormal_berkorelasi(rng, pk["korelasi_lokal_hulu"], z1)
        for lok, seri, e in (("lokal", lokal, e_lok), ("hulu", hulu, e_hulu)):
            for awal in range(h_terbit, sesudah, periode):
                sel = (jam_rel >= awal) & (jam_rel < awal + periode)
                benar = seri[sel].sum()
                sp = pk["sigma_log_per_periode"]
                faktor = np.exp(sig * e - sig ** 2 / 2) * np.exp(sp * rng.standard_normal() - sp ** 2 / 2)
                baris.append((t0 + timedelta(hours=h_terbit), t0 + timedelta(hours=awal), lok,
                              float(benar * faktor)))
    return baris


def bangkitkan_episode(rng: np.random.Generator, params: ParamsAktif, episode_id: str,
                       t0: datetime, seed: int) -> EpisodeSintetis:
    """Membangkitkan satu episode sintetis.

    Parameter:
        rng: generator acak episode ini.
        params: parameter preset aktif.
        episode_id: id episode (mis. 'SIN-0001').
        t0: jam acuan T-0.
        seed: seed yang menghasilkan rng (dicatat).
    Kembali:
        EpisodeSintetis.
    """
    d = params.dummy
    H = params.episode.horizon_jam
    A = params.episode.antesedent_hari * 24
    sesudah = d["prakiraan"]["sesudah_t0_jam"]
    jam_rel = np.arange(-(H + A), sesudah, dtype=float)  # jam relatif T-0, sampai T+sesudah
    waktu = [t0 + timedelta(hours=float(h)) for h in jam_rel]
    n = len(jam_rel)
    sigma, rho = d["sigma_log_hujan"], d["korelasi_lokal_hulu"]

    # 1. Hujan anteseden (5 hari sebelum horizon)
    z_a = rng.standard_normal()
    a_lok = d["antesedent_median_mm"] * np.exp(sigma * z_a)
    a_hulu = d["antesedent_median_mm"] * d["hujan_hulu_median_mm"] / d["hujan_lokal_median_mm"] \
        * np.exp(sigma * _lognormal_berkorelasi(rng, rho, z_a))
    lokal, hulu, gundih = np.zeros(n), np.zeros(n), np.zeros(n)
    ante = jam_rel < -H
    lokal[ante] = _sebar(a_lok, ante.sum(), rng)
    hulu[ante] = _sebar(a_hulu, ante.sum(), rng)
    gundih[ante] = _sebar(a_lok, ante.sum(), rng)

    # 2. Badai pada horizon keputusan (total berkorelasi antar lokasi)
    z_l = rng.standard_normal()
    s_lok = d["hujan_lokal_median_mm"] * np.exp(sigma * z_l)
    s_hulu = d["hujan_hulu_median_mm"] * np.exp(sigma * _lognormal_berkorelasi(rng, rho, z_l))
    s_gun = d["hujan_lokal_median_mm"] * np.exp(
        sigma * _lognormal_berkorelasi(rng, d["korelasi_hujan_gundih"], z_l))
    b = d["badai"]
    puncak = -rng.uniform(b["puncak_sebelum_t0_jam_min"], b["puncak_sebelum_t0_jam_maks"])
    puncak_hulu = puncak - rng.uniform(0, 6)  # hujan hulu cenderung lebih awal
    badai = ~ante
    lokal[badai] += _badai(s_lok, jam_rel[badai], puncak, b["lebar_jam"], rng)
    hulu[badai] += _badai(s_hulu, jam_rel[badai], puncak_hulu, b["lebar_jam"], rng)
    gundih[badai] += _badai(s_gun, jam_rel[badai], puncak + rng.uniform(-6, 6), b["lebar_jam"], rng)

    # 3. Muka air sintetis dari hujan hulu
    ma = params.muka_air
    s = muka_air_sintetis.hitung_tampungan(hulu, ma["sintetis"]["konstanta_waduk_jam"],
                                           ma["sintetis"]["tampungan_awal_mm"])
    elev = muka_air_sintetis.elevasi(s)
    idx_rel = muka_air_sintetis.indeks_badan_rel(pd.Series(lokal, index=pd.DatetimeIndex(waktu)))

    # 4. Kebenaran gangguan (multinomial logistik "kebenaran")
    f = fitur_kebenaran(lokal, hulu, elev, jam_rel, ma["ambang_awas"])
    kb = d["kebenaran"]
    eta = {m: kb[m]["intersep"] + sum(kb[m][k] * v for k, v in f.items()) for m in ("genangan", "gerusan")}
    peluang = _softmax3(eta["genangan"], eta["gerusan"])
    kelas = KELAS[rng.choice(3, p=peluang)]
    terganggu = kelas != "tidak"
    skenario, lama = None, None
    if terganggu:
        lt = params.lama_tutup
        sebaran = lt.peluang_bersyarat[kelas]
        skenario = rng.choice(list(sebaran), p=list(sebaran.values()))
        sk = lt.skenario[skenario]
        lama = float(rng.uniform(sk.jam_min, sk.jam_maks))

    # 5. Prakiraan: terbit tiap jam keputusan, periode 3 jam dari waktu terbit sampai T+sesudah
    periode = d["prakiraan"]["periode_jam"]
    baris_pk = bangkitkan_prakiraan(jam_rel, lokal, hulu, t0, params, rng)

    # 6. Laporan lapangan dan jalan putus
    lp = d["laporan_lapangan"]
    laporan = []
    if terganggu and rng.random() < lp["peluang_lapor_bila_terganggu"]:
        laporan.append((t0 - timedelta(hours=float(rng.uniform(0, lp["lapor_sebelum_t0_jam_maks"]))),
                        "air_badan_rel", "Petugas melaporkan air mulai menggenangi badan rel (sintetis)"))
    elif not terganggu and rng.random() < lp["peluang_lapor_palsu"]:
        laporan.append((t0 - timedelta(hours=float(rng.uniform(0, lp["lapor_sebelum_t0_jam_maks"]))),
                        "air_badan_rel", "Laporan air di badan rel (sintetis, ternyata tidak berlanjut)"))
    jp = d["jalan_putus"]
    if s_lok >= jp["ambang_hujan_lokal_mm"] and rng.random() < jp["peluang_bila_hujan_lebat"]:
        laporan.append((t0 - timedelta(hours=float(rng.uniform(0, 24))), "jalan_putus",
                        "Jalan Semarang-Purwodadi dilaporkan terputus (sintetis)"))

    # Rakit tabel standar
    wkt = pd.DatetimeIndex(waktu)
    hujan = pd.concat([
        pd.DataFrame({"waktu": wkt, "lokasi": lok, "nilai": seri}) for lok, seri in
        (("lokal", lokal), ("hulu", hulu), ("gundih", gundih))
    ], ignore_index=True).assign(satuan="mm", sumber=NAMA_SUMBER, is_simulated=True, resolusi_jam=1)
    prakiraan = pd.DataFrame(baris_pk, columns=["waktu_terbit", "waktu", "lokasi", "nilai"]).assign(
        satuan="mm", sumber=NAMA_SUMBER, is_simulated=True, resolusi_jam=periode)
    muka_air = pd.concat([
        pd.DataFrame({"waktu": wkt, "lokasi": "glapan", "nilai": elev, "satuan": "cm (sintetis)"}),
        pd.DataFrame({"waktu": wkt, "lokasi": "badan_rel", "nilai": idx_rel.to_numpy(), "satuan": "indeks"}),
    ], ignore_index=True).assign(sumber="muka_air_sintetis", is_simulated=True)
    lap = pd.DataFrame(laporan, columns=["waktu", "jenis", "isi"]).assign(
        sumber=NAMA_SUMBER, is_simulated=True)
    lap["waktu"] = pd.to_datetime(lap["waktu"])

    return EpisodeSintetis(
        id=episode_id, t0=t0, preset=params.preset, seed=seed,
        hujan=hujan, prakiraan=prakiraan, muka_air=muka_air, laporan=lap,
        kebenaran={
            "terganggu": bool(terganggu), "mekanisme": kelas if terganggu else None,
            "skenario_lama_tutup": skenario, "lama_tutup_jam": lama,
            "peluang_kebenaran": {"genangan": float(peluang[1]), "gerusan": float(peluang[2])},
            "fitur_kebenaran": {k: float(v) for k, v in f.items()},
            "hujan_badai_lokal_mm": float(s_lok), "hujan_badai_hulu_mm": float(s_hulu),
        },
    )


def ambil(n: int, seed: int, preset: str | None = None, awalan: str = "SIN",
          mulai_nomor: int = 1) -> list[EpisodeSintetis]:
    """Membangkitkan n episode sintetis yang dapat diulang (seed sama -> hasil sama).

    Parameter:
        n: jumlah episode.
        seed: seed induk; tiap episode mendapat aliran acak sendiri (SeedSequence.spawn).
        preset: preset parameter; bawaan PARAMS_PRESET.
        awalan: awalan id episode.
        mulai_nomor: nomor episode pertama.
    Kembali:
        Daftar EpisodeSintetis.
    """
    params = muat_params(preset)
    d = params.dummy
    t0_dasar = datetime.fromisoformat(d["t0_dasar"])
    jarak = timedelta(days=d["jarak_antarepisode_hari"])
    anak = np.random.SeedSequence(seed).spawn(n)
    hasil = []
    for i, ss in enumerate(anak):
        nomor = mulai_nomor + i
        hasil.append(bangkitkan_episode(np.random.default_rng(ss), params, f"{awalan}-{nomor:04d}",
                                        t0_dasar + jarak * (nomor - 1), seed))
    return hasil


def ke_format_standar(ep: EpisodeSintetis) -> dict[str, pd.DataFrame]:
    """Tabel standar tervalidasi untuk satu episode: hujan, prakiraan, muka_air."""
    return {
        "hujan": validasi_standar(ep.hujan),
        "prakiraan": validasi_standar(ep.prakiraan, prakiraan=True),
        "muka_air": validasi_standar(ep.muka_air),
    }


def cek_kualitas(tabel: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Menandai nilai janggal pada tabel sintetis (pengaman bila parameter generator diubah)."""
    b = batas_kualitas()
    glapan = tabel["muka_air"]["lokasi"] == "glapan"
    ma = tabel["muka_air"].copy()
    ma.loc[glapan, "kualitas"] = tandai_kualitas(ma[glapan], b["muka_air_min"], b["muka_air_maks"])["kualitas"]
    ma.loc[~glapan, "kualitas"] = tandai_kualitas(ma[~glapan], 0.0, None)["kualitas"]
    return {
        "hujan": tandai_kualitas(tabel["hujan"], 0.0, b["hujan_jam_maks_mm"]),
        "prakiraan": tandai_kualitas(tabel["prakiraan"], 0.0, b["hujan_jam_maks_mm"] * 3),
        "muka_air": ma,
    }


def jalankan(n: int, seed: int, preset: str | None = None) -> list[EpisodeSintetis]:
    """Pipeline ambil -> ke_format_standar (validasi) untuk n episode."""
    episode = ambil(n, seed, preset)
    for ep in episode:
        ke_format_standar(ep)
    return episode
