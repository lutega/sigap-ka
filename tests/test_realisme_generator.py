"""
Tujuan      : Menguji pemeriksaan realisme generator (simulation/realisme_generator.py): ringkasan
              episode sintetis, tabel kuantil, dan frekuensi gangguan per kelas hujan.
Lapis       : Simulasi/evaluasi.
Sumber      : Episode sintetis berseed dan tabel pindai buatan tes.
Masukan     : -
Keluaran    : -
Keterbatasan: -
"""

import pandas as pd
import pytest

from simulation import realisme_generator as rg


def _pindai():
    return pd.DataFrame({
        "tanggal": [f"2025-01-{i:02d}" for i in range(1, 9)],
        "label": ["lain", "lain", "lain", "kejadian", "sekitar", "lain", "kejadian", "lain"],
        "hujan_aktual_hulu_72j": [0.0, 10.0, 30.0, 70.0, 90.0, 50.0, 110.0, 5.0],
        "hujan_aktual_lokal_72j": [0.0, 12.0, 25.0, 60.0, 80.0, 40.0, 100.0, 4.0],
        "hujan_hulu_3h_tersedia": [0.0, 8.0, 20.0, 50.0, 60.0, 30.0, 90.0, 2.0],
        "hujan_lokal_3h_tersedia": [0.0, 9.0, 15.0, 45.0, 55.0, 25.0, 80.0, 1.0],
        "glapan_relatif_T0": [-200.0] * 8,
    })


def test_ringkas_sintetis_berseed_dan_berkolom_lengkap():
    """Ringkasan episode sintetis berulang untuk seed sama dan memuat hujan 72 jam serta kebenaran."""
    a = rg.ringkas_sintetis(n=6, seed=7)
    b = rg.ringkas_sintetis(n=6, seed=7)
    pd.testing.assert_frame_equal(a, b)
    assert set(rg.KOLOM_BANDING) | {"terganggu", "mekanisme"} <= set(a.columns)
    assert (a["hulu_72j"] > 0).all()


def test_tabel_kuantil_dan_kelas_hujan():
    """Kuantil per kelompok dan frekuensi per kelas (hari 'sekitar' dibuang dari data nyata)."""
    sintetis = pd.DataFrame({"hulu_72j": [30.0, 70.0, 120.0], "lokal_72j": [20.0, 60.0, 100.0],
                             "hulu_3h_tersedia": [30.0, 70.0, 120.0], "lokal_3h_tersedia": [20.0, 60.0, 100.0],
                             "glapan_relatif_T0": [-100.0, 0.0, 50.0], "terganggu": [False, True, True],
                             "mekanisme": [None, "genangan", "gerusan"]})
    k = rg.tabel_kuantil(sintetis, _pindai())
    baris = k[(k["besaran"] == "hulu_72j") & (k["kelompok"] == "sintetis_latih")].iloc[0]
    assert baris["q50"] == pytest.approx(70.0)
    assert baris["persentil_nyata_median_sintetis"] == pytest.approx(5 / 8 * 100, abs=0.1)
    assert set(k["kelompok"]) == {"sintetis_latih", "nyata_semua_hari", "nyata_hari_kejadian"}
    kelas = rg.tabel_kelas_hujan(sintetis, _pindai()).set_index("hujan_hulu_72j")
    assert kelas.loc["60-80 mm", "porsi_terganggu_sintetis"] == 1.0
    assert kelas.loc["60-80 mm", "porsi_hari_kejadian_nyata"] == 1.0
    assert kelas["n_hari_nyata"].sum() == 7          # satu hari 'sekitar' dibuang
    assert kelas.loc["100- mm", "hari_kejadian"] == 1
