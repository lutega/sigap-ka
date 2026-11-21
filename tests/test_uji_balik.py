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
    hasil = ub.uji_balik_kandidat(p, hujan=hujan, kandidat=kandidat, varian=["persistensi", "kosong"],
                                  varian_muka_air=["tertunda"])
    assert len(hasil) == 4 and (hasil["muka_air"] == "tertunda").all()
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


def _hujan_jam(mm_per_jam: float = 0.5) -> pd.DataFrame:
    """Hujan per jam buatan (IMERG Late per jam) Januari 2025."""
    jam = pd.date_range("2025-01-01 07:00", "2025-01-31 06:00", freq="h")
    return pd.concat([pd.DataFrame({"waktu": jam, "lokasi": lok, "nilai": mm_per_jam, "satuan": "mm",
                                    "sumber": "gpm_imerg_late_jam", "is_simulated": False, "resolusi_jam": 1})
                      for lok in ("lokal", "hulu", "gundih")], ignore_index=True)


def test_prakiraan_persistensi_per_jam_rerata_24_jam_tersedia():
    """Data per jam: laju = rerata 24 jam terakhir yang tersedia (latensi 14 jam), bukan jam terakhir saja."""
    p = muat_params()
    hujan = _hujan_jam(0.0)
    t0 = datetime(2025, 1, 25, 12, 0)
    # 12 jam bernilai 2 mm yang berakhir tepat 14 jam sebelum T-0 -> tersedia; 24 jam terakhir = 24 mm -> 1 mm/jam
    blok = (hujan["waktu"] >= t0 - pd.Timedelta(hours=26)) & (hujan["waktu"] < t0 - pd.Timedelta(hours=14))
    hujan.loc[blok, "nilai"] = 2.0
    pk = prakiraan_persistensi(hujan, t0, p)
    terakhir = pk[pk["waktu_terbit"] == pk["waktu_terbit"].max()]
    assert terakhir["nilai"].max() == pytest.approx(3.0)   # 1 mm/jam x periode 3 jam


def test_jalankan_per_sumber_dengan_data_per_jam(tmp_path, monkeypatch):
    """Pipeline uji balik: sumber yang belum diunduh dicatat; sumber per jam menulis kandidat_jam.csv."""
    from config import reset_cache
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    reset_cache()
    try:
        _hujan_jam(0.8).to_csv(tmp_path / "hujan_gpm_imerg_jam.csv", index=False)
        r = ub.jalankan(pindai=False, sumber=["harian", "jam"])
        assert "catatan" in r["per_sumber"]["harian"] and r["sumber_utama"] == "jam"
        assert (tmp_path / "uji_balik" / "kandidat_jam.csv").exists()
        dinilai = [k for k in r["kandidat"] if not k.get("catatan")]
        assert {k["id_kandidat"] for k in dinilai} >= {"K02", "K03"}
    finally:
        reset_cache()


def test_muka_air_tertunda_tidak_memakai_hujan_belum_tersedia():
    """Muka air sintetis tertunda (data per jam): pada T-0 yang terbaca adalah nilai T-15 (1 jam + latensi 14)."""
    p = muat_params()
    hujan = _hujan_jam(0.2)
    blok = (hujan["waktu"] >= "2025-01-24 00:00") & (hujan["waktu"] < "2025-01-25 00:00")
    hujan.loc[blok, "nilai"] = 8.0
    t0 = datetime(2025, 1, 25, 0, 0)
    nyata = _ep(t0, hujan=hujan, prakiraan="kosong")
    tunda = _ep(t0, hujan=hujan, prakiraan="kosong", muka_air_tertunda=True)
    assert (tunda.muka_air["sumber"] == "muka_air_sintetis_tertunda_jam").all()
    seri = nyata.muka_air[nyata.muka_air["lokasi"] == "glapan"].set_index("waktu")["nilai"]
    elev_tunda = IndeksEpisode(tunda, p).fitur_mentah(0.0)["glapan_relatif"] + p.muka_air["ambang_awas"]
    elev_nyata = IndeksEpisode(nyata, p).fitur_mentah(0.0)["glapan_relatif"] + p.muka_air["ambang_awas"]
    assert elev_tunda == pytest.approx(seri.loc[pd.Timestamp(t0) - pd.Timedelta(hours=15)])
    assert elev_nyata > elev_tunda      # hujan 24/1 sudah menaikkan muka air waktu nyata
    with pytest.raises(ValueError):
        ub._tertunda("kemarin")


def test_auc_selang_bootstrap():
    """Selang bootstrap memuat AUC titik dan tetap untuk seed sama; terlalu sedikit data -> None."""
    pos, neg = np.array([0.9, 0.6, 0.4]), np.array([0.1, 0.2, 0.5, 0.3, 0.7])
    a = ub.auc_selang(pos, neg, n=500, seed=1)
    assert a == ub.auc_selang(pos, neg, n=500, seed=1)
    assert a[0] <= ub._auc(pos, neg) <= a[1]
    assert ub.auc_selang(np.array([0.5]), neg) is None


def test_muat_hujan_hulu_das_mengganti_hulu(tmp_path, monkeypatch):
    """hulu_das=True: baris hulu diganti rerata DAS, lokal/Gundih tetap; tanpa berkas DAS -> kosong."""
    from config import reset_cache
    from simulation.episode import muat_hujan_imerg_late
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    reset_cache()
    try:
        _hujan().to_csv(tmp_path / "hujan_gpm_imerg.csv", index=False)
        assert muat_hujan_imerg_late(hulu_das=True).empty
        das = _hujan(dasar=9.0)
        das = das[das["lokasi"] == "hulu"].assign(sumber="gpm_imerg_late_das")
        das.to_csv(tmp_path / "hujan_gpm_imerg_das.csv", index=False)
        h = muat_hujan_imerg_late(hulu_das=True)
        assert (h.loc[h["lokasi"] == "hulu", "nilai"] == 9.0).all()
        assert (h.loc[h["lokasi"] == "lokal", "nilai"] == 5.0).all()
    finally:
        reset_cache()
