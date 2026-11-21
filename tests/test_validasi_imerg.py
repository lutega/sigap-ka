"""
Tujuan      : Menguji validasi IMERG terhadap stasiun BMKG (features/validasi_imerg.py): total bulanan
              hanya untuk bulan lengkap, tabel perbandingan, dan metrik bias/korelasi/MAE/RMSE.
Lapis       : QA, validasi masukan lapis S.
Sumber      : Seri buatan tes (angka uji, bukan data nyata).
Masukan     : -
Keluaran    : -
Keterbatasan: -
"""

import numpy as np
import pandas as pd
import pytest

from sigap_ka.features import validasi_imerg as v


def _harian(mulai, hari, nilai=1.0, produk="gpm_imerg_late"):
    tgl = pd.date_range(mulai, periods=hari, freq="D")
    return pd.DataFrame({"tanggal": tgl, "zona": v.ZONA, "nilai": nilai, "sumber": produk, "status_data": "nyata"})


def test_imerg_bulanan_hanya_bulan_lengkap():
    """Januari lengkap (31 hari) dijumlah; Februari tidak lengkap -> NaN."""
    total = v.imerg_bulanan(_harian("2025-01-01", 40, 2.0))
    assert total.loc[pd.Timestamp("2025-01-01")] == pytest.approx(62.0)
    assert np.isnan(total.loc[pd.Timestamp("2025-02-01")])


def test_metrik_dihitung_tangan():
    """bias = (sum sat - sum stasiun)/sum stasiun; MAE dan RMSE dari galat per bulan."""
    t = pd.DataFrame({"rerata_stasiun": [100.0, 200.0, 300.0], "sat": [110.0, 190.0, 360.0]})
    m = v.metrik(t, "sat")
    assert m["n_bulan"] == 3
    assert m["bias_persen"] == pytest.approx((660 - 600) / 600 * 100, abs=0.05)
    assert m["mae_mm"] == pytest.approx((10 + 10 + 60) / 3, abs=0.05)
    assert m["rmse_mm"] == pytest.approx(np.sqrt((100 + 100 + 3600) / 3), abs=0.05)
    assert v.metrik(t.iloc[:1], "sat")["bias_persen"] is None


def test_tabel_perbandingan_dan_jalankan(tmp_path):
    """Tabel berisi kolom tiap stasiun, rerata, dan produk IMERG; berkas hasil tersimpan."""
    bmkg = pd.DataFrame({
        "tanggal": pd.to_datetime(["2025-01-01", "2025-01-01"]), "zona": v.ZONA, "nilai": [60.0, 64.0],
        "sumber": "bmkg", "status_data": "nyata", "stasiun": ["Stasiun A", "Stasiun B"], "resolusi": "bulanan",
    })
    t = v.tabel_perbandingan(bmkg, {"gpm_imerg_late": _harian("2025-01-01", 31, 2.0)})
    assert t.loc[0, "rerata_stasiun"] == pytest.approx(62.0) and t.loc[0, "gpm_imerg_late"] == pytest.approx(62.0)

    p_bmkg, p_imerg = tmp_path / "bmkg.csv", tmp_path / "imerg.csv"
    bmkg.to_csv(p_bmkg, index=False)
    d = _harian("2025-01-01", 31, 2.0)
    pd.DataFrame({"waktu": d["tanggal"] + pd.Timedelta(hours=7), "lokasi": "semarang_pembanding", "nilai": 2.0,
                  "satuan": "mm", "sumber": "gpm_imerg_late", "is_simulated": False}).to_csv(p_imerg, index=False)
    tabel, hasil = v.jalankan(p_bmkg, p_imerg, tmp_path / "validasi.csv")
    assert (tmp_path / "validasi.csv").exists() and len(tabel) == 1
    assert set(hasil) >= {"gpm_imerg_late", "gpm_imerg_final", "antarstasiun"}
