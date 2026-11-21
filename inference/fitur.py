"""
Tujuan      : Menyusun vektor fitur lapis I pada jam keputusan dari data episode, hanya memakai
              informasi yang SUDAH tersedia pada jam itu (latensi tiap sumber dan waktu terbit
              prakiraan dihormati).
Lapis       : I (Inferensi).
Sumber      : Objek episode (sintetis atau dari database) dengan atribut t0, hujan, prakiraan,
              muka_air, laporan berformat tabel standar; latensi dan skala fitur dari params.json.
Masukan     : Episode dan jam keputusan.
Keluaran    : dict fitur mentah (mm, cm) dan vektor fitur terskala untuk model.
Keterbatasan: Hujan 1/3/5 hari dihitung sebagai akumulasi yang berakhir pada data terakhir yang
              tersedia (bukan tepat pada jam keputusan) karena tiap sumber punya latensi. Bila
              tidak ada data muka air, elevasi diisi elevasi dasar model sintetis (A-025).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from config import ParamsAktif, muat_params

NAMA_FITUR = ("hujan_lokal_1h", "hujan_lokal_3h", "hujan_lokal_5h", "hujan_hulu_3h",
              "prakiraan_lokal", "prakiraan_hulu", "glapan_relatif", "glapan_tren")


def _jam_relatif(waktu: pd.Series, t0: datetime) -> np.ndarray:
    """Waktu (Series datetime) menjadi jam relatif terhadap T-0 (float)."""
    if len(waktu) == 0:
        return np.zeros(0)
    return ((pd.to_datetime(waktu) - pd.Timestamp(t0)) / pd.Timedelta(hours=1)).to_numpy(dtype=float)


@dataclass
class _SeriHujan:
    """Seri hujan satu lokasi dalam jam relatif: awal, akhir, tersedia, nilai."""

    awal: np.ndarray
    akhir: np.ndarray
    tersedia: np.ndarray
    nilai: np.ndarray

    def akumulasi(self, t: float, jendela_jam: float) -> float:
        """Jumlah hujan dalam jendela yang berakhir pada data terakhir yang tersedia sebelum t."""
        ada = self.tersedia <= t
        if not ada.any():
            return 0.0
        ujung = self.akhir[ada].max()
        pilih = ada & (self.awal >= ujung - jendela_jam)
        return float(np.nansum(self.nilai[pilih]))


class IndeksEpisode:
    """Pra-hitung larik numpy per episode agar fitur cepat dihitung pada banyak jam keputusan.

    Parameter:
        episode: objek dengan atribut t0, hujan, prakiraan, muka_air, laporan.
        params: parameter preset (latensi, skala, ambang Awas).
    """

    def __init__(self, episode, params: ParamsAktif | None = None):
        self.params = params or muat_params()
        self.t0 = episode.t0
        lat = self.params.inferensi["latensi_jam"]
        self.hujan = {lok: self._seri_hujan(episode.hujan, lok, lat) for lok in ("lokal", "hulu")}
        self.prakiraan = {lok: self._seri_prakiraan(episode.prakiraan, lok) for lok in ("lokal", "hulu")}
        ma = episode.muka_air
        ma = ma[ma["lokasi"] == "glapan"] if len(ma) else ma
        if len(ma):
            jam = _jam_relatif(ma["waktu"], self.t0)
            latensi = ma["sumber"].map(lambda s: lat.get(s, 0)).to_numpy(dtype=float)
            urut = np.argsort(jam)
            self.glapan_jam = jam[urut]
            self.glapan_tersedia = (jam + latensi)[urut]
            self.glapan_nilai = ma["nilai"].to_numpy(dtype=float)[urut]
        else:
            self.glapan_jam = self.glapan_tersedia = self.glapan_nilai = np.zeros(0)
        lap = episode.laporan
        if len(lap):
            rel = lap[lap["jenis"] == "air_badan_rel"]
            self.laporan_air = np.sort(_jam_relatif(rel["waktu"], self.t0))
            jp = lap[lap["jenis"] == "jalan_putus"]
            self.laporan_jalan = np.sort(_jam_relatif(jp["waktu"], self.t0))
        else:
            self.laporan_air = self.laporan_jalan = np.zeros(0)

    def _seri_hujan(self, df: pd.DataFrame, lokasi: str, lat: dict) -> _SeriHujan:
        """Larik hujan satu lokasi; tersedia = akhir periode + latensi sumber."""
        d = df[df["lokasi"] == lokasi] if len(df) else df
        if not len(d):
            kosong = np.zeros(0)
            return _SeriHujan(kosong, kosong, kosong, kosong)
        awal = _jam_relatif(d["waktu"], self.t0)
        res = d["resolusi_jam"].to_numpy(dtype=float) if "resolusi_jam" in d else np.ones(len(d))
        latensi = d["sumber"].map(lambda s: lat.get(s, 0)).to_numpy(dtype=float)
        return _SeriHujan(awal, awal + res, awal + res + latensi, d["nilai"].to_numpy(dtype=float))

    def _seri_prakiraan(self, df: pd.DataFrame, lokasi: str) -> dict:
        """Larik prakiraan satu lokasi: waktu terbit, awal periode, nilai."""
        d = df[df["lokasi"] == lokasi] if len(df) else df
        if not len(d):
            return {"terbit": np.zeros(0), "awal": np.zeros(0), "nilai": np.zeros(0)}
        return {"terbit": _jam_relatif(d["waktu_terbit"], self.t0),
                "awal": _jam_relatif(d["waktu"], self.t0),
                "nilai": d["nilai"].to_numpy(dtype=float)}

    def _prakiraan_sampai_t0(self, lokasi: str, t: float) -> float:
        """Jumlah prakiraan terbitan terakhir (terbit <= t) untuk periode dari t sampai T-0."""
        p = self.prakiraan[lokasi]
        sudah = p["terbit"] <= t
        if not sudah.any():
            return 0.0
        terakhir = p["terbit"][sudah].max()
        pilih = (p["terbit"] == terakhir) & (p["awal"] >= t) & (p["awal"] < 0)
        return float(np.nansum(p["nilai"][pilih]))

    def _glapan(self, t: float) -> tuple[float, float]:
        """Elevasi Glapan terakhir yang tersedia dan kenaikannya 6 jam sebelumnya."""
        dasar = self.params.muka_air["sintetis"]["elevasi_dasar"]
        ada = self.glapan_tersedia <= t
        if not ada.any():
            return dasar, 0.0
        jam, nilai = self.glapan_jam[ada], self.glapan_nilai[ada]
        terakhir = nilai[-1]
        sebelum = jam <= jam[-1] - 6
        tren = terakhir - nilai[sebelum][-1] if sebelum.any() else 0.0
        return float(terakhir), float(tren)

    def ada_laporan_air(self, t: float) -> bool:
        """True bila laporan air di badan rel sudah masuk sebelum/pada t."""
        return bool((self.laporan_air <= t).any())

    def ada_laporan_jalan_putus(self, t: float) -> bool:
        """True bila laporan jalan Semarang-Purwodadi putus sudah masuk sebelum/pada t."""
        return bool((self.laporan_jalan <= t).any())

    def fitur_mentah(self, t: float) -> dict[str, float]:
        """Fitur dalam satuan asli pada jam relatif t (jam terhadap T-0, negatif = sebelum)."""
        elev, tren = self._glapan(t)
        awas = self.params.muka_air["ambang_awas"]
        return {
            "hujan_lokal_1h": self.hujan["lokal"].akumulasi(t, 24),
            "hujan_lokal_3h": self.hujan["lokal"].akumulasi(t, 72),
            "hujan_lokal_5h": self.hujan["lokal"].akumulasi(t, 120),
            "hujan_hulu_3h": self.hujan["hulu"].akumulasi(t, 72),
            "prakiraan_lokal": self._prakiraan_sampai_t0("lokal", t),
            "prakiraan_hulu": self._prakiraan_sampai_t0("hulu", t),
            "glapan_relatif": elev - awas,
            "glapan_tren": tren,
        }

    def vektor(self, t: float) -> np.ndarray:
        """Vektor fitur terskala (dibagi skala params.json) pada jam relatif t."""
        return skalakan(self.fitur_mentah(t), self.params)


def skalakan(mentah: dict[str, float], params: ParamsAktif | None = None) -> np.ndarray:
    """Membagi tiap fitur dengan skalanya di params.json (urutan NAMA_FITUR)."""
    params = params or muat_params()
    skala = params.inferensi["fitur"]
    return np.array([mentah[n] / skala[n]["skala"] for n in NAMA_FITUR], dtype=float)


def jam_relatif_keputusan(params: ParamsAktif | None = None) -> list[float]:
    """Daftar jam keputusan relatif T-0: -horizon, ..., -interval, 0."""
    ep = (params or muat_params()).episode
    return [-float(ep.jam_sebelum_t0(k)) for k in range(ep.jumlah_langkah)]
