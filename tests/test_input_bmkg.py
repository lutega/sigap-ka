"""
Tujuan      : Menguji kontrak input (base.py), pembaca dan pembersih curah hujan BMKG (bmkg.py),
              adapter IMERG (imerg.py), dan fitur hujan harian per zona (features/hujan.py).
Lapis       : QA, lapis S dan penyiapan fitur.
Sumber      : Berkas .csv/.xlsx buatan tes berformat mirip unduhan portal BMKG (angka uji, bukan
              data nyata).
Masukan     : -
Keluaran    : -
Keterbatasan: Format persis berkas portal BMKG belum diverifikasi dengan berkas asli.
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from sigap_ka.features import hujan as fitur_hujan
from sigap_ka.inputs import bmkg, imerg
from sigap_ka.inputs.base import GalatSkema, KOLOM_WAJIB, ke_tabel_standar, validasi

PEMETAAN_UJI = {
    "zona_hujan": ["lokal_gubug_karangjati", "hulu_tuntang", "gundih"],
    "zona_lain": ["semarang_pembanding"],
    "stasiun": {
        "Pos Hujan Gubug": {"zona": "lokal_gubug_karangjati", "alias": ["Gubug"]},
        "Pos Hujan Tuntang": {"zona": "hulu_tuntang", "alias": ["Tuntang"]},
    },
}


def _tulis_csv_bmkg(path, nama_stasiun, baris_data):
    """Berkas CSV mirip unduhan BMKG: metadata, judul tabel, data, catatan kaki."""
    isi = [
        "ID WMO,: 00000,,",
        f"Nama Stasiun,: {nama_stasiun},,",
        "Lintang,: -7.0,,",
        ",,,",
        "Tanggal,Tn,Tx,RR",
    ] + [f"{t},22.0,31.0,{rr}" for t, rr in baris_data] + [
        ",,,",
        "KETERANGAN: 8888 = data tidak terukur; 9999 = tidak ada data,,,",
    ]
    path.write_text("\n".join(isi) + "\n", encoding="utf-8")


@pytest.fixture
def folder_bmkg(tmp_path):
    """Folder mentah berisi satu CSV (Gubug), satu XLSX (Tuntang), dan satu stasiun tak terpetakan."""
    d = tmp_path / "bmkg"
    d.mkdir()
    _tulis_csv_bmkg(d / "gubug.csv", "Pos Hujan Gubug", [
        ("01-01-2025", "12.5"), ("02-01-2025", "8888"), ("03-01-2025", "9999"),
        ("04-01-2025", "-3"), ("05-01-2025", "4.0"), ("05-01-2025", "4.0"),
        ("06-01-2025", "7.0"), ("06-01-2025", "9.0"), ("07-01-2025", ""), ("08-01-2025", "x"),
    ])
    xlsx = pd.DataFrame([
        ["Nama Stasiun", "Pos Hujan Tuntang", None],
        [None, None, None],
        ["Tanggal", "RR", "ss"],
        ["01-01-2025", 20.0, 5],
        ["02-01-2025", 30.0, 4],
        ["03-01-2025", 0.0, 6],
    ])
    xlsx.to_excel(d / "tuntang.xlsx", header=False, index=False)
    _tulis_csv_bmkg(d / "lain.csv", "Stasiun Entah", [("01-01-2025", "1.0")])
    (d / "catatan.txt").write_text("bukan data", encoding="utf-8")
    return d


# ---------------------------------------------------------------- kontrak base

def test_validator_menolak_pelanggaran_kontrak():
    """Kolom hilang, status tidak dikenal, zona di luar daftar, tanggal bukan datetime ditolak."""
    baik = pd.DataFrame({"tanggal": [datetime(2025, 1, 1)], "zona": ["hulu_tuntang"], "nilai": [1.0],
                         "sumber": ["bmkg"], "status_data": ["nyata"]})
    validasi(baik, ["hulu_tuntang"])
    with pytest.raises(GalatSkema):
        validasi(baik.drop(columns=["sumber"]))
    with pytest.raises(GalatSkema):
        validasi(baik.assign(status_data="tebakan"))
    with pytest.raises(GalatSkema):
        validasi(baik, ["gundih"])
    with pytest.raises(GalatSkema):
        validasi(baik.assign(tanggal="2025-01-01"))


def test_adapter_ke_tabel_standar_lama():
    """Adapter menghasilkan kolom standar lapis S lama dengan is_simulated dari status_data."""
    df = pd.DataFrame({"tanggal": [datetime(2025, 1, 1)] * 2, "zona": ["glapan"] * 2, "nilai": [1.0, 2.0],
                       "sumber": ["a", "b"], "status_data": ["nyata", "sintetis"]})
    s = ke_tabel_standar(df, "cm")
    assert list(s.columns) == ["waktu", "lokasi", "nilai", "satuan", "sumber", "is_simulated"]
    assert list(s["is_simulated"]) == [False, True]


# ---------------------------------------------------------------- BMKG

def test_baca_berkas_csv_dan_xlsx_dengan_metadata(folder_bmkg):
    """Nama stasiun diambil dari baris metadata; tanggal dd-mm-yyyy terbaca; catatan kaki dibuang."""
    c = bmkg.baca_berkas(folder_bmkg / "gubug.csv")
    assert set(c["stasiun"]) == {"Pos Hujan Gubug"}
    assert c["tanggal"].min() == pd.Timestamp("2025-01-01") and c["tanggal"].max() == pd.Timestamp("2025-01-08")
    x = bmkg.baca_berkas(folder_bmkg / "tuntang.xlsx")
    assert set(x["stasiun"]) == {"Pos Hujan Tuntang"} and len(x) == 3


def test_bersihkan_kode_anomali_negatif_dan_tanggal_ganda(folder_bmkg):
    """8888/9999/negatif/teks -> NaN; tanggal ganda sama -> satu baris; berbeda -> NaN."""
    b = bmkg.bersihkan(bmkg.baca_berkas(folder_bmkg / "gubug.csv")).set_index("tanggal")
    assert b.loc["2025-01-01", "nilai"] == pytest.approx(12.5)
    for tgl, alasan in [("2025-01-02", "kode 8888"), ("2025-01-03", "kode 9999"), ("2025-01-04", "negatif"),
                        ("2025-01-07", "kosong"), ("2025-01-08", "tak terbaca")]:
        assert np.isnan(b.loc[tgl, "nilai"]) and b.loc[tgl, "catatan_qc"] == alasan, tgl
    assert b.loc["2025-01-05", "nilai"] == pytest.approx(4.0)
    assert np.isnan(b.loc["2025-01-06", "nilai"]) and "berbeda" in b.loc["2025-01-06", "catatan_qc"]
    assert not b.index.duplicated().any()


def test_jalankan_memetakan_zona_menandai_dan_menyimpan(folder_bmkg, tmp_path):
    """Stasiun dipetakan ke zona lewat config; sumber bmkg, status nyata; tak terpetakan dilaporkan."""
    keluar = tmp_path / "interim" / "bmkg_clean.csv"
    hasil, lap = bmkg.jalankan(folder_bmkg, keluar, PEMETAAN_UJI)
    assert keluar.exists()
    assert set(hasil["zona"]) == {"lokal_gubug_karangjati", "hulu_tuntang"}
    assert set(hasil["sumber"]) == {"bmkg"} and set(hasil["status_data"]) == {"nyata"}
    assert lap["stasiun_tak_terpetakan"] == ["Stasiun Entah"]
    assert lap["jumlah_nan"] == 6
    assert list(hasil.columns[:5]) == KOLOM_WAJIB
    disimpan = pd.read_csv(keluar)
    assert len(disimpan) == len(hasil)


def test_folder_kosong_tidak_galat(tmp_path):
    """Tanpa berkas BMKG, keluaran kosong berskema benar dan diberi catatan."""
    hasil, lap = bmkg.jalankan(tmp_path / "tidak_ada", tmp_path / "bmkg_clean.csv", PEMETAAN_UJI)
    assert hasil.empty and list(hasil.columns[:5]) == KOLOM_WAJIB
    assert lap["berkas_gagal"]


def test_pemetaan_bawaan_stasiun_semarang_hanya_pembanding():
    """Stasiun Kota Semarang tidak dipetakan ke zona lokal/hulu/Gundih (jarak 25-30 km)."""
    pem = bmkg.muat_pemetaan()
    assert bmkg.cari_stasiun("STASIUN METEOROLOGI AHMAD YANI", pem) == ("Stasiun Meteorologi Ahmad Yani", "semarang_pembanding")
    assert bmkg.cari_stasiun("Stasiun Klimatologi Jawa Tengah", pem)[1] == "semarang_pembanding"
    assert bmkg.cari_stasiun("Stasiun Entah", pem) is None


# ---------------------------------------------------------------- IMERG dan fitur hujan

def test_adapter_imerg_hari_utc(tmp_path):
    """Waktu IMERG 07.00 WIB dikembalikan ke tanggal hari UTC; lokasi dipetakan ke zona."""
    p = tmp_path / "imerg.csv"
    pd.DataFrame({"waktu": ["2025-01-20 07:00:00", "2025-01-20 07:00:00"], "lokasi": ["hulu", "lokal"],
                  "nilai": [53.5, 61.4], "satuan": "mm", "sumber": "gpm_imerg_late",
                  "is_simulated": False}).to_csv(p, index=False)
    d = imerg.jalankan(path=p)
    assert set(d["zona"]) == {"hulu_tuntang", "lokal_gubug_karangjati"}
    assert (d["tanggal"] == pd.Timestamp("2025-01-20")).all() and set(d["status_data"]) == {"nyata"}


def _seri(zona, sumber, nilai, mulai="2025-01-01"):
    tgl = pd.date_range(mulai, periods=len(nilai), freq="D")
    return pd.DataFrame({"tanggal": tgl, "zona": zona, "nilai": nilai, "sumber": sumber, "status_data": "nyata"})


def test_fitur_hujan_prioritas_bmkg_dan_cadangan_imerg():
    """BMKG dipakai bila terisi; hari BMKG kosong dan zona tanpa BMKG memakai IMERG Late."""
    b = _seri("lokal_gubug_karangjati", "bmkg", [10.0, np.nan, 30.0, 40.0, 50.0])
    i = pd.concat([_seri(z, "gpm_imerg_late", [1.0, 2.0, 3.0, 4.0, 5.0]) for z in
                   ("lokal_gubug_karangjati", "hulu_tuntang", "gundih")], ignore_index=True)
    zona = fitur_hujan.hujan_zona_harian({"bmkg": b, "gpm_imerg_late": i}, ["bmkg", "gpm_imerg_late"])
    lokal = zona[zona["zona"] == "lokal_gubug_karangjati"].set_index("tanggal")
    assert list(lokal["sumber"]) == ["bmkg", "gpm_imerg_late", "bmkg", "bmkg", "bmkg"]
    f = fitur_hujan.hitung_fitur(zona).set_index("tanggal")
    assert f.loc["2025-01-03", "hujan_lokal_3d"] == pytest.approx(10 + 2 + 30)
    assert f.loc["2025-01-05", "hujan_lokal_5d"] == pytest.approx(10 + 2 + 30 + 40 + 50)
    assert np.isnan(f.loc["2025-01-02", "hujan_lokal_3d"])        # jendela belum penuh
    assert f.loc["2025-01-03", "hujan_hulu_3d"] == pytest.approx(6.0)
    assert f.loc["2025-01-02", "hujan_gundih_1d"] == pytest.approx(2.0)
    assert f.loc["2025-01-02", "sumber_lokal"] == "gpm_imerg_late"


def test_fitur_hujan_hari_tanpa_data_menjadi_nan(tmp_path):
    """Hari yang tidak ada di sumber mana pun membuat jendela yang memuatnya NaN (tidak ditebak)."""
    i = _seri("hulu_tuntang", "gpm_imerg_late", [5.0, 5.0, 5.0, 5.0, 5.0])
    i = i.drop(index=2)  # 3 Jan hilang
    f = fitur_hujan.hitung_fitur(fitur_hujan.hujan_zona_harian({"gpm_imerg_late": i}, ["gpm_imerg_late"]))
    f = f.set_index("tanggal")
    assert np.isnan(f.loc["2025-01-03", "hujan_hulu_3d"]) and np.isnan(f.loc["2025-01-05", "hujan_hulu_3d"])
    keluar = fitur_hujan.jalankan(tmp_path / "hujan_features.csv", {"gpm_imerg_late": i})
    assert (tmp_path / "hujan_features.csv").exists() and len(keluar) == 5
