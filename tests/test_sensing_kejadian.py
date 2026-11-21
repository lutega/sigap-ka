"""
Tujuan      : Menguji katalog kejadian: metode manual dan metode OCR + LLM (dengan klien LLM
              tiruan), kode periksa K1-K3, serta presisi/recall terhadap koding manual.
Lapis       : QA, lapis S.
Sumber      : data/manual/kejadian.csv dan teks pengumuman buatan.
Masukan     : -
Keluaran    : -
Keterbatasan: Tidak memanggil Claude API sungguhan.
"""

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from sensing import kejadian_manual, kejadian_ocr_llm
from sensing.standar import SumberTidakTersedia, validasi_standar


def test_katalog_manual_e1_sampai_e6_tanpa_tebakan():
    """Katalog manual memuat E1-E6; kolom yang belum diketahui kosong dan berstatus belum terkonfirmasi."""
    df = kejadian_manual.jalankan()
    validasi_standar(df)
    assert list(df["id"]) == ["E1", "E2", "E3", "E4", "E5", "E6"]
    assert (df["status_konfirmasi"] == "belum terkonfirmasi").all()
    assert df["jam_tutup"].isna().all()  # tidak ada jam yang dikarang
    assert (df["kualitas"] == "kosong").all()
    assert not df["is_simulated"].any()


def test_katalog_manual_lama_tutup_dan_kualitas(tmp_path):
    """Lama tutup dihitung dari jam buka - jam tutup; mekanisme tak dikenal ditandai janggal."""
    p = tmp_path / "k.csv"
    p.write_text(
        "id,tanggal,jam_tutup,jam_buka,lokasi_km,mekanisme,ka_terdampak,sumber,status_konfirmasi,catatan\n"
        "X1,2025-01-01,2025-01-01 10:00,2025-01-01 16:00,KM 1,Genangan,KA uji,uji,terkonfirmasi,\n"
        "X2,2025-01-02,2025-01-02 10:00,2025-01-02 11:00,KM 2,longsor,,uji,terkonfirmasi,\n",
        encoding="utf-8")
    df = kejadian_manual.jalankan(p)
    assert df.loc[0, "nilai"] == pytest.approx(6.0)
    assert df.loc[0, "mekanisme"] == "genangan"
    assert list(df["kualitas"]) == ["baik", "janggal"]


class _KlienTiruan:
    """Klien LLM tiruan dengan bentuk client.beta.messages.create."""

    def __init__(self, keluaran: dict, stop_reason: str = "end_turn"):
        self.panggilan = []
        keluaran_json = json.dumps(keluaran)

        def create(**kw):
            self.panggilan.append(kw)
            return SimpleNamespace(stop_reason=stop_reason,
                                   content=[SimpleNamespace(type="text", text=keluaran_json)])
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=create))


KELUARAN_LLM = {"kejadian": [
    {"tanggal": "2025-01-24", "jam_tutup": "2025-01-24T21:30", "jam_buka": "2025-01-25T06:00",
     "lokasi_km": "KM 30+500", "mekanisme": "genangan", "ka_terdampak": "KA uji",
     "relevan_koridor": True, "kutipan": "jalur tergenang di petak Gubug"},
    {"tanggal": "2025-02-01", "jam_tutup": None, "jam_buka": None, "lokasi_km": None,
     "mekanisme": "tidak disebut", "ka_terdampak": None, "relevan_koridor": False,
     "kutipan": "gangguan di lintas lain"},
]}


def test_llm_memakai_structured_outputs_dan_fallback():
    """Permintaan memakai skema JSON (structured outputs) dan fallback sisi server."""
    klien = _KlienTiruan(KELUARAN_LLM)
    hasil = kejadian_ocr_llm.ekstrak_dengan_llm("teks uji", klien=klien, model="claude-opus-5-5")
    kw = klien.panggilan[0]
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["output_config"]["format"]["schema"] == kejadian_ocr_llm.SKEMA_KEJADIAN
    assert kw["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in kw["betas"]
    assert len(hasil) == 2


def test_llm_menolak_menjadi_sumber_tidak_tersedia():
    """stop_reason refusal ditangani, bukan dibaca sebagai JSON."""
    with pytest.raises(SumberTidakTersedia):
        kejadian_ocr_llm.ekstrak_dengan_llm("x", klien=_KlienTiruan({}, stop_reason="refusal"), model="m")


def test_alur_ocr_llm_sampai_kode_periksa(tmp_path):
    """Teks -> LLM -> berkas periksa -> hanya baris K1/K2 masuk katalog."""
    folder = tmp_path / "pengumuman"
    folder.mkdir()
    (folder / "p1.txt").write_text("Pengumuman uji", encoding="utf-8")
    dokumen = kejadian_ocr_llm.ambil(folder)
    tabel = kejadian_ocr_llm.ekstrak_semua(dokumen, klien=_KlienTiruan(KELUARAN_LLM))
    assert list(tabel["id"]) == ["OCR-001", "OCR-002"]
    assert (tabel["kode_periksa"] == "").all()
    tabel["kode_periksa"] = ["K1", "K3"]  # peneliti menerima baris 1, menolak baris 2
    path = kejadian_ocr_llm.simpan_untuk_diperiksa(tabel, tmp_path / "periksa.csv")
    katalog = kejadian_ocr_llm.jalankan(path)
    validasi_standar(katalog)
    assert list(katalog["id"]) == ["OCR-001"]
    assert katalog.loc[0, "metode"] == "ocr_llm"
    assert katalog.loc[0, "nilai"] == pytest.approx(8.5)
    assert katalog.loc[0, "kode_periksa"] == "K1"


def test_presisi_recall_terhadap_koding_manual():
    """Presisi dan recall dihitung dari kecocokan (tanggal, mekanisme)."""
    hasil = pd.DataFrame({"tanggal": ["2025-01-24", "2025-02-01"], "mekanisme": ["genangan", "gerusan"]})
    acuan = pd.DataFrame({"tanggal": ["2025-01-24", "2025-03-01", "2025-04-01"],
                          "mekanisme": ["genangan", "genangan", "gerusan"]})
    m = kejadian_ocr_llm.presisi_recall(hasil, acuan)
    assert m["presisi"] == pytest.approx(0.5)
    assert m["recall"] == pytest.approx(1 / 3)


def test_ocr_llm_tanpa_folder_tidak_tersedia(tmp_path):
    """Folder pengumuman yang belum ada memberi SumberTidakTersedia."""
    with pytest.raises(SumberTidakTersedia):
        kejadian_ocr_llm.ambil(tmp_path / "kosong")
