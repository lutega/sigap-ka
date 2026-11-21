"""
Tujuan      : Menguji simulasi: definisi enam kebijakan, biaya per episode (FR-E2), keterulangan
              (NFR-4, FR-E3), informasi sempurna sebagai batas bawah, perbandingan SIGAP,
              metrik POD/FAR/CSI (FR-E4), episode nyata 24 Jan 2025, dan penyimpanan ke database.
Lapis       : QA, simulasi.
Sumber      : Generator dummy, data/processed (NASA POWER nyata, Glapan), database SQLite.
Masukan     : -
Keluaran    : -
Keterbatasan: Angka biaya memakai parameter dummy.
"""

import numpy as np
import pandas as pd
import pytest

from config import muat_params
from inference.estimasi import Estimator, model_bawaan
from simulation import evaluasi, kebijakan
from simulation.episode import (
    bangun_episode_nyata,
    episode_cadangan,
    episode_sintetis,
    muat_dari_db,
    simpan_ke_db,
)


@pytest.fixture(scope="module")
def hasil_base():
    """Simulasi resmi: 300 episode preset base, seed 42 (spesifikasi 4.6)."""
    return evaluasi.simulasi(300, 42, "base")


def _lintasan(p: float, laporan_dari: int | None = None, n: int = 13) -> dict:
    """Lintasan buatan: peluang tetap, faktor L 1, laporan mulai langkah tertentu."""
    lap = np.zeros(n, bool)
    if laporan_dari is not None:
        lap[laporan_dari:] = True
    return {"peluang": np.full(n, p), "faktor_L": np.ones(n), "laporan": lap}


# ---------------------------------------------------------------- definisi kebijakan

def test_kebijakan_ambang_tetap_dan_cost_loss_batas(params_base):
    """p = 0,6 tetap: ambang 0,5 bertindak di langkah 0; cost-loss di batas bertindak di batas
    kecuali tindakan berambang statis > 0,6 (T9)."""
    lin = _lintasan(0.6)
    a05 = kebijakan.ambang_tetap_05(lin, True, params_base)
    assert all(v == 0 for v in a05.values())
    cl = kebijakan.cost_loss_batas(lin, True, params_base)
    ep = params_base.episode
    assert cl["T9"] is None
    assert cl["T1"] == ep.langkah_dari_jam(params_base.tindakan["T1"].param.waktu_siap_jam)


def test_kebijakan_jam_tetap_24(params_base):
    """Jam tetap: T1 (batas T-36) diputuskan di batasnya; T2 (batas T-6) diputuskan di T-24."""
    r = kebijakan.jam_tetap_24(_lintasan(0.9), True, params_base)
    ep = params_base.episode
    assert r["T1"] == ep.langkah_dari_jam(36)
    assert r["T2"] == ep.langkah_dari_jam(24)


def test_kebijakan_reaktif_dan_sempurna(params_base):
    """Reaktif menunggu laporan (langkah 10); tindakan berbatas lebih awal tidak sempat dijalankan."""
    r = kebijakan.reaktif(_lintasan(0.1, laporan_dari=10), True, params_base)
    assert r["T2"] == 10 and r["T1"] is None
    assert all(v == 0 for v in kebijakan.informasi_sempurna(_lintasan(0.1), True, params_base).values())
    assert all(v is None for v in kebijakan.informasi_sempurna(_lintasan(0.9), False, params_base).values())


def test_kebijakan_sigap_mengikuti_kurva(params_base):
    """SIGAP: p = 1 bertindak di langkah pertama; p = 0 tidak pernah bertindak."""
    assert all(v == 0 for v in kebijakan.sigap(_lintasan(1.0), True, params_base).values())
    assert all(v is None for v in kebijakan.sigap(_lintasan(0.0), True, params_base).values())


# ---------------------------------------------------------------- biaya dan simulasi

def test_biaya_episode_fr_e2(params_base):
    """Tanpa tindakan dan terganggu: biaya = jumlah L; tanpa gangguan: 0; semua bertindak di batas
    tanpa gangguan: jumlah (C + P)."""
    kosong = {t: None for t in params_base.tindakan}
    assert evaluasi.biaya_episode(kosong, True, 1.0, params_base) == pytest.approx(
        sum(t.param.L for t in params_base.daftar_tindakan()))
    assert evaluasi.biaya_episode(kosong, False, 1.0, params_base) == 0
    ep = params_base.episode
    di_batas = {t.id: ep.langkah_dari_jam(t.param.waktu_siap_jam) for t in params_base.daftar_tindakan()}
    assert evaluasi.biaya_episode(di_batas, False, 1.0, params_base) == pytest.approx(
        sum(t.param.C + t.param.P for t in params_base.daftar_tindakan()))


def test_simulasi_dapat_diulang():
    """Seed sama -> tabel biaya identik (NFR-4, FR-E3)."""
    a = evaluasi.simulasi(15, 9, "base")
    b = evaluasi.simulasi(15, 9, "base")
    pd.testing.assert_frame_equal(a.biaya, b.biaya)
    assert a.ringkasan == b.ringkasan


def test_informasi_sempurna_batas_bawah(hasil_base):
    """Informasi sempurna tidak pernah lebih mahal dari kebijakan lain pada episode mana pun."""
    tab = hasil_base.biaya.pivot(index="episode_ke", columns="kebijakan", values="biaya")
    for k in kebijakan.KEBIJAKAN:
        assert (tab["informasi_sempurna"] <= tab[k] + 1e-9).all(), k


def test_sigap_tidak_lebih_mahal_dari_pembanding(hasil_base):
    """Rerata biaya SIGAP <= pembanding (toleransi 1% terhadap cost-loss di batas; batas atas menurut
    asumsi model sendiri)."""
    r = hasil_base.ringkasan["rerata_biaya"]
    assert r["sigap"] <= r["cost_loss_batas"] * 1.01
    for k in ("jam_tetap_24", "ambang_tetap_05", "reaktif"):
        assert r["sigap"] < r[k], k
    assert set(r) == set(kebijakan.KEBIJAKAN)
    sp = hasil_base.ringkasan["selisih_berpasangan_sigap"]
    assert sp["reaktif"]["ki95"][1] < 0  # jelas lebih murah dari reaktif
    assert all(v["galat_baku"] >= 0 for v in sp.values())


def test_sensitivitas_diskon():
    """Tanpa biaya menunggu, SIGAP setara cost-loss di batas; diskon lebih besar memberi keunggulan lebih."""
    eps = episode_sintetis(60, 42, "base")
    tab = evaluasi.sensitivitas_diskon([0.0, 0.05], eps, "base")
    assert list(tab["diskon"]) == [0.0, 0.05]
    nol, lima = tab.iloc[0], tab.iloc[1]
    assert nol["sigap"] == pytest.approx(nol["cost_loss_batas"], rel=0.01)
    assert lima["sigap"] < lima["cost_loss_batas"]


# ---------------------------------------------------------------- metrik deteksi

def test_metrik_kontingensi_dihitung_tangan():
    """POD = hit/(hit+miss), FAR = fa/(hit+fa), CSI = hit/(hit+miss+fa); lead time rerata hit."""
    jam = [-72.0, -48.0, -24.0, 0.0]
    m = evaluasi.metrik_kontingensi([0, 2, None, 1, None], np.array([True, True, True, False, False]), jam)
    assert (m["hit"], m["miss"], m["false_alarm"]) == (2, 1, 1)
    assert m["POD"] == pytest.approx(2 / 3)
    assert m["FAR"] == pytest.approx(1 / 3)
    assert m["CSI"] == pytest.approx(2 / 4)
    assert m["lead_time_jam"] == pytest.approx((72 + 24) / 2)


def test_loeo_dan_pembanding():
    """Peluang LOEO berbentuk (episode, langkah) dalam [0, 1]; metrik untuk SIGAP dan dua pembanding."""
    eps = episode_sintetis(25, 5, "base")
    p = evaluasi.peluang_loeo(eps)
    assert p.shape == (25, muat_params().episode.jumlah_langkah)
    assert np.all((p >= 0) & (p <= 1))
    m = evaluasi.evaluasi_deteksi(eps)
    assert set(m) == {"sigap_loeo", "aturan_hujan_lokal", "hmhews"}
    skor = evaluasi.skor_pembanding(eps)
    assert skor["hmhews"].max() <= 4 and skor["hmhews"].min() >= 0


# ---------------------------------------------------------------- episode nyata dan database

def test_episode_nyata_24_januari_2025():
    """Episode nyata: hujan NASA POWER nyata, prakiraan sintetis berlabel, Glapan nyata ikut, hasil belum terkonfirmasi."""
    ep = bangun_episode_nyata()
    assert ep.jenis == "nyata" and ep.status_hasil == "belum terkonfirmasi"
    lab = ep.label_seri
    assert lab["hujan"] == "nyata" and lab["prakiraan"] == "dummy" and lab["muka_air"] == "campuran"
    assert ep.kebenaran["terganggu"] is None
    assert (ep.muka_air["nilai"] == 1970).any()
    papan_p = Estimator(model_bawaan("base")).lintasan(ep)["peluang"]
    assert np.all((papan_p >= 0) & (papan_p <= 1))


def test_episode_cadangan_tetap_dan_terganggu():
    """Skenario cadangan presentasi selalu sama dan memperlihatkan gangguan."""
    a, b = episode_cadangan(), episode_cadangan()
    assert a.id == muat_params().demo["id_episode_cadangan"]
    pd.testing.assert_frame_equal(a.hujan, b.hujan)
    assert a.kebenaran["terganggu"] is True


def test_episode_simpan_dan_muat_db(engine_sqlite):
    """Episode sintetis yang disimpan lalu dimuat menghasilkan lintasan lapis I yang sama."""
    from db.koneksi import pabrik_sesi
    ep = episode_sintetis(1, 3, "base")[0]
    sesi = pabrik_sesi(engine_sqlite)()
    simpan_ke_db(sesi, ep)
    sesi.commit()
    kembali = muat_dari_db(sesi, ep.id)
    sesi.close()
    est = Estimator(model_bawaan("base"))
    np.testing.assert_allclose(est.lintasan(kembali)["peluang"], est.lintasan(ep)["peluang"], atol=1e-9)
    assert kembali.kebenaran["terganggu"] == ep.kebenaran["terganggu"]
    assert len(kembali.laporan) == len(ep.laporan)


def test_simpan_hasil_simulasi_db(engine_sqlite):
    """Hasil simulasi tersimpan per episode per kebijakan beserta ringkasan run."""
    from sqlalchemy import func, select

    from db.koneksi import pabrik_sesi
    from db.model import HasilSimulasi, SimulasiRun
    from simulation.jalankan import simpan_hasil_db
    h = evaluasi.simulasi(5, 1, "base")
    sesi = pabrik_sesi(engine_sqlite)()
    simpan_hasil_db(sesi, "uji-1", h)
    sesi.commit()
    assert sesi.scalar(select(func.count()).select_from(HasilSimulasi)) == 5 * 6
    assert sesi.get(SimulasiRun, "uji-1").ringkasan["pembanding_terbaik"]
    sesi.close()
