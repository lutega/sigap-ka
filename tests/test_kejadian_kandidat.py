"""
Tujuan      : Menguji pembaca katalog kejadian kandidat (inputs/kejadian_kandidat.py): validasi
              struktur, aturan T-0 tanpa jam, dan ringkasan publik tanpa tautan dan tanpa klaim aman.
Lapis       : S (Sensing), QA.
Sumber      : data/manual/kejadian_kandidat.csv dan CSV buatan tes.
Masukan     : -
Keluaran    : -
Keterbatasan: Tidak memeriksa kebenaran isi berita.
"""

from datetime import datetime

import pandas as pd
import pytest

from action.penjaga_klaim import pastikan_tanpa_klaim_aman
from sigap_ka.inputs import kejadian_kandidat as kk
from sigap_ka.inputs.base import GalatSkema


def _csv(tmp_path, **ubah):
    """CSV satu baris valid; kolom dapat diubah lewat argumen."""
    baris = {k: "" for k in kk.KOLOM}
    baris.update(id_kandidat="X1", tanggal="2025-01-24", jam_acuan="22:25", jenis_gangguan="tutup_dua_jalur",
                 mekanisme="gerusan", sumber_dibaca="https://www.contoh.id/a | https://berita.contoh.id/b",
                 status="kandidat; uji")
    baris.update(ubah)
    p = tmp_path / "kandidat.csv"
    pd.DataFrame([baris]).to_csv(p, index=False)
    return p


def test_katalog_repo_valid_dan_berstatus_kandidat():
    """Katalog di repo lolos validasi, semua berstatus kandidat, kolom E1-E6 tidak diisi sepihak."""
    df = kk.baca()
    assert len(df) >= 5
    assert df["status"].str.startswith("kandidat").all()
    assert (df["kemungkinan_E"] == "").all()


def test_t0_dengan_dan_tanpa_jam(tmp_path):
    """Jam tersedia -> T-0 tepat; tanpa jam -> pukul 00.00 hari kejadian, jam_diketahui False."""
    r = kk.baca(_csv(tmp_path)).iloc[0]
    assert kk.t0(r) == (datetime(2025, 1, 24, 22, 25), True)
    r = kk.baca(_csv(tmp_path, jam_acuan="")).iloc[0]
    assert kk.t0(r) == (datetime(2025, 1, 24, 0, 0), False)
    t = kk.tabel_t0(kk.baca(_csv(tmp_path)))
    assert bool(t.loc[0, "tutup"]) and t.loc[0, "mekanisme"] == "gerusan"


@pytest.mark.parametrize("ubah", [
    {"jam_acuan": "25:00"}, {"tanggal": "24/01/2025"}, {"jenis_gangguan": "putus"},
    {"mekanisme": "longsor"}, {"sumber_dibaca": ""}, {"status": "terkonfirmasi"},
])
def test_validasi_menolak_baris_salah(tmp_path, ubah):
    """Jam, tanggal, kategori, sumber kosong, atau status bukan kandidat ditolak."""
    with pytest.raises(GalatSkema):
        kk.baca(_csv(tmp_path, **ubah))


def test_ringkasan_publik_tanpa_tautan_dan_tanpa_klaim_aman():
    """Ringkasan untuk API hanya memuat domain sumber dan lolos penjaga klaim."""
    ringkas = kk.ringkasan_publik()
    pastikan_tanpa_klaim_aman(ringkas)
    for r in ringkas:
        assert r["sumber"] and all("/" not in d for d in r["sumber"])


def test_domain_sumber():
    """Domain diambil tanpa www., tanpa duplikat."""
    assert kk.domain_sumber("https://www.detik.com/a | https://detik.com/b | https://bnpb.go.id/c") == [
        "detik.com", "bnpb.go.id"]
