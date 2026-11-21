"""
Tujuan      : Menguji lapis G: ambang cost-loss, kurva pemicu pemrograman dinamis (nilai di batas
              waktu, bentuk kurva, pola T1/T9, efek P), pembanding brute force, dan status tindakan.
Lapis       : QA, lapis G.
Sumber      : params.json (nilai dummy).
Masukan     : -
Keluaran    : -
Keterbatasan: Pola kurva yang diuji adalah sifat parameter dummy (spesifikasi 10.4).
"""

import numpy as np
import pytest
from scipy import integrate, stats

from config import ID_TINDAKAN, muat_params
from gating import cost_loss, status
from gating.kurva_pemicu import hitung_kurva, kurva_untuk_tindakan, matriks_transisi, semua_kurva

TOL = 1e-6


# ---------------------------------------------------------------- cost-loss

def test_ambang_statis_rumus():
    """(C + P) / (L + P) dan titik impas biaya harapan."""
    C, L, P = 40.0, 300.0, 30.0
    p = cost_loss.ambang_statis(C, L, P)
    assert p == pytest.approx(70 / 330)
    assert cost_loss.biaya_harapan_bertindak(p, C, P) == pytest.approx(cost_loss.biaya_harapan_tidak(p, L))


def test_biaya_aktual_fr_e2():
    """Biaya aktual: C (+P bila alarm palsu) bila bertindak; L bila tidak bertindak dan terganggu."""
    assert cost_loss.biaya_aktual(True, True, 10, 100, 5) == 10
    assert cost_loss.biaya_aktual(True, False, 10, 100, 5) == 15
    assert cost_loss.biaya_aktual(False, True, 10, 100, 5) == 100
    assert cost_loss.biaya_aktual(False, False, 10, 100, 5) == 0


def test_biaya_lebih_awal_lebih_murah():
    """Diskon biaya: di batas waktu = C, lebih awal lebih murah."""
    assert cost_loss.biaya_tindakan_pada_langkah(100, 0, 0.02) == 100
    assert cost_loss.biaya_tindakan_pada_langkah(100, 3, 0.02) == pytest.approx(100 * 0.98 ** 3)


# ---------------------------------------------------------------- kurva pemicu

def test_matriks_transisi_martingale_dan_stokastik():
    """Baris berjumlah 1, ujung menyerap, rerata baris = p (martingale) dalam toleransi grid."""
    g, T = matriks_transisi(201, 12.0)
    np.testing.assert_allclose(T.sum(axis=1), 1.0)
    assert T[0, 0] == 1.0 and T[-1, -1] == 1.0
    assert np.max(np.abs(T @ g - g)) < 0.005


def test_kurva_di_batas_waktu_sama_ambang_statis(params_semua_preset):
    """FR-G2: di batas waktu siap, ambang = (C + P) / (L + P) untuk semua tindakan dan preset."""
    for t in params_semua_preset.daftar_tindakan():
        k = kurva_untuk_tindakan(t, params_semua_preset)
        assert k.jam_sebelum_t0[-1] == t.param.waktu_siap_jam
        assert k.ambang[-1] == pytest.approx(t.param.ambang_statis, abs=TOL)


def test_kurva_tinggi_jauh_dan_turun_ke_batas(params_semua_preset):
    """Spesifikasi 10.2: kurva >= ambang statis dan tidak naik menuju batas waktu."""
    for t in params_semua_preset.daftar_tindakan():
        a = np.array(kurva_untuk_tindakan(t, params_semua_preset).ambang)
        assert np.all(a >= t.param.ambang_statis - TOL), t.id
        assert np.all(np.diff(a) <= TOL), t.id
        if len(a) > 1:
            assert a[0] > t.param.ambang_statis  # menunggu bernilai saat kejadian masih jauh


def test_pola_t1_paling_awal_dan_t9_mahal(params_base):
    """Spesifikasi 10.4: kurva T1 turun paling awal; T9 butuh peluang di atas 70% (base, dummy)."""
    kurva = semua_kurva(params_base)

    def jam_pertama_di_bawah(k, batas=0.5):
        for j, a in zip(k.jam_sebelum_t0, k.ambang):
            if a <= batas:
                return j
        return -1
    jam = {tid: jam_pertama_di_bawah(k) for tid, k in kurva.items()}
    assert jam["T1"] == max(jam.values())
    assert min(kurva["T9"].ambang) > 0.7


def test_denda_alarm_palsu_menaikkan_ambang(params_base):
    """FR-P1: P lebih besar -> ambang lebih tinggi di sepanjang kurva."""
    t = params_base.tindakan["T3"]
    kecil = kurva_untuk_tindakan(t, params_base, P=10)
    besar = kurva_untuk_tindakan(t, params_base, P=200)
    assert all(b >= a - TOL for a, b in zip(kecil.ambang, besar.ambang))
    assert besar.ambang[-1] > kecil.ambang[-1]


def test_slider_tidak_mengubah_params(params_base):
    """FR-G4: parameter pengganti hanya untuk hitung ulang; params.json tidak berubah."""
    t = params_base.tindakan["T2"]
    kurva_untuk_tindakan(t, params_base, C=1, L=999, P=0)
    assert params_base.tindakan["T2"].param.C == muat_params("base").tindakan["T2"].param.C


def test_dp_sama_dengan_integral_kontinu_satu_langkah():
    """Satu langkah sebelum batas: ambang DP sama dengan solusi integral Beta kontinu (brute force)."""
    C, L, P, k, d = 40.0, 300.0, 30.0, 12.0, 0.02
    ambang_dp = hitung_kurva(C, L, P, 1, k, d, 801)[0]

    def selisih(p):
        nilai_tunggu = integrate.quad(
            lambda q: min(C + (1 - q) * P, q * L) * stats.beta.pdf(q, k * p, k * (1 - p)),
            0, 1, limit=200)[0]
        return C * (1 - d) + (1 - p) * P - nilai_tunggu
    grid = np.linspace(0.01, 0.99, 197)
    s = np.array([selisih(p) for p in grid])
    i = np.nonzero(s <= 0)[0][0]
    ambang_bf = grid[i - 1] + (grid[i] - grid[i - 1]) * s[i - 1] / (s[i - 1] - s[i])
    assert ambang_dp == pytest.approx(ambang_bf, abs=0.01)


def test_dp_stabil_terhadap_resolusi_grid():
    """Kurva tiga langkah hampir sama pada grid 201 dan 801 titik."""
    a = hitung_kurva(80, 250, 40, 3, 12.0, 0.02, 201)
    b = hitung_kurva(80, 250, 40, 3, 12.0, 0.02, 801)
    np.testing.assert_allclose(a, b, atol=0.01)


def test_tanpa_diskon_menunggu_tak_pernah_rugi():
    """Tanpa diskon biaya awal, nilai informasi membuat bertindak sebelum batas hanya pada p sangat tinggi."""
    a = hitung_kurva(40, 300, 30, 4, 12.0, 0.0, 201)
    assert np.all(a[:-1] >= 0.95)


# ---------------------------------------------------------------- status

def test_status_putuskan_tunggu_terlambat_disetujui(params_base):
    """Aturan 10.3 untuk tindakan T3 (batas T-12)."""
    t = params_base.tindakan["T3"]
    di_batas = t.param.waktu_siap_jam
    assert status.tentukan_status(t, 0.9, di_batas, params_base).status == status.PUTUSKAN
    assert status.tentukan_status(t, 0.1, di_batas, params_base).status == status.TUNGGU
    assert status.tentukan_status(t, 0.99, di_batas - 6, params_base).status == status.TERLAMBAT
    assert status.tentukan_status(t, 0.0, 48, params_base, disetujui=True).status == status.DISETUJUI


def test_status_memakai_kurva_bukan_ambang_statis(params_base):
    """Jauh sebelum batas waktu, p sedikit di atas ambang statis masih Tunggu (nilai menunggu)."""
    t = params_base.tindakan["T3"]
    s = status.tentukan_status(t, t.param.ambang_statis + 0.05, 48, params_base)
    assert s.status == status.TUNGGU
    assert s.ambang == pytest.approx(kurva_untuk_tindakan(t, params_base).ambang_pada(48), abs=TOL)
    assert s.sisa_jam == 48 - t.param.waktu_siap_jam


def test_faktor_L_menurunkan_ambang(params_base):
    """L efektif lebih besar (skenario tutup panjang) menurunkan ambang."""
    t = params_base.tindakan["T4"]
    a1 = status.ambang_pada_jam(t, 24, params_base, faktor_L=1.0)
    a2 = status.ambang_pada_jam(t, 24, params_base, faktor_L=1.8)
    assert a2 < a1


def test_tidak_ada_status_jalur_aman():
    """Sistem tidak pernah menyatakan jalur aman (FR-A5)."""
    for s in status.SEMUA_STATUS:
        assert "aman" not in s.lower()


def test_semua_tindakan_punya_kurva(params_base):
    """T1-T9 masing-masing punya kurva tak kosong."""
    kurva = semua_kurva(params_base)
    assert list(kurva) == list(ID_TINDAKAN)
    assert all(len(k.ambang) >= 1 for k in kurva.values())
