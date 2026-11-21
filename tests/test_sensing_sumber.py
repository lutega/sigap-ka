"""
Tujuan      : Menguji modul sumber lapis S: kontrak tabel standar, pengurai tiap sumber
              (NASA POWER, IMERG, GSMaP, BMKG, Glapan, BBWS, stasiun BMKG, jadwal KA), dan
              penanganan sumber tanpa kredensial.
Lapis       : QA, lapis S.
Sumber      : Fixture buatan berbentuk respons API asli (angka uji, bukan data nyata).
Masukan     : -
Keluaran    : -
Keterbatasan: Tidak mengakses internet; HTTP di-mock dengan pustaka responses.
"""

import gzip
import io
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest
import responses

from config import muat_params
from sensing import (
    hujan_bmkg_stasiun,
    hujan_gpm_imerg,
    hujan_gsmap,
    hujan_nasa_power,
    jadwal_ka,
    muka_air_bbws,
    muka_air_glapan,
    prakiraan_bmkg,
)
from sensing.standar import KOLOM_STANDAR, SumberTidakTersedia, validasi_standar

URL_POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
URL_BMKG = "https://api.bmkg.go.id/publik/prakiraan-cuaca"

JSON_POWER = {"properties": {"parameter": {"PRECTOTCORR": {
    "20250101": 1.5, "20250102": -999.0, "20250103": 600.0, "20250104": 0.0}}}}

JSON_BMKG = {
    "lokasi": {"adm4": "33.15.17.2001", "desa": "Uji"},
    "data": [{"lokasi": {}, "cuaca": [
        [{"local_datetime": "2025-01-24 07:00:00", "analysis_date": "2025-01-24T00:00:00", "tp": 9.9}],
        [{"local_datetime": "2025-01-24 13:00:00", "analysis_date": "2025-01-24T00:00:00", "tp": 2.5},
         {"local_datetime": "2025-01-24 16:00:00", "analysis_date": "2025-01-24T00:00:00", "tp": 0.0}],
    ]}],
}


def _cek_kontrak(df, simulasi: bool | None = None):
    """Memastikan tabel memenuhi kontrak standar (kolom, tipe is_simulated, sumber terisi)."""
    assert list(df.columns[:6]) == KOLOM_STANDAR or set(KOLOM_STANDAR) <= set(df.columns)
    validasi_standar(df, deret_waktu=True)
    if simulasi is not None:
        assert (df["is_simulated"] == simulasi).all()


# ---------------------------------------------------------------- kontrak bersama

def test_validasi_menolak_kolom_hilang():
    """Tabel tanpa kolom standar ditolak."""
    with pytest.raises(ValueError):
        validasi_standar(pd.DataFrame({"waktu": [datetime(2025, 1, 1)], "nilai": [1.0]}))


def test_validasi_menolak_is_simulated_bukan_boolean():
    """is_simulated wajib boolean."""
    df = pd.DataFrame({"waktu": [datetime(2025, 1, 1)], "lokasi": ["lokal"], "nilai": [1.0],
                       "satuan": ["mm"], "sumber": ["uji"], "is_simulated": ["ya"]})
    with pytest.raises(ValueError):
        validasi_standar(df)


def test_validasi_prakiraan_tidak_boleh_berlaku_sebelum_terbit():
    """Prakiraan dengan waktu valid sebelum terbit ditolak."""
    df = pd.DataFrame({"waktu_terbit": [datetime(2025, 1, 2)], "waktu": [datetime(2025, 1, 1)],
                       "lokasi": ["lokal"], "nilai": [1.0], "satuan": ["mm"], "sumber": ["uji"],
                       "is_simulated": [False]})
    with pytest.raises(ValueError):
        validasi_standar(df, prakiraan=True)


# ---------------------------------------------------------------- NASA POWER

@responses.activate
def test_nasa_power_pipeline_dan_kualitas():
    """NASA POWER: -999 menjadi kosong, nilai > batas ditandai janggal, nyata (is_simulated False)."""
    responses.add(responses.GET, URL_POWER, json=JSON_POWER, status=200)
    df, mentah = hujan_nasa_power.jalankan("lokal", date(2025, 1, 1), date(2025, 1, 4))
    _cek_kontrak(df, simulasi=False)
    assert list(df["kualitas"]) == ["baik", "kosong", "janggal", "baik"]
    assert (df["resolusi_jam"] == 24).all()
    assert "latitude=" in hujan_nasa_power.tautan(mentah)


@responses.activate
def test_nasa_power_gagal_jaringan_jadi_sumber_tidak_tersedia():
    """Galat HTTP diubah menjadi SumberTidakTersedia agar registri bisa beralih ke cadangan."""
    responses.add(responses.GET, URL_POWER, status=500)
    with pytest.raises(SumberTidakTersedia):
        hujan_nasa_power.ambil("lokal", date(2025, 1, 1), date(2025, 1, 2))


# ---------------------------------------------------------------- GPM IMERG

def test_imerg_tanpa_token_tidak_tersedia(monkeypatch):
    """Tanpa EARTHDATA_TOKEN modul memberi SumberTidakTersedia."""
    monkeypatch.setenv("EARTHDATA_TOKEN", "")
    with pytest.raises(SumberTidakTersedia):
        hujan_gpm_imerg.ambil("hulu", date(2025, 1, 1), date(2025, 1, 1), token="")


def test_imerg_urai_ascii_dan_nilai_pengisi():
    """Pengurai ASCII OPeNDAP mengambil nilai sel dan mengenali nilai pengisi."""
    teks = "Dataset: uji\nprecipitation.precipitation[1][1][1]\n[0][0], 12.5\n"
    assert hujan_gpm_imerg.urai_ascii(teks) == pytest.approx(12.5)
    assert np.isnan(hujan_gpm_imerg.urai_ascii("precipitation[0][0], -9999.9\n"))


@responses.activate
def test_imerg_pipeline_dengan_token():
    """Dengan token, tiap hari diminta ke OPeNDAP dan menjadi tabel standar."""
    responses.add(responses.GET, hujan_gpm_imerg.url_harian(date(2025, 1, 1), -7.25, 110.47),
                  body="precipitation.precipitation[1][1][1]\n[0][0], 3.25\n")
    df, _ = hujan_gpm_imerg.jalankan("hulu", date(2025, 1, 1), date(2025, 1, 1), token="uji")
    _cek_kontrak(df, simulasi=False)
    assert df.loc[0, "nilai"] == pytest.approx(3.25)
    assert responses.calls[0].request.headers["Authorization"] == "Bearer uji"


CSV_GIOVANNI = (
    "prod_name,GPM_3IMERGDL.07\nunit,mm/day\nundef,-9999.9\nlat,-7.249999999999997\nlon,110.45\n\n"
    "Timestamp (UTC),Data\n2025-01-20 00:00,53.5\n2025-01-21 00:00,-9999.9\n2025-01-22 00:00,12.7\n"
)


def test_imerg_urai_giovanni():
    """CSV Giovanni: metadata dibaca, nilai pengisi menjadi kosong."""
    from sensing.hujan_gpm_imerg import urai_giovanni
    meta, tabel = urai_giovanni(CSV_GIOVANNI)
    assert meta["lon"] == "110.45"
    assert list(tabel["nilai"].isna()) == [False, True, False]
    assert tabel["nilai"].iloc[0] == pytest.approx(53.5)


@responses.activate
def test_imerg_giovanni_late_ke_format_standar():
    """Jalur utama Giovanni: satu permintaan, hari UTC dicatat 07.00 WIB, sumber gpm_imerg_late."""
    import re
    responses.add(responses.GET, re.compile(r"https://api\.giovanni\.earthdata\.nasa\.gov/timeseries.*"),
                  body=CSV_GIOVANNI)
    df, mentah = hujan_gpm_imerg.jalankan("hulu", date(2025, 1, 20), date(2025, 1, 22), "late", token="uji")
    _cek_kontrak(df, simulasi=False)
    assert len(responses.calls) == 1 and "GPM_3IMERGDL_07" in mentah["url"]
    assert df["waktu"].iloc[0] == datetime(2025, 1, 20, 7)
    assert set(df["sumber"]) == {"gpm_imerg_late"}
    assert list(df["kualitas"]) == ["baik", "kosong", "baik"]


@responses.activate
def test_imerg_final_tidak_jatuh_ke_opendap():
    """Bila Giovanni gagal untuk produk Final, tidak ada cadangan OPeNDAP (OPeNDAP hanya Late)."""
    import re
    responses.add(responses.GET, re.compile(r"https://api\.giovanni.*"), status=500, json={"message": None})
    with pytest.raises(SumberTidakTersedia):
        hujan_gpm_imerg.jalankan("hulu", date(2025, 1, 20), date(2025, 1, 21), "final", token="uji")


@responses.activate
def test_imerg_eula_belum_disetujui_memberi_tautan():
    """403 'EULA Acceptance Failure' diubah menjadi pesan berisi tautan persetujuan aplikasi."""
    responses.add(responses.GET, hujan_gpm_imerg.url_harian(date(2025, 1, 1), -7.25, 110.47), status=403,
                  json={"status_code": 403, "error_description": "EULA Acceptance Failure",
                        "resolution_url": "https://urs.earthdata.nasa.gov/approve_app?client_id=uji"})
    with pytest.raises(SumberTidakTersedia, match="approve_app"):
        hujan_gpm_imerg.ambil("hulu", date(2025, 1, 1), date(2025, 1, 1), token="uji")


# ---------------------------------------------------------------- GSMaP

class _SftpTiruan:
    """Klien SFTP tiruan yang mengembalikan grid GSMaP buatan."""

    def __init__(self, isi: bytes):
        self.isi = isi
        self.jalur = []

    def open(self, jalur):
        self.jalur.append(jalur)
        return io.BytesIO(self.isi)


def test_gsmap_urai_grid_dan_konversi_wib(monkeypatch):
    """Sel lokasi terambil dari grid 3600x1200; jalur berkas memakai waktu UTC (WIB - 7)."""
    monkeypatch.setenv("JAXA_USER", "")
    titik = muat_params().lokasi["hulu"]
    grid = np.zeros((hujan_gsmap.NY, hujan_gsmap.NX), dtype="<f4")
    baris, kolom = hujan_gsmap.indeks_grid(titik["lat"], titik["lon"])
    grid[baris, kolom] = 4.2
    klien = _SftpTiruan(gzip.compress(grid.tobytes()))
    df, _ = hujan_gsmap.jalankan("hulu", datetime(2025, 1, 24, 7), datetime(2025, 1, 24, 8),
                                 klien_sftp=klien)
    _cek_kontrak(df, simulasi=False)
    assert list(df["nilai"].round(3)) == [4.2, 4.2]
    assert "gsmap_nrt.20250124.0000" in klien.jalur[0]


def test_gsmap_tanpa_kredensial_tidak_tersedia(monkeypatch):
    """Tanpa JAXA_USER/JAXA_PASSWORD modul memberi SumberTidakTersedia."""
    monkeypatch.setenv("JAXA_USER", "")
    monkeypatch.setenv("JAXA_PASSWORD", "")
    with pytest.raises(SumberTidakTersedia):
        hujan_gsmap.ambil("hulu", datetime(2025, 1, 1), datetime(2025, 1, 1))


# ---------------------------------------------------------------- BMKG

@responses.activate
def test_bmkg_prakiraan_waktu_terbit_dan_periode():
    """BMKG: analysis_date (UTC) + 7 jam = waktu terbit WIB; periode yang dimulai sebelum terbit dibuang."""
    responses.add(responses.GET, URL_BMKG, json=JSON_BMKG, status=200)
    df, _ = prakiraan_bmkg.jalankan()
    validasi_standar(df, prakiraan=True)
    assert (df["waktu_terbit"] == datetime(2025, 1, 24, 7)).all()
    assert list(df["waktu"]) == [datetime(2025, 1, 24, 10), datetime(2025, 1, 24, 13)]
    assert list(df["nilai"]) == [2.5, 0.0]
    assert not df["is_simulated"].any()


def test_bmkg_peringatan_disaring_menurut_wilayah():
    """Peringatan dini hanya yang menyebut wilayah koridor."""
    rss = ("<rss><channel>"
           "<item><title>Hujan lebat Grobogan</title><link>u1</link><pubDate>x</pubDate>"
           "<description>Waspada</description></item>"
           "<item><title>Hujan Bandung</title><link>u2</link><description>-</description></item>"
           "</channel></rss>")
    hasil = prakiraan_bmkg.ambil_peringatan(teks_rss=rss)
    assert [h["tautan"] for h in hasil] == ["u1"]


# ---------------------------------------------------------------- muka air dan data bersurat

def test_glapan_titik_nyata_dari_csv_manual():
    """CSV manual Glapan berisi titik nyata 1970 (24 Jan 2025) berlabel nyata."""
    df, _ = muka_air_glapan.jalankan()
    _cek_kontrak(df, simulasi=False)
    baris = df[df["waktu"].dt.date == date(2025, 1, 24)].iloc[0]
    assert baris["nilai"] == 1970
    assert not baris["jam_diketahui"]


@pytest.mark.parametrize("mod", [muka_air_bbws, hujan_bmkg_stasiun])
def test_data_bersurat_belum_ada_tidak_tersedia(mod, tmp_path):
    """Data bersurat yang belum diterima memberi SumberTidakTersedia (NFR-5)."""
    with pytest.raises(SumberTidakTersedia):
        mod.ambil(tmp_path / "tidak_ada.csv")


def test_bbws_bila_berkas_ada(tmp_path):
    """Bila CSV BBWS sudah diterima, modul menghasilkan tabel standar nyata."""
    p = tmp_path / "bbws.csv"
    p.write_text("waktu,lokasi,nilai,satuan\n2025-01-24 06:00,glapan,1950,cm\n", encoding="utf-8")
    _cek_kontrak(muka_air_bbws.jalankan(p), simulasi=False)


# ---------------------------------------------------------------- jadwal KA

def test_jadwal_placeholder_berlabel_dummy(tmp_path):
    """Tanpa jadwal nyata, placeholder KA-A s.d. KA-F dipakai dengan is_simulated True."""
    df = jadwal_ka.jalankan(tmp_path / "tidak_ada.csv")
    _cek_kontrak(df, simulasi=True)
    assert list(df["nomor"]) == ["KA-A", "KA-B", "KA-C", "KA-D", "KA-E", "KA-F"]
    assert (df["kualitas"] == "baik").all()


def test_jadwal_nyata_dari_csv(tmp_path):
    """Jadwal yang diisi manual berlabel nyata."""
    p = tmp_path / "jadwal.csv"
    p.write_text("nomor,relasi,jam_lewat_gubug,sumber\n101,A - B,08:15,uji\n", encoding="utf-8")
    df = jadwal_ka.jalankan(p)
    _cek_kontrak(df, simulasi=False)
