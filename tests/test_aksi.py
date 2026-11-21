"""
Tujuan      : Menguji lapis A: penjaga klaim jalur aman, log keputusan operator, papan tindakan
              (9 baris, status, alasan, peringatan maladaptasi), dan ringkasan biaya T-0.
Lapis       : QA, lapis A.
Sumber      : Episode buatan tes, generator dummy, database SQLite di memori.
Masukan     : -
Keluaran    : -
Keterbatasan: Biaya yang diuji memakai parameter dummy.
"""

from datetime import timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from action import log_keputusan, penjaga_klaim, ringkasan
from action.papan_tindakan import susun_papan
from config import ID_TINDAKAN
from gating.status import DISETUJUI, PUTUSKAN, TERLAMBAT, TUNGGU
from inference.estimasi import Estimator, model_bawaan
from tests.test_inferensi import T0, buat_episode


@pytest.fixture(scope="module")
def estimator():
    """Estimator dengan model bawaan base."""
    return Estimator(model_bawaan("base"))


class _EstimatorTetap:
    """Estimator tiruan: peluang tetap di semua jam (untuk ringkasan yang dihitung tangan)."""

    def __init__(self, peluang: float, langkah: int = 13):
        self.peluang, self.langkah = peluang, langkah

    def estimasi_episode(self, episode):
        return [SimpleNamespace(peluang=self.peluang, lama_tutup={"faktor_L": 1.0})
                for _ in range(self.langkah)]


# ---------------------------------------------------------------- penjaga klaim

@pytest.mark.parametrize("teks", ["Jalur aman dilalui", "STATUS: AMAN", "track is safe", "tidak aman"])
def test_penjaga_menolak_klaim_aman(teks):
    """Kata utuh 'aman'/'safe' dalam keluaran ditolak (FR-A5)."""
    with pytest.raises(penjaga_klaim.KlaimAmanTerlarang):
        penjaga_klaim.pastikan_tanpa_klaim_aman({"pesan": [teks]})


@pytest.mark.parametrize("teks", ["keamanan data", "pengamanan jalur", "ambang Awas", "Putuskan sekarang"])
def test_penjaga_tidak_salah_tangkap(teks):
    """Kata turunan seperti 'keamanan' tidak ditolak."""
    assert penjaga_klaim.pastikan_tanpa_klaim_aman(teks) == teks


# ---------------------------------------------------------------- log keputusan

def _catat(sesi, tindakan, jam, keputusan, status="Putuskan sekarang", **kw):
    return log_keputusan.catat(sesi, "EP", tindakan, jam, keputusan, "operator1", status, **kw)


def test_log_setujui_batalkan_dan_validasi(sesi_sqlite):
    """Setujui -> tidak bisa disetujui lagi; batalkan -> bisa; batalkan tanpa setujui -> galat."""
    r = _catat(sesi_sqlite, "T1", 36, "setujui", alasan="uji", peluang=0.4, nilai_kurva=0.1)
    assert r["username"] == "operator1" and r["status_sigap"] == "Putuskan sekarang"
    assert r["waktu_dicatat"] is not None and r["mode"] == "normal"
    with pytest.raises(log_keputusan.KeputusanTidakValid):
        _catat(sesi_sqlite, "T1", 30, "setujui")
    _catat(sesi_sqlite, "T1", 30, "batalkan")
    _catat(sesi_sqlite, "T1", 24, "setujui")
    with pytest.raises(log_keputusan.KeputusanTidakValid):
        _catat(sesi_sqlite, "T2", 24, "batalkan")
    with pytest.raises(log_keputusan.KeputusanTidakValid):
        _catat(sesi_sqlite, "T2", 0, "setujui", status=TERLAMBAT)
    with pytest.raises(log_keputusan.KeputusanTidakValid):
        _catat(sesi_sqlite, "T99", 24, "setujui")
    _catat(sesi_sqlite, "T2", 24, "tolak", alasan="menunggu laporan lapangan")
    # sah: setujui, batalkan, setujui, tolak (yang ditolak validasi tidak tercatat)
    assert [r["keputusan"] for r in log_keputusan.daftar(sesi_sqlite, "EP")] == \
        ["setujui", "batalkan", "setujui", "tolak"]


def test_tindakan_disetujui_tanpa_intip_keputusan_masa_depan():
    """Persetujuan pada T-12 tidak terlihat saat papan dilihat pada T-24."""
    log = [{"id": 1, "tindakan_id": "T3", "jam_sebelum_t0": 12, "keputusan": "setujui"},
           {"id": 2, "tindakan_id": "T1", "jam_sebelum_t0": 36, "keputusan": "setujui"},
           {"id": 3, "tindakan_id": "T1", "jam_sebelum_t0": 30, "keputusan": "batalkan"}]
    assert log_keputusan.tindakan_disetujui(log, 24) == {}
    assert log_keputusan.tindakan_disetujui(log, 36) == {"T1": 36}
    assert log_keputusan.tindakan_disetujui(log, 6) == {"T3": 12}


def test_hapus_log_demo_hanya_sesi_itu(sesi_sqlite):
    """Reset demo menghapus log mode=demo sesi itu saja; log normal dan sesi lain tetap."""
    _catat(sesi_sqlite, "T1", 36, "setujui")
    _catat(sesi_sqlite, "T1", 36, "setujui", mode="demo", sesi_demo_id="A")
    _catat(sesi_sqlite, "T1", 36, "setujui", mode="demo", sesi_demo_id="B")
    assert log_keputusan.hapus_log_demo(sesi_sqlite, "A") == 1
    sisa = log_keputusan.daftar(sesi_sqlite, "EP")
    assert sorted((r["mode"], r["sesi_demo_id"]) for r in sisa) == [("demo", "B"), ("normal", None)]


# ---------------------------------------------------------------- papan tindakan

def test_papan_sembilan_tindakan_dan_label(estimator):
    """Papan selalu 9 baris berurutan T1-T9; T6-T8 berlabel belum terkonfirmasi; parameter dummy."""
    papan = susun_papan(buat_episode(80, 90, glapan=1950), 24, estimator)
    assert [b["tindakan"] for b in papan["tindakan"]] == list(ID_TINDAKAN)
    assert [b["terkonfirmasi"] for b in papan["tindakan"]][5:8] == [False, False, False]
    assert all(b["label_parameter"] == "dummy" for b in papan["tindakan"])
    assert all(b["status"] in (PUTUSKAN, TUNGGU, TERLAMBAT, DISETUJUI) for b in papan["tindakan"])
    assert any("KAI" in c for c in papan["catatan"])
    assert 0 <= papan["inferensi"]["peluang"] <= 1


def test_papan_status_terlambat_dan_disetujui(estimator):
    """Pada T-0 semua batas waktu lewat (Terlambat) kecuali yang sudah disetujui."""
    log = [{"id": 1, "tindakan_id": "T1", "jam_sebelum_t0": 48, "keputusan": "setujui"}]
    papan = susun_papan(buat_episode(80, 90), 0, estimator, log=log)
    status = {b["tindakan"]: b["status"] for b in papan["tindakan"]}
    assert status["T1"] == DISETUJUI
    assert all(status[t] == TERLAMBAT for t in ID_TINDAKAN if t != "T1")
    t1 = next(b for b in papan["tindakan"] if b["tindakan"] == "T1")
    assert "T-48" in t1["alasan"]


def test_papan_alasan_memuat_selisih_dan_bukti(estimator):
    """Alasan singkat menyebut peluang, kurva, selisih, dan bukti utama."""
    papan = susun_papan(buat_episode(120, 150, glapan=2050), 12, estimator)
    t3 = next(b for b in papan["tindakan"] if b["tindakan"] == "T3")
    assert "kurva pemicu" in t3["alasan"] and "Bukti utama" in t3["alasan"]
    assert t3["selisih"] == pytest.approx(t3["peluang"] - t3["ambang"])


def test_peringatan_maladaptasi_gundih_dan_jalan_putus(estimator):
    """T3 diberi peringatan bila Gundih hujan lebat; T4 bila jalan Semarang-Purwodadi putus."""
    ep = buat_episode(100, 120)
    gundih = ep.hujan[ep.hujan["lokasi"] == "lokal"].assign(lokasi="gundih")
    gundih["nilai"] = np.where(gundih["waktu"] >= T0 - timedelta(hours=40), 4.0, 0.0)
    ep.hujan = pd.concat([ep.hujan, gundih], ignore_index=True)
    ep.laporan = pd.DataFrame({"waktu": [T0 - timedelta(hours=20)], "jenis": ["jalan_putus"],
                               "isi": ["uji"], "sumber": ["uji"], "is_simulated": [True]})
    papan = susun_papan(ep, 12, estimator)
    b = {x["tindakan"]: x for x in papan["tindakan"]}
    assert any("Gundih" in p for p in b["T3"]["peringatan"])
    assert any("Semarang-Purwodadi" in p for p in b["T4"]["peringatan"])
    papan_awal = susun_papan(buat_episode(100, 120), 12, estimator)
    assert all(not x["peringatan"] for x in papan_awal["tindakan"])


def test_papan_episode_sintetis_tanpa_klaim_aman(estimator):
    """Papan untuk beberapa episode sintetis di semua jam lolos penjaga klaim."""
    from sensing import dummy_generator
    for ep in dummy_generator.ambil(3, 77, "base"):
        for jam in (72, 36, 12, 0):
            papan = susun_papan(ep, jam, estimator)
            penjaga_klaim.pastikan_tanpa_klaim_aman(papan)


# ---------------------------------------------------------------- ringkasan T-0

def test_ringkasan_dihitung_tangan_terganggu(params_base):
    """Operator menyetujui T1 di batas waktunya; SIGAP (peluang 0) tidak bertindak; gangguan terjadi."""
    ep = SimpleNamespace(id="X", t0=T0, kebenaran={"terganggu": True, "mekanisme": "genangan",
                                                    "skenario_lama_tutup": "sedang"})
    log = [{"id": 1, "tindakan_id": "T1", "jam_sebelum_t0": 36, "keputusan": "setujui"}]
    r = ringkasan.ringkasan_episode(ep, _EstimatorTetap(0.0), log, params_base)
    s = r["skenario"][0]
    total_L = sum(t.param.L for t in params_base.daftar_tindakan())
    t1 = params_base.tindakan["T1"].param
    assert s["total_sigap"] == pytest.approx(total_L)
    assert s["total_operator"] == pytest.approx(total_L - t1.L + t1.C)
    lab = {b["tindakan"]: b for b in s["tindakan"]}
    assert lab["T1"]["operator"]["label"] == "tepat"
    assert lab["T2"]["operator"]["label"] == "terlambat"


def test_ringkasan_sia_sia_dan_terlalu_awal(params_base):
    """Tanpa gangguan, tindakan operator sia-sia (C + P); SIGAP (peluang 1) bertindak paling awal."""
    ep = SimpleNamespace(id="X", t0=T0, kebenaran={"terganggu": False})
    log = [{"id": 1, "tindakan_id": "T2", "jam_sebelum_t0": 6, "keputusan": "setujui"}]
    r = ringkasan.ringkasan_episode(ep, _EstimatorTetap(0.0), log, params_base)
    t2 = params_base.tindakan["T2"].param
    s = r["skenario"][0]
    assert s["total_operator"] == pytest.approx(t2.C + t2.P)
    assert s["total_sigap"] == 0
    assert next(b for b in s["tindakan"] if b["tindakan"] == "T2")["operator"]["label"] == "sia-sia"
    # terlalu awal: operator bertindak sebelum saat SIGAP menyarankan
    assert ringkasan.klasifikasi(langkah=2, langkah_sigap=5, batas=6, terganggu=True) == "terlalu awal"
    assert ringkasan.klasifikasi(langkah=5, langkah_sigap=5, batas=6, terganggu=True) == "tepat"


def test_ringkasan_hasil_belum_terkonfirmasi_dua_kemungkinan(params_base):
    """Episode nyata tanpa hasil di katalog: ringkasan untuk terganggu dan tidak terganggu."""
    ep = SimpleNamespace(id="NYATA", t0=T0, kebenaran={"terganggu": None})
    r = ringkasan.ringkasan_episode(ep, _EstimatorTetap(0.3), [], params_base)
    assert r["status_hasil"] == "belum terkonfirmasi"
    assert [s["terganggu"] for s in r["skenario"]] == [True, False]


def test_ringkasan_episode_sintetis_dengan_estimator_nyata(estimator):
    """Ringkasan pada episode sintetis memakai kebenarannya; SIGAP mengikuti langkah_putuskan."""
    from sensing import dummy_generator
    ep = dummy_generator.ambil(1, 2024, "base")[0]
    r = ringkasan.ringkasan_episode(ep, estimator, [])
    assert r["status_hasil"] == "diketahui" and len(r["skenario"]) == 1
    assert len(r["peluang_per_jam"]) == 13
