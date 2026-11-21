"""
Tujuan      : Menguji generator dummy, muka air sintetis, registri sumber (rantai cadangan),
              dan CLI lapis S (proses manual dan muat ke database).
Lapis       : QA, lapis S.
Sumber      : params.json, berkas manual repo, HTTP tiruan.
Masukan     : -
Keluaran    : -
Keterbatasan: Rentang laju gangguan yang diuji adalah sifat parameter dummy, bukan klaim nyata.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
import responses

from config import muat_params
from sensing import dummy_generator, muka_air_sintetis, registri
from sensing.standar import validasi_standar


@pytest.fixture(scope="module")
def episode_base():
    """120 episode sintetis preset base dengan seed tetap."""
    return dummy_generator.ambil(120, 11, "base")


def test_generator_dapat_diulang():
    """Seed sama -> keluaran identik; seed berbeda -> berbeda (NFR-4)."""
    a = dummy_generator.ambil(3, 5, "base")
    b = dummy_generator.ambil(3, 5, "base")
    c = dummy_generator.ambil(3, 6, "base")
    for x, y in zip(a, b):
        pd.testing.assert_frame_equal(x.hujan, y.hujan)
        pd.testing.assert_frame_equal(x.prakiraan, y.prakiraan)
        assert x.kebenaran == y.kebenaran
    assert not np.allclose(a[0].hujan["nilai"], c[0].hujan["nilai"])


def test_semua_keluaran_dummy_berlabel_simulasi(episode_base):
    """Seluruh tabel generator berlabel is_simulated = True dan lolos kontrak standar."""
    for ep in episode_base[:10]:
        tabel = dummy_generator.cek_kualitas(dummy_generator.ke_format_standar(ep))
        for df in tabel.values():
            assert df["is_simulated"].all()
            assert (df["kualitas"] == "baik").all()
        assert ep.laporan.empty or ep.laporan["is_simulated"].all()


def test_prakiraan_terbit_sebelum_berlaku(episode_base):
    """Setiap prakiraan berlaku setelah atau tepat saat terbit, dan terbit tiap jam keputusan."""
    ep = episode_base[0]
    validasi_standar(ep.prakiraan, prakiraan=True)
    p = muat_params("base").episode
    terbit = sorted(ep.prakiraan["waktu_terbit"].unique())
    assert len(terbit) == p.jumlah_langkah
    assert pd.Timestamp(terbit[-1]) == pd.Timestamp(ep.t0)


def test_galat_prakiraan_mengecil_mendekati_t0():
    """Prakiraan dekat T-0 lebih akurat daripada prakiraan jauh (informasi membaik)."""
    eps = dummy_generator.ambil(150, 3, "base")
    galat = {72: [], 12: []}
    for ep in eps:
        hujan = ep.hujan[ep.hujan["lokasi"] == "hulu"].set_index("waktu")["nilai"]
        for lead in galat:
            terbit = ep.t0 - timedelta(hours=lead)
            pk = ep.prakiraan[(ep.prakiraan["waktu_terbit"] == terbit) & (ep.prakiraan["lokasi"] == "hulu")]
            benar = hujan[(hujan.index >= terbit) & (hujan.index < terbit + timedelta(hours=24))].sum()
            galat[lead].append(abs(np.log((pk["nilai"].sum() + 1) / (benar + 1))))
    assert np.mean(galat[12]) < np.mean(galat[72])


def test_laju_gangguan_wajar_dan_naik_menurut_preset():
    """Laju gangguan dummy: low < base < high, base dalam rentang yang membuat simulasi bermakna."""
    laju = {p: np.mean([e.kebenaran["terganggu"] for e in dummy_generator.ambil(200, 9, p)])
            for p in ("low", "base", "high")}
    assert laju["low"] < laju["base"] < laju["high"]
    assert 0.15 <= laju["base"] <= 0.45


def test_ada_kasus_mirip_e3_e6(episode_base):
    """Ada episode terganggu dengan hujan lokal rendah (bukti hulu menentukan), seperti E3/E6."""
    kasus = [e for e in episode_base if e.kebenaran["terganggu"]
             and e.kebenaran["fitur_kebenaran"]["hujan_lokal_3h"] < 0.6]
    assert kasus, "generator harus menghasilkan gangguan dengan hujan lokal rendah"


def test_kebenaran_konsisten(episode_base):
    """Episode terganggu punya mekanisme dan lama tutup dalam rentang skenarionya."""
    lt = muat_params("base").lama_tutup
    for e in episode_base:
        k = e.kebenaran
        if k["terganggu"]:
            sk = lt.skenario[k["skenario_lama_tutup"]]
            assert k["mekanisme"] in ("genangan", "gerusan")
            assert sk.jam_min <= k["lama_tutup_jam"] <= sk.jam_maks
        else:
            assert k["mekanisme"] is None


def test_muka_air_sintetis_naik_saat_hujan_dan_berlabel():
    """Waduk linear: hujan menaikkan elevasi lalu surut; keluaran berlabel sintetis."""
    waktu = pd.date_range("2025-01-01", periods=72, freq="h")
    nilai = np.zeros(72)
    nilai[10:20] = 8.0
    hulu = pd.DataFrame({"waktu": waktu, "lokasi": "hulu", "nilai": nilai, "satuan": "mm",
                         "sumber": "uji", "is_simulated": True, "resolusi_jam": 1})
    df = muka_air_sintetis.jalankan(hulu, hulu.assign(lokasi="lokal"))
    elev = df[df["lokasi"] == "glapan"]["nilai"].to_numpy()
    assert elev[20] > elev[5] and elev[71] < elev[20]
    assert df["is_simulated"].all()
    assert set(df["lokasi"]) == {"glapan", "badan_rel"}


def test_hujan_harian_dibagi_rata_ke_jam():
    """Masukan harian dibagi rata menjadi 24 jam (A-019)."""
    df = pd.DataFrame({"waktu": [pd.Timestamp("2025-01-01")], "nilai": [48.0], "resolusi_jam": [24]})
    seri = muka_air_sintetis.ke_per_jam(df)
    assert len(seri) == 24 and seri.iloc[0] == pytest.approx(2.0)


# ---------------------------------------------------------------- registri

@responses.activate
def test_rantai_cadangan_hujan_hulu_ke_nasa_power(monkeypatch):
    """Tanpa kredensial IMERG dan GSMaP, registri beralih ke NASA POWER dan mencatat percobaan."""
    monkeypatch.setenv("EARTHDATA_TOKEN", "")
    monkeypatch.setenv("JAXA_USER", "")
    monkeypatch.setenv("SUMBER_HUJAN_HULU", "gpm_imerg")
    responses.add(responses.GET, "https://power.larc.nasa.gov/api/temporal/daily/point",
                  json={"properties": {"parameter": {"PRECTOTCORR": {"20250101": 2.0}}}})
    hasil = registri.ambil_hujan_hulu(date(2025, 1, 1), date(2025, 1, 1))
    assert hasil.sumber == "nasa_power"
    assert [p["status"] for p in hasil.percobaan] == ["dilewati", "dilewati", "sukses"]
    assert hasil.memakai_cadangan


@responses.activate
def test_rantai_cadangan_terakhir_dummy_berlabel(monkeypatch):
    """Bila semua sumber gagal, cadangan terakhir adalah dummy berlabel is_simulated True."""
    monkeypatch.setenv("EARTHDATA_TOKEN", "")
    monkeypatch.setenv("JAXA_USER", "")
    responses.add(responses.GET, "https://power.larc.nasa.gov/api/temporal/daily/point", status=503)
    hasil = registri.ambil_hujan_hulu(date(2025, 1, 1), date(2025, 1, 10))
    assert hasil.sumber == "dummy_generator"
    assert hasil.data["is_simulated"].all() and len(hasil.data) == 10


def test_pemilih_metode_kejadian(monkeypatch):
    """KEJADIAN_METODE=ocr_llm tanpa berkas periksa jatuh ke metode manual."""
    monkeypatch.setenv("KEJADIAN_METODE", "ocr_llm")
    m, catatan = registri.modul_kejadian()
    assert m.NAMA_SUMBER == "kejadian_manual" and "manual" in catatan


def test_status_sumber_lengkap():
    """Status memuat semua sumber params.json; data bersurat yang belum ada berstatus belum siap."""
    status = {s["nama"]: s for s in registri.status_sumber()}
    assert set(status) == set(muat_params().sumber_data)
    assert status["bbws"]["siap"] is False and status["bbws"]["kelompok"] == "tambahan"


# ---------------------------------------------------------------- CLI

def test_cli_manual_dan_muat_ke_db(tmp_path, monkeypatch, engine_sqlite):
    """Perintah manual menulis CSV olahan + log; perintah muat memasukkannya ke database."""
    from db import repositori as repo
    from db.koneksi import pabrik_sesi
    from sensing import jalankan

    from config import reset_cache
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    reset_cache()  # pengaturan dibaca ulang agar DATA_DIR sementara dipakai
    jalankan.ambil_manual()
    assert (tmp_path / "kejadian.csv").exists() and (tmp_path / "log_pengambilan.csv").exists()
    jumlah = jalankan.muat_ke_db(engine_sqlite)
    assert jumlah["kejadian"] == 6 and jumlah["jadwal_ka"] == 6 and jumlah["obs_muka_air"] == 1
    sesi = pabrik_sesi(engine_sqlite)()
    assert len(repo.ambil_kejadian(sesi)) == 6
    sumber = {s["nama"]: s for s in repo.daftar_sumber(sesi)}
    assert sumber["glapan_bnpb"]["status_terakhir"] == "sukses"
    sesi.close()
