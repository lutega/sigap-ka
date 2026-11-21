"""
Tujuan      : Menaksir mekanisme gangguan (genangan atau gerusan) dan bukti yang paling
              memengaruhi hasil pada jam keputusan.
Lapis       : I (Inferensi).
Sumber      : Keluaran ModelPeluang (inference/peluang_gangguan.py) dan fitur jam keputusan.
Masukan     : Peluang (tidak, genangan, gerusan), vektor fitur terskala, fitur mentah.
Keluaran    : Porsi tiap mekanisme, mekanisme dominan, daftar bukti utama berurutan.
Keterbatasan: Kontribusi bukti dihitung dari koefisien MAP x nilai fitur (linear pada logit),
              bukan atribusi kausal.
"""

from __future__ import annotations

import numpy as np

from config import muat_params
from inference.fitur import NAMA_FITUR
from inference.peluang_gangguan import ModelPeluang

SATUAN_FITUR = {
    "hujan_lokal_1h": "mm", "hujan_lokal_3h": "mm", "hujan_lokal_5h": "mm", "hujan_hulu_3h": "mm",
    "prakiraan_lokal": "mm", "prakiraan_hulu": "mm", "glapan_relatif": "cm terhadap Awas",
    "glapan_tren": "cm per 6 jam",
}


def tentukan(peluang: np.ndarray) -> dict:
    """Porsi genangan/gerusan di antara peluang gangguan dan mekanisme dominan.

    Parameter:
        peluang: (tidak, genangan, gerusan).
    Kembali:
        dict peluang_genangan, peluang_gerusan, porsi_genangan, porsi_gerusan, dominan.
    """
    pg, ps = float(peluang[1]), float(peluang[2])
    total = pg + ps
    porsi_g = pg / total if total > 0 else 0.5
    return {
        "peluang_genangan": pg,
        "peluang_gerusan": ps,
        "porsi_genangan": porsi_g,
        "porsi_gerusan": 1 - porsi_g,
        "dominan": "genangan" if pg >= ps else "gerusan",
    }


def bukti_utama(model: ModelPeluang, x: np.ndarray, mentah: dict[str, float], peluang: np.ndarray,
                jumlah: int = 3) -> list[dict]:
    """Fitur dengan kontribusi terbesar pada logit gangguan (dibobot porsi mekanisme).

    Parameter:
        model: model terlatih.
        x: vektor fitur terskala.
        mentah: fitur dalam satuan asli.
        peluang: (tidak, genangan, gerusan).
        jumlah: banyaknya bukti yang dikembalikan.
    Kembali:
        Daftar dict {fitur, keterangan, nilai, satuan, kontribusi, arah}.
    """
    m = tentukan(peluang)
    k = model.kontribusi(x)
    total = m["porsi_genangan"] * k["genangan"] + m["porsi_gerusan"] * k["gerusan"]
    ket = muat_params().inferensi["fitur"]
    urut = np.argsort(-np.abs(total))[:jumlah]
    return [{
        "fitur": NAMA_FITUR[i],
        "keterangan": ket[NAMA_FITUR[i]]["keterangan"],
        "nilai": round(float(mentah[NAMA_FITUR[i]]), 2),
        "satuan": SATUAN_FITUR[NAMA_FITUR[i]],
        "kontribusi": round(float(total[i]), 3),
        "arah": "menaikkan" if total[i] >= 0 else "menurunkan",
    } for i in urut]
