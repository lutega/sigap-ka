"""
Tujuan      : Menguji pembangun episode nyata umum (T-0 sembarang, skala hujan, mode prakiraan) dan
              uji balik (simulation/uji_balik.py): hujan aktual proporsional, cakupan data, AUC,
              pemindaian harian, serta perbaikan T-0 bermenit (akumulasi dan prakiraan sintetis).
Lapis       : Simulasi/evaluasi, lapis I.
Sumber      : Seri hujan buatan tes (angka uji, bukan data nyata).
Masukan     : -
Keluaran    : -
Keterbatasan: Memakai model lapis I bawaan (dilatih episode sintetis).
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from config import muat_params
from inference.fitur import IndeksEpisode
from simulation import uji_balik as ub
from simulation.episode import bangun_episode_hujan_nyata, prakiraan_persistensi

GLAPAN_KOSONG = pd.DataFrame(columns=["waktu", "lokasi", "nilai", "satuan", "sumber", "is_simulated"])


def _hujan(nilai_hari: dict[str, float] | None = None, dasar: float = 5.0) -> pd.DataFrame:
    """Hujan harian buatan (IMERG Late, hari UTC disimpan pukul 07.00 WIB) Januari 2025."""
    tgl = pd.date_range("2025-01-01 07:00", "2025-01-31 07:00", freq="D")
    baris = []
    for lok in ("lokal", "hulu", "gundih"):
        for t in tgl:
            v = (nilai_hari or {}).get(t.strftime("%Y-%m-%d"), dasar)
            baris.append({"waktu": t, "lokasi": lok, "nilai": v, "satuan": "mm", "sumber": "gpm_imerg_late",
                          "is_simulated": False, "resolusi_jam": 24})
    return pd.DataFrame(baris)


def _ep(t0, **kw):
    return bangun_episode_hujan_nyata(t0, "UJI", "uji", muat_params(), hujan_harian=kw.pop("hujan", _hujan()),
                                      glapan=kw.pop("glapan", GLAPAN_KOSONG), **kw)


def test_akumulasi_tidak_bergantung_menit_t0():
    """Hujan 3 hari pada jam keputusan yang sama tidak berubah bila T-0 bergeser beberapa menit."""
    p = muat_params()
    hujan = _hujan({"2025-01-20": 40.0, "2025-01-21": 30.0, "2025-01-22": 20.0})
    a = IndeksEpisode(_ep(datetime(2025, 1, 24, 21, 0), hujan=hujan), p).fitur_mentah(-24)
    b = IndeksEpisode(_ep(datetime(2025, 1, 24, 21, 25), hujan=hujan), p).fitur_mentah(-24)
    assert a["hujan_lokal_3h"] == pytest.approx(b["hujan_lokal_3h"]) == pytest.approx(90.0)


def test_prakiraan_sintetis_terisi_untuk_t0_bermenit():
    """Prakiraan sintetis tidak nol hanya karena T-0 tidak tepat jam bulat (perbaikan grid jam)."""
    ep = _ep(datetime(2025, 1, 24, 22, 25), hujan=_hujan(dasar=12.0), prakiraan="sintetis")
    assert ep.prakiraan["nilai"].sum() > 0


def test_prakiraan_persistensi_hanya_informasi_tersedia():
    """Hujan hari terakhir yang belum tersedia (latensi 14 jam setelah akhir hari UTC) tidak dipakai."""
    p = muat_params()
    hujan = _hujan({"2025-01-23": 240.0}, dasar=0.0)
    t0 = datetime(2025, 1, 24, 12, 0)   # hari UTC 23 Jan (07.00 23/1 - 07.00 24/1) baru tersedia 21.00 24/1
    pk = prakiraan_persistensi(hujan[hujan["waktu"] < "2025-01-25"], t0, p)
    assert pk["nilai"].max() == 0.0
    t0 = datetime(2025, 1, 25, 0, 0)    # sesudah 21.00 24/1: laju 240/24 = 10 mm/jam -> 30 mm per periode 3 jam
    pk = prakiraan_persistensi(hujan[hujan["waktu"] < "2025-01-25"], t0, p)
    terakhir = pk[pk["waktu_terbit"] == pk["waktu_terbit"].max()]
    assert terakhir["nilai"].max() == pytest.approx(30.0)
    assert pk["is_simulated"].all() and (pk["sumber"] == "prakiraan_persistensi").all()


def test_skala_hujan_dan_jendela_glapan():
    """Skala mengalikan hujan; titik Glapan di luar jendela episode tidak ikut."""
    t0 = datetime(2025, 1, 24, 21, 0)
    glapan = pd.DataFrame({"waktu": pd.to_datetime(["2024-06-01 00:00", "2025-01-24 12:00"]), "lokasi": "glapan",
                           "nilai": [1999.0, 1950.0], "satuan": "cm", "sumber": "glapan_bnpb", "is_simulated": False})
    ep1, ep2 = _ep(t0), _ep(t0, skala_hujan=0.5, glapan=glapan, prakiraan="kosong")
    assert ep2.hujan["nilai"].sum() == pytest.approx(0.5 * ep1.hujan["nilai"].sum())
    nyata = ep2.muka_air[ep2.muka_air["sumber"] == "glapan_bnpb"]
    assert nyata["nilai"].tolist() == [1950.0] and ep2.prakiraan.empty
    with pytest.raises(ValueError):
        _ep(t0, prakiraan="ramalan")


def test_hujan_aktual_proporsional_dan_cakupan():
    """Hujan aktual menghitung bagian hari yang jatuh dalam jendela; cakupan = porsi hari berdata."""
    hujan = _hujan(dasar=24.0)      # 1 mm/jam
    t0 = datetime(2025, 1, 24, 19, 0)
    assert ub.hujan_aktual(hujan, "lokal", t0, 72) == pytest.approx(72.0)
    p = muat_params()
    assert ub.cakupan_data(hujan, t0, p) == 1.0
    assert ub.cakupan_data(hujan[hujan["waktu"] > "2025-01-20"], t0, p) < 0.8


def test_auc_dan_metrik_pemisahan():
    """AUC 1 bila semua hari kejadian di atas hari lain; 0,5 bila seri."""
    assert ub._auc(np.array([0.9, 0.8]), np.array([0.1, 0.2, 0.3])) == 1.0
    assert ub._auc(np.array([0.5]), np.array([0.5])) == 0.5
    assert ub._auc(np.array([]), np.array([0.5])) is None
    pindai = pd.DataFrame({"tanggal": ["a", "b", "c", "d"], "label": ["kejadian", "lain", "lain", "sekitar"],
                           "p_T-0": [0.6, 0.2, 0.4, 0.9]})
    m = ub.metrik_pemisahan(pindai, kolom=("p_T-0",))
    assert m["n_kejadian"] == 1 and m["n_lain"] == 2
    assert m["skor"]["p_T-0"]["auc"] == 1.0 and m["skor"]["p_T-0"]["persentil_kejadian"]["a"] == 100.0
    assert m["skor"]["p_T-0"]["ambang_0.5"]["porsi_kejadian"] == 1.0


def test_uji_balik_kandidat_dan_pindai_harian():
    """Uji balik menghasilkan baris per kandidat x varian, termasuk penanda data kurang; pindai berlabel."""
    p = muat_params()
    hujan = _hujan({"2025-01-19": 90.0, "2025-01-20": 80.0})
    kandidat = pd.DataFrame({"id_kandidat": ["U1", "U2"],
                             "t0": [datetime(2025, 1, 22, 6, 0), datetime(2025, 1, 3, 6, 0)],
                             "jam_diketahui": [True, True], "jenis_gangguan": "tutup_dua_jalur",
                             "mekanisme": "genangan"})
    hasil = ub.uji_balik_kandidat(p, hujan=hujan, kandidat=kandidat, varian=["persistensi", "kosong"])
    assert len(hasil) == 4
    u1 = hasil[(hasil["id_kandidat"] == "U1") & (hasil["prakiraan"] == "persistensi")].iloc[0]
    assert 0 <= u1["p_T-0"] <= 1 and u1["hujan_hulu_3h_tersedia"] > 100
    u2 = hasil[hasil["id_kandidat"] == "U2"]
    assert (u2["catatan"] != "").all()          # jendela sebelum awal data
    kb = ub.kepekaan_bias(p, hujan=hujan, kandidat=kandidat.iloc[:1], skala=[1.0, 0.5])
    assert kb.loc[kb["skala_hujan"] == 0.5, "hujan_hulu_3h_tersedia"].iloc[0] == pytest.approx(
        0.5 * kb.loc[kb["skala_hujan"] == 1.0, "hujan_hulu_3h_tersedia"].iloc[0], abs=0.1)
    ph = ub.pindai_harian(p, hujan=hujan, kandidat=kandidat, mulai="2025-01-15", selesai="2025-01-27")
    assert set(ph["label"]) <= {"kejadian", "sekitar", "lain"}
    assert (ph.loc[ph["tanggal"] == "2025-01-22", "label"] == "kejadian").all()
