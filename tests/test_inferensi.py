"""
Tujuan      : Menguji lapis I: fitur tanpa intip masa depan, model logistik multinomial Bayesian,
              mekanisme, lama tutup, pembaruan laporan lapangan, kasus mirip E3/E6, sensitivitas
              prior, dan kinerja pada episode sintetis uji.
Lapis       : QA, lapis I.
Sumber      : Episode buatan tes dan generator dummy.
Masukan     : -
Keluaran    : -
Keterbatasan: Kinerja yang diuji adalah terhadap data sintetis (asumsi generator), bukan nyata.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from config import muat_params
from inference import lama_tutup, mekanisme
from inference.estimasi import Estimator, data_latih, model_bawaan
from inference.fitur import NAMA_FITUR, IndeksEpisode, jam_relatif_keputusan
from inference.peluang_gangguan import ModelPeluang, perbarui_dengan_laporan, prior_dari_params
from sensing import dummy_generator

T0 = datetime(2100, 1, 1, 21)


def buat_episode(lokal_mm: float, hulu_mm: float, glapan: float = 1800.0,
                 laporan_jam: float | None = None, prakiraan_faktor: float = 1.0):
    """Episode buatan: hujan merata 48 jam sebelum T-0, prakiraan = sisa hujan x faktor."""
    jam = pd.date_range(T0 - timedelta(hours=192), T0 - timedelta(hours=1), freq="h")
    rel = np.arange(-192, 0)
    badai = rel >= -48
    baris = []
    for lok, total in (("lokal", lokal_mm), ("hulu", hulu_mm)):
        nilai = np.where(badai, total / 48.0, 0.0)
        baris.append(pd.DataFrame({"waktu": jam, "lokasi": lok, "nilai": nilai}))
    hujan = pd.concat(baris).assign(satuan="mm", sumber="dummy_generator", is_simulated=True, resolusi_jam=1)
    pk = []
    for h in range(-72, 1, 6):
        for lok, total in (("lokal", lokal_mm), ("hulu", hulu_mm)):
            for a in range(h, 0, 3):
                sisa = total / 48.0 * 3 if a >= -48 else 0.0
                pk.append((T0 + timedelta(hours=h), T0 + timedelta(hours=a), lok, sisa * prakiraan_faktor))
    prakiraan = pd.DataFrame(pk, columns=["waktu_terbit", "waktu", "lokasi", "nilai"]).assign(
        satuan="mm", sumber="dummy_generator", is_simulated=True, resolusi_jam=3)
    muka_air = pd.DataFrame({"waktu": jam, "lokasi": "glapan", "nilai": glapan, "satuan": "cm",
                             "sumber": "muka_air_sintetis", "is_simulated": True})
    lap = pd.DataFrame(columns=["waktu", "jenis", "isi", "sumber", "is_simulated"])
    if laporan_jam is not None:
        lap = pd.DataFrame({"waktu": [T0 + timedelta(hours=laporan_jam)], "jenis": ["air_badan_rel"],
                            "isi": ["uji"], "sumber": ["uji"], "is_simulated": [True]})
    return SimpleNamespace(id="UJI", t0=T0, hujan=hujan, prakiraan=prakiraan, muka_air=muka_air, laporan=lap)


@pytest.fixture(scope="module")
def model():
    """Model bawaan preset base (dilatih sekali per modul tes)."""
    return model_bawaan("base")


# ---------------------------------------------------------------- fitur

def test_fitur_tanpa_intip_masa_depan():
    """Mengubah data sesudah jam keputusan tidak mengubah fitur pada jam itu."""
    ep = buat_episode(80, 90)
    t = -24.0
    sebelum = IndeksEpisode(ep).vektor(t)
    ep.hujan.loc[ep.hujan["waktu"] >= T0 - timedelta(hours=24), "nilai"] = 999.0
    ep.prakiraan.loc[ep.prakiraan["waktu_terbit"] > T0 - timedelta(hours=24), "nilai"] = 999.0
    # pembacaan tepat pada jam t sah dipakai (latensi 0); yang sesudahnya tidak boleh
    ep.muka_air.loc[ep.muka_air["waktu"] > T0 - timedelta(hours=24), "nilai"] = 2500.0
    ep.laporan = pd.DataFrame({"waktu": [T0 - timedelta(hours=1)], "jenis": ["air_badan_rel"],
                               "isi": ["x"], "sumber": ["x"], "is_simulated": [True]})
    idx = IndeksEpisode(ep)
    np.testing.assert_allclose(idx.vektor(t), sebelum)
    assert not idx.ada_laporan_air(t)


def test_latensi_sumber_dihormati():
    """Hujan dalam rentang latensi (dummy 3 jam) belum terhitung pada jam keputusan."""
    lat = muat_params().inferensi["latensi_jam"]["dummy_generator"]
    ep = buat_episode(0, 0)
    ep.hujan.loc[(ep.hujan["lokasi"] == "lokal") & (ep.hujan["waktu"] == T0 - timedelta(hours=7)), "nilai"] = 50.0
    idx = IndeksEpisode(ep)
    # hujan jam -7 (berakhir -6) tersedia pada -6 + latensi
    assert idx.fitur_mentah(-6.0 + lat - 0.5)["hujan_lokal_1h"] == 0.0
    assert idx.fitur_mentah(-6.0 + lat)["hujan_lokal_1h"] == pytest.approx(50.0)


def test_prakiraan_terbitan_terakhir_sampai_t0():
    """Fitur prakiraan memakai terbitan terakhir yang sudah ada dan hanya periode t..T-0."""
    ep = buat_episode(48, 48)
    m = IndeksEpisode(ep).fitur_mentah(-24.0)
    assert m["prakiraan_lokal"] == pytest.approx(24.0)  # 24 jam tersisa x 1 mm/jam
    assert IndeksEpisode(ep).fitur_mentah(-80.0)["prakiraan_lokal"] == 0.0  # belum ada terbitan


def test_muka_air_kosong_diisi_elevasi_dasar():
    """Tanpa data Glapan, elevasi diisi elevasi dasar model sintetis (A-025)."""
    ep = buat_episode(10, 10)
    ep.muka_air = ep.muka_air.iloc[0:0]
    p = muat_params()
    assert IndeksEpisode(ep).fitur_mentah(-24)["glapan_relatif"] == \
        p.muka_air["sintetis"]["elevasi_dasar"] - p.muka_air["ambang_awas"]


# ---------------------------------------------------------------- model

def test_prior_mengikuti_preset():
    """Preset low/base/high mengubah rerata dan simpangan prior."""
    mu_low, sd_low = prior_dari_params(muat_params("low"))
    mu_high, sd_high = prior_dari_params(muat_params("high"))
    assert np.all(np.abs(mu_high[:, 1:]) >= np.abs(mu_low[:, 1:]))
    assert np.all(sd_high > sd_low)


def test_peluang_valid_dan_berjumlah_satu(model):
    """Peluang tiap kelas dalam [0, 1] dan berjumlah 1; total = genangan + gerusan."""
    X = np.random.default_rng(0).normal(0, 1, (50, len(NAMA_FITUR)))
    P = model.prediksi(X)
    assert np.all((P >= 0) & (P <= 1))
    np.testing.assert_allclose(P.sum(axis=1), 1.0)


def test_prediksi_dapat_diulang(model):
    """Prediksi Monte Carlo memakai seed tetap (hasil identik)."""
    x = np.ones(len(NAMA_FITUR))
    m2 = ModelPeluang(params=model.params, w_map=model.w_map, kovarians=model.kovarians)
    np.testing.assert_allclose(model.prediksi(x), m2.prediksi(x))


def test_model_terlatih_menangkap_arah_fisik(model):
    """Hujan lokal 3 hari menaikkan genangan; hujan hulu menaikkan gerusan (spesifikasi 9.2)."""
    i_lok = 1 + NAMA_FITUR.index("hujan_lokal_3h")
    i_hulu = 1 + NAMA_FITUR.index("hujan_hulu_3h")
    assert model.w_map[0, i_lok] > 0
    assert model.w_map[1, i_hulu] > 0
    assert np.all(np.linalg.eigvalsh(model.kovarians) > 0)  # kovarians Laplace definit positif


def test_laporan_lapangan_menaikkan_peluang_tajam():
    """Laporan air di badan rel menaikkan peluang dan mempertahankan porsi mekanisme."""
    p = np.array([0.8, 0.15, 0.05])
    q = perbarui_dengan_laporan(p, True)
    assert q[1] + q[2] > 0.7
    assert q[1] / q[2] == pytest.approx(3.0)
    np.testing.assert_allclose(perbarui_dengan_laporan(p, False), p)


# ---------------------------------------------------------------- mekanisme dan lama tutup

def test_mekanisme_dan_bukti_utama(model):
    """Mekanisme dominan dan bukti utama berurutan menurut besar kontribusi."""
    m = mekanisme.tentukan(np.array([0.5, 0.1, 0.4]))
    assert m["dominan"] == "gerusan" and m["porsi_gerusan"] == pytest.approx(0.8)
    ep = buat_episode(40, 150, glapan=2000)
    idx = IndeksEpisode(ep)
    p = model.prediksi(idx.vektor(-12))
    bukti = mekanisme.bukti_utama(model, idx.vektor(-12), idx.fitur_mentah(-12), p)
    assert len(bukti) == 3
    assert abs(bukti[0]["kontribusi"]) >= abs(bukti[1]["kontribusi"]) >= abs(bukti[2]["kontribusi"])


def test_lama_tutup_bergantung_mekanisme():
    """Genangan condong ke skenario pendek, gerusan ke panjang; sebaran berjumlah 1."""
    g = lama_tutup.ringkas(np.array([0.5, 0.5, 0.0]))
    s = lama_tutup.ringkas(np.array([0.5, 0.0, 0.5]))
    assert sum(g["sebaran"].values()) == pytest.approx(1.0)
    assert max(g["sebaran"], key=g["sebaran"].get) == "pendek"
    assert max(s["sebaran"], key=s["sebaran"].get) == "panjang"
    assert s["harapan_jam"] > g["harapan_jam"] and s["faktor_L"] > g["faktor_L"]
    bawaan = lama_tutup.sebaran(np.array([1.0, 0.0, 0.0]))  # tanpa peluang gangguan -> campuran bawaan
    assert sum(bawaan.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------- estimasi episode

def test_hasil_inferensi_lengkap(model):
    """HasilInferensi memuat peluang total = genangan + gerusan untuk semua jam keputusan."""
    est = Estimator(model)
    hasil = est.estimasi_episode(buat_episode(90, 100, glapan=1950))
    assert [h.jam_sebelum_t0 for h in hasil] == [int(-t) for t in jam_relatif_keputusan()]
    for h in hasil:
        assert h.peluang == pytest.approx(h.peluang_genangan + h.peluang_gerusan)
        assert 0 <= h.peluang <= 1
        assert h.mekanisme_dominan in ("genangan", "gerusan")
        assert "aman" not in str(h.ke_dict()).lower().split()


def test_kasus_mirip_e3_e6_bukti_hulu(model):
    """Hujan lokal rendah tetapi hulu dan Glapan tinggi memberi peluang jauh di atas kasus kering."""
    est = Estimator(model)
    kering = est.estimasi(buat_episode(15, 15, glapan=1750), 6)
    hulu = est.estimasi(buat_episode(15, 160, glapan=2050), 6)
    assert hulu.peluang > kering.peluang + 0.2
    assert hulu.mekanisme_dominan == "gerusan"


def test_laporan_pada_estimasi_episode(model):
    """Laporan lapangan yang masuk pada T-10 menaikkan peluang mulai T-6, tidak sebelumnya."""
    est = Estimator(model)
    tanpa = est.estimasi_episode(buat_episode(50, 50))
    dengan = est.estimasi_episode(buat_episode(50, 50, laporan_jam=-10))
    jam = [h.jam_sebelum_t0 for h in tanpa]
    for a, b, j in zip(tanpa, dengan, jam):
        if j > 10:
            assert b.peluang == pytest.approx(a.peluang)
        else:
            assert b.peluang > a.peluang and b.laporan_air_badan_rel


def test_sensitivitas_prior_low_base_high():
    """Model prior-saja berbeda antar preset (uji sensitivitas prior tercatat)."""
    x = IndeksEpisode(buat_episode(100, 100, glapan=1950)).vektor(-12)
    p = {pr: ModelPeluang(params=muat_params(pr)).prediksi(x)[1:].sum() for pr in ("low", "base", "high")}
    assert len({round(v, 4) for v in p.values()}) == 3


def test_kinerja_pada_episode_sintetis_uji(model):
    """AUC pada episode uji (seed berbeda dari latih) membaik mendekati T-0 dan > 0,75 pada T-24."""
    est = Estimator(model)
    uji = dummy_generator.ambil(200, 4242, "base")
    P = np.array([est.peluang_episode(e) for e in uji])
    y = np.array([e.kebenaran["terganggu"] for e in uji])

    def auc(s):
        urut = np.argsort(s)
        rank = np.empty(len(s))
        rank[urut] = np.arange(1, len(s) + 1)
        n1, n0 = y.sum(), len(y) - y.sum()
        return (rank[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
    jam = jam_relatif_keputusan()
    k24 = jam.index(-24.0)
    assert auc(P[:, k24]) > 0.75
    assert auc(P[:, -1]) > auc(P[:, 0])


def test_data_latih_berlabel_kelas():
    """Data latih: satu baris per episode per jam keputusan, label 0/1/2."""
    eps = dummy_generator.ambil(5, 1, "base")
    X, y = data_latih(eps)
    assert X.shape == (5 * len(jam_relatif_keputusan()), len(NAMA_FITUR))
    assert set(np.unique(y)) <= {0, 1, 2}
