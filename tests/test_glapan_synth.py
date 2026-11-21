"""
Tujuan      : Menguji estimasi TMA Glapan sintetis (inputs/glapan_synth.py): respons terhadap hujan,
              peluruhan surut, lonjakan banjir di atas ambang, skema dan label sintetis, anchoring
              ke titik nyata (termasuk batas faktor), serta fitur glapan_relatif dan tren_glapan_6j.
Lapis       : QA, lapis S dan penyiapan fitur.
Sumber      : Seri hujan buatan tes dan berkas anchor buatan (angka uji, bukan data nyata).
Masukan     : -
Keluaran    : -
Keterbatasan: Menguji perilaku model konseptual, bukan ketepatan hidrologis.
"""

import numpy as np
import pandas as pd
import pytest

from config import muat_params
from sigap_ka.features import glapan as fitur_glapan
from sigap_ka.inputs import glapan_synth
from sigap_ka.inputs.base import validasi


def _zona_harian(hulu, lokal=None, mulai="2025-01-01"):
    """Seri hujan harian buatan untuk zona hulu dan lokal."""
    lokal = lokal if lokal is not None else [0.0] * len(hulu)
    tgl = pd.date_range(mulai, periods=len(hulu), freq="D")
    bagian = [pd.DataFrame({"tanggal": tgl, "zona": z, "nilai": v, "sumber": "uji", "status_data": "nyata"})
              for z, v in (("hulu_tuntang", hulu), ("lokal_gubug_karangjati", lokal))]
    return pd.concat(bagian, ignore_index=True)


def _anchor(tmp_path, tanggal, nilai):
    """Berkas anchor berformat data/processed/muka_air_glapan.csv."""
    p = tmp_path / "anchor.csv"
    pd.DataFrame({"waktu": [f"{tanggal} 23:00:00"], "lokasi": ["glapan"], "nilai": [nilai], "satuan": ["cm"],
                  "sumber": ["glapan_bnpb"], "is_simulated": [False]}).to_csv(p, index=False)
    return p


@pytest.fixture
def p():
    return muat_params().muka_air["glapan_api"]


def test_tma_naik_saat_hujan_lebat_lalu_surut(p):
    """Hujan hulu lebat menaikkan TMA (lonjakan cepat aktif), lalu TMA meluruh saat kering."""
    jam = 24 * 10
    hulu = np.zeros(jam)
    hulu[48:72] = 80.0 / 24  # 80 mm pada hari ketiga (di atas ambang lonjakan)
    sim = glapan_synth.simulasi(hulu, np.zeros(jam), p)
    tma = sim["tma"]
    puncak = int(np.argmax(tma))
    assert 48 <= puncak <= 96
    assert tma[puncak] > tma[40] + 20
    assert tma[-1] < tma[puncak]
    assert sim["s_cepat"][:48].max() == 0 and sim["s_cepat"].max() > 0


def test_hujan_di_bawah_ambang_tanpa_lonjakan(p):
    """Hujan kecil (di bawah ambang harian) hanya mengisi aliran dasar, tanpa komponen lonjakan."""
    jam = 24 * 5
    sim = glapan_synth.simulasi(np.full(jam, 10.0 / 24), np.zeros(jam), p)
    assert sim["s_cepat"].max() == 0
    assert sim["tma"].min() >= p["elevasi_dasar"]


def test_skema_dan_label_sintetis(tmp_path):
    """Keluaran per jam berskema standar, sumber glapan_api_synth, status sintetis."""
    hasil, lap = glapan_synth.jalankan(_zona_harian([0, 0, 60, 10, 0, 0]), anchor=False)
    validasi(hasil, ["glapan"])
    assert len(hasil) == 6 * 24
    assert set(hasil["sumber"]) == {"glapan_api_synth"} and set(hasil["status_data"]) == {"sintetis"}
    assert (hasil["tanggal"].diff().dropna() == pd.Timedelta(hours=1)).all()
    assert lap["faktor_anchor"] == 1.0


def test_anchoring_mencocokkan_maksimum_harian_dengan_titik_nyata(tmp_path, p):
    """Setelah anchoring, maksimum harian model pada tanggal titik nyata sama dengan nilai nyata."""
    zona = _zona_harian([0, 10, 70, 30, 5, 0, 0])
    tanpa, _ = glapan_synth.jalankan(zona, anchor=False)
    model = tanpa[tanpa["tanggal"].dt.date.astype(str) == "2025-01-04"]["nilai"].max()
    target = p["elevasi_dasar"] + 1.5 * (model - p["elevasi_dasar"])  # dalam batas faktor
    hasil, lap = glapan_synth.jalankan(zona, anchor=True, path_anchor=_anchor(tmp_path, "2025-01-04", target))
    hari = hasil[hasil["tanggal"].dt.date.astype(str) == "2025-01-04"]["nilai"].max()
    assert hari == pytest.approx(target, rel=1e-9)
    assert lap["faktor_anchor"] == pytest.approx(1.5)
    assert lap["rincian_anchor"][0]["model_setelah"] == pytest.approx(target)


def test_anchoring_dibatasi_dan_titik_di_luar_rentang(tmp_path, p):
    """Faktor dibatasi [min, maks]; titik di luar rentang seri dilewati (faktor 1)."""
    zona = _zona_harian([0, 10, 70, 30, 5, 0, 0])
    _, lap = glapan_synth.jalankan(zona, anchor=True, path_anchor=_anchor(tmp_path, "2025-01-04", 99999))
    assert lap["faktor_anchor"] == p["faktor_anchor_maks"]
    _, lap2 = glapan_synth.jalankan(zona, anchor=True, path_anchor=_anchor(tmp_path, "2030-01-01", 1970))
    assert lap2["faktor_anchor"] == 1.0 and lap2["rincian_anchor"][0]["dipakai"] is False


def test_tanpa_hujan_hulu_keluaran_kosong():
    """Tanpa hujan hulu Tuntang, tidak ada seri yang dikarang."""
    zona = _zona_harian([1.0, 2.0])
    hasil, lap = glapan_synth.jalankan(zona[zona["zona"] != "hulu_tuntang"], anchor=False)
    assert hasil.empty and "hulu" in lap["pesan"]


def test_fitur_glapan_relatif_dan_tren_6j():
    """glapan_relatif = TMA - 1905; tren_glapan_6j = TMA_t - TMA_(t-6); jam hilang membuat tren NaN."""
    jam = pd.date_range("2025-01-01", periods=12, freq="h")
    tma = pd.DataFrame({"tanggal": jam, "zona": "glapan", "nilai": 1900.0 + np.arange(12) * 2,
                        "sumber": "glapan_api_synth", "status_data": "sintetis"})
    f = fitur_glapan.hitung_fitur(tma)
    assert f["glapan_relatif"].iloc[0] == pytest.approx(1900 - muat_params().muka_air["ambang_awas"])
    assert f["tren_glapan_6j"].iloc[:6].isna().all() and f["tren_glapan_6j"].iloc[6] == pytest.approx(12.0)
    berlubang = fitur_glapan.hitung_fitur(tma.drop(index=3))
    assert len(berlubang) == 12 and np.isnan(berlubang["tma"].iloc[3]) and np.isnan(berlubang["tren_glapan_6j"].iloc[9])
    assert set(f["status_data"]) == {"sintetis"}


def test_jalankan_fitur_menyimpan_interim_dan_processed(tmp_path):
    """Pipeline fitur menyimpan seri TMA sintetis (interim) dan fitur (processed)."""
    interim, proses = tmp_path / "interim" / "glapan_tma_synth.csv", tmp_path / "processed" / "glapan_features.csv"
    f, lap = fitur_glapan.jalankan(anchor=False, zona_harian=_zona_harian([0, 50, 0, 0]),
                                   path_interim=interim, path_fitur=proses)
    assert interim.exists() and proses.exists() and len(f) == 4 * 24
    assert set(pd.read_csv(interim)["status_data"]) == {"sintetis"}
