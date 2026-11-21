"""
Tujuan      : Membangun katalog kejadian gangguan dari unggahan KAI121/Daop 4: OCR untuk
              pengumuman berbentuk gambar, LLM untuk mengubah teks menjadi baris terstruktur,
              lalu peneliti memeriksa tiap baris (kode K1-K3). Presisi dan recall diukur
              terhadap koding manual.
Lapis       : S (Sensing), data inti, metode opsional (KEJADIAN_METODE=ocr_llm).
Sumber      : Berkas pengumuman di data/raw/pengumuman/ (.png/.jpg/.jpeg diproses OCR Tesseract,
              .txt dibaca langsung). LLM: Claude API (ANTHROPIC_API_KEY, LLM_MODEL di .env)
              dengan structured outputs (skema JSON) dan fallback sisi server bila model menolak.
Masukan     : Folder pengumuman; berkas periksa data/manual/kejadian_ocr_periksa.csv yang kolom
              kode_periksa-nya diisi peneliti.
Keluaran    : Tabel standar kejadian (format sama dengan kejadian_manual) berisi baris K1/K2.
Keterbatasan: Butuh Tesseract terpasang (TESSERACT_CMD) untuk gambar dan kunci API untuk LLM;
              tanpa keduanya metode manual tetap dipakai. Kode K1-K3 ditafsirkan sebagai
              K1 = benar tanpa koreksi, K2 = benar setelah dikoreksi peneliti, K3 = ditolak (A-020).
              LLM diminta tidak menebak; kolom yang tidak tertulis dibiarkan kosong.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from config import AKAR_REPO, muat_pengaturan
from sensing import kejadian_manual
from sensing.standar import DIR_MANUAL, SumberTidakTersedia

NAMA_SUMBER = "kejadian_ocr_llm"
DIR_PENGUMUMAN = AKAR_REPO / "data" / "raw" / "pengumuman"
BERKAS_PERIKSA = "kejadian_ocr_periksa.csv"
EKSTENSI_GAMBAR = {".png", ".jpg", ".jpeg"}
KODE_DITERIMA = {"K1", "K2"}

_NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}

# Skema JSON keluaran LLM (structured outputs menjamin JSON valid sesuai skema).
SKEMA_KEJADIAN = {
    "type": "object",
    "properties": {
        "kejadian": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tanggal": _NULLABLE_STR,       # YYYY-MM-DD
                    "jam_tutup": _NULLABLE_STR,     # YYYY-MM-DDTHH:MM (WIB)
                    "jam_buka": _NULLABLE_STR,
                    "lokasi_km": _NULLABLE_STR,
                    "mekanisme": {"type": "string", "enum": ["genangan", "gerusan", "tidak disebut"]},
                    "ka_terdampak": _NULLABLE_STR,
                    "relevan_koridor": {"type": "boolean"},
                    "kutipan": {"type": "string"},
                },
                "required": ["tanggal", "jam_tutup", "jam_buka", "lokasi_km", "mekanisme",
                             "ka_terdampak", "relevan_koridor", "kutipan"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["kejadian"],
    "additionalProperties": False,
}

PROMPT_SISTEM = (
    "Anda membantu peneliti menyusun katalog gangguan perjalanan kereta api akibat banjir di "
    "koridor Brumbung-Karangjati (Grobogan, Jawa Tengah; termasuk petak Gubug dan Karangjati). "
    "Dari teks pengumuman yang diberikan, ekstrak setiap kejadian gangguan jalur. Ambil hanya "
    "fakta yang tertulis eksplisit di teks; jangan menebak atau melengkapi. Bila tanggal, jam, KM, "
    "atau KA terdampak tidak tertulis, isi null. Mekanisme 'genangan' bila teks menyebut air "
    "menggenangi rel, 'gerusan' bila menyebut rel/tanah tergerus, amblas, atau tanggul jebol, "
    "selain itu 'tidak disebut'. Tulis tanggal sebagai YYYY-MM-DD dan jam sebagai "
    "YYYY-MM-DDTHH:MM dalam WIB. relevan_koridor bernilai true hanya bila lokasi di koridor "
    "tersebut. Isi kutipan dengan potongan kalimat sumber yang mendukung baris itu. Bila tidak "
    "ada kejadian, kembalikan daftar kosong."
)


class KlienLLM(Protocol):
    """Antarmuka minimal klien LLM (anthropic.Anthropic atau tiruan untuk tes)."""

    beta: Any


# ---------------------------------------------------------------- OCR dan pengambilan

def ocr_gambar(path: Path) -> str:
    """Membaca teks dari gambar pengumuman dengan Tesseract (bahasa Indonesia bila tersedia).

    Galat:
        SumberTidakTersedia bila pytesseract/Tesseract tidak terpasang.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError as galat:
        raise SumberTidakTersedia("OCR butuh paket pytesseract dan Pillow") from galat
    cmd = muat_pengaturan().tesseract_cmd
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    try:
        bahasa = "ind" if "ind" in pytesseract.get_languages(config="") else "eng"
        return pytesseract.image_to_string(Image.open(path), lang=bahasa)
    except pytesseract.TesseractNotFoundError as galat:
        raise SumberTidakTersedia("Tesseract belum terpasang (atur TESSERACT_CMD di .env)") from galat


def ambil(folder: Path | None = None) -> list[dict]:
    """Membaca semua pengumuman di folder: gambar lewat OCR, .txt dibaca langsung.

    Kembali:
        Daftar dict {'berkas', 'teks'}.
    Galat:
        SumberTidakTersedia bila folder kosong/tidak ada.
    """
    folder = folder or DIR_PENGUMUMAN
    if not folder.exists():
        raise SumberTidakTersedia(f"folder pengumuman {folder} belum ada")
    dokumen = []
    for path in sorted(folder.iterdir()):
        ext = path.suffix.lower()
        if ext == ".txt":
            dokumen.append({"berkas": path.name, "teks": path.read_text(encoding="utf-8")})
        elif ext in EKSTENSI_GAMBAR:
            dokumen.append({"berkas": path.name, "teks": ocr_gambar(path)})
    if not dokumen:
        raise SumberTidakTersedia(f"tidak ada pengumuman di {folder}")
    return dokumen


# ---------------------------------------------------------------- LLM

def buat_klien() -> KlienLLM:
    """Membuat klien Claude API. Galat SumberTidakTersedia bila paket/kredensial tidak ada."""
    try:
        import anthropic
    except ImportError as galat:
        raise SumberTidakTersedia("metode ocr_llm butuh paket anthropic") from galat
    kunci = muat_pengaturan().anthropic_api_key
    return anthropic.Anthropic(api_key=kunci) if kunci else anthropic.Anthropic()


def ekstrak_dengan_llm(teks: str, klien: KlienLLM | None = None, model: str | None = None) -> list[dict]:
    """Mengubah teks satu pengumuman menjadi daftar kejadian terstruktur.

    Memakai structured outputs (output_config.format json_schema) sehingga respons selalu JSON
    sesuai SKEMA_KEJADIAN, dan fallback sisi server bila model menolak permintaan.
    Parameter:
        teks: hasil OCR atau teks pengumuman.
        klien: klien anthropic (atau tiruan); bawaan dibuat dari .env.
        model: nama model; bawaan LLM_MODEL di .env.
    Kembali:
        Daftar dict sesuai skema.
    Galat:
        SumberTidakTersedia bila seluruh rantai model menolak atau API gagal.
    """
    klien = klien or buat_klien()
    model = model or muat_pengaturan().llm_model
    try:
        resp = klien.beta.messages.create(
            model=model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low",
                           "format": {"type": "json_schema", "schema": SKEMA_KEJADIAN}},
            system=PROMPT_SISTEM,
            messages=[{"role": "user", "content": f"Teks pengumuman:\n\n{teks}"}],
        )
    except Exception as galat:  # galat jaringan/API dari SDK
        raise SumberTidakTersedia(f"permintaan LLM gagal: {galat.__class__.__name__}") from galat
    if getattr(resp, "stop_reason", None) == "refusal":
        raise SumberTidakTersedia("LLM menolak mengekstrak pengumuman ini")
    teks_json = next(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return json.loads(teks_json)["kejadian"]


def ekstrak_semua(dokumen: list[dict], klien: KlienLLM | None = None) -> pd.DataFrame:
    """Mengekstrak semua dokumen menjadi tabel calon kejadian untuk diperiksa peneliti.

    Kembali:
        DataFrame kolom katalog + berkas, kutipan, relevan_koridor, kode_periksa (kosong).
    """
    baris = []
    for dok in dokumen:
        for k in ekstrak_dengan_llm(dok["teks"], klien=klien):
            baris.append({**k, "berkas": dok["berkas"]})
    df = pd.DataFrame(baris, columns=list(SKEMA_KEJADIAN["properties"]["kejadian"]["items"]["properties"])
                      + ["berkas"])
    df.insert(0, "id", [f"OCR-{i + 1:03d}" for i in range(len(df))])
    df["mekanisme"] = df["mekanisme"].replace({"tidak disebut": None})
    df["kode_periksa"] = ""  # diisi peneliti: K1 / K2 / K3
    df["status_konfirmasi"] = "menunggu pemeriksaan"
    return df


def simpan_untuk_diperiksa(df: pd.DataFrame, path: Path | None = None) -> Path:
    """Menyimpan calon kejadian ke data/manual/kejadian_ocr_periksa.csv untuk diperiksa peneliti."""
    path = path or DIR_MANUAL / BERKAS_PERIKSA
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="
")
    return path


# ---------------------------------------------------------------- format standar dan evaluasi

def ke_format_standar(tabel_periksa: pd.DataFrame) -> pd.DataFrame:
    """Mengubah tabel hasil pemeriksaan menjadi tabel standar; hanya baris K1/K2 yang dipakai."""
    d = tabel_periksa.copy()
    d["kode_periksa"] = d["kode_periksa"].fillna("").astype(str).str.upper().str.strip()
    d = d[d["kode_periksa"].isin(KODE_DITERIMA)].reset_index(drop=True)
    if d.empty:
        kosong = pd.DataFrame(columns=kejadian_manual.KOLOM_KATALOG + ["sumber"])
        return kejadian_manual.ke_format_standar(kosong, metode="ocr_llm", sumber=NAMA_SUMBER)
    d["sumber"] = d.get("berkas")
    d["status_konfirmasi"] = d["kode_periksa"].map({"K1": "terkonfirmasi (K1)", "K2": "dikoreksi peneliti (K2)"})
    d["catatan"] = d.get("kutipan")
    for kol in kejadian_manual.KOLOM_KATALOG:
        if kol not in d:
            d[kol] = None
    hasil = kejadian_manual.ke_format_standar(d, metode="ocr_llm", sumber=NAMA_SUMBER)
    hasil["kode_periksa"] = d["kode_periksa"].to_numpy()
    return hasil


def cek_kualitas(df: pd.DataFrame) -> pd.DataFrame:
    """Sama dengan pemeriksaan katalog manual."""
    return kejadian_manual.cek_kualitas(df)


def presisi_recall(hasil: pd.DataFrame, acuan: pd.DataFrame,
                   kunci: tuple[str, ...] = ("tanggal", "mekanisme")) -> dict[str, float]:
    """Presisi dan recall hasil OCR+LLM terhadap koding manual (spesifikasi 8.3).

    Parameter:
        hasil: tabel kejadian dari OCR+LLM.
        acuan: tabel kejadian koding manual.
        kunci: kolom pencocokan.
    Kembali:
        {'presisi', 'recall', 'cocok', 'jumlah_hasil', 'jumlah_acuan'}.
    """
    def _kunci(df: pd.DataFrame) -> set[tuple]:
        return {tuple(str(r[k]) for k in kunci) for _, r in df.iterrows()}
    h, a = _kunci(hasil), _kunci(acuan)
    cocok = len(h & a)
    return {
        "presisi": cocok / len(h) if h else 0.0,
        "recall": cocok / len(a) if a else 0.0,
        "cocok": cocok,
        "jumlah_hasil": len(h),
        "jumlah_acuan": len(a),
    }


def jalankan(path_periksa: Path | None = None) -> pd.DataFrame:
    """Membaca berkas periksa (yang sudah diberi kode K1-K3) menjadi tabel standar berkualitas.

    Galat:
        SumberTidakTersedia bila berkas periksa belum ada.
    """
    path_periksa = path_periksa or DIR_MANUAL / BERKAS_PERIKSA
    if not path_periksa.exists():
        raise SumberTidakTersedia("berkas periksa OCR+LLM belum ada; jalankan ekstraksi lebih dulu")
    return cek_kualitas(ke_format_standar(pd.read_csv(path_periksa, encoding="utf-8", dtype=str)))
