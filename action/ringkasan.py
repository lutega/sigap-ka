"""
Tujuan      : Ringkasan akhir episode (T-0): biaya keputusan operator dibandingkan biaya bila saran
              SIGAP diikuti, beserta tindakan yang terlalu awal, terlambat, sia-sia, atau tepat
              (FR-A4, spesifikasi 12.3).
Lapis       : A (Aksi).
Sumber      : Log keputusan operator, peluang lapis I per jam keputusan, kurva pemicu lapis G,
              hasil episode (kebenaran sintetis atau katalog kejadian).
Masukan     : Episode, estimator, log keputusan.
Keluaran    : dict ringkasan per tindakan dan total; bila hasil episode belum terkonfirmasi,
              ringkasan dihitung untuk dua kemungkinan (terganggu / tidak terganggu).
Keterbatasan: Biaya memakai parameter dummy; tindakan dianggap mencegah seluruh L bila dijalankan
              sebelum batas waktunya. Untuk hasil belum terkonfirmasi, L memakai skenario sedang.
"""

from __future__ import annotations

from config import ParamsAktif, muat_params
from action.log_keputusan import tindakan_disetujui
from action.penjaga_klaim import pastikan_tanpa_klaim_aman
from gating.cost_loss import biaya_rencana
from gating.status import langkah_putuskan
from inference.estimasi import Estimator


def langkah_operator(log: list[dict], params: ParamsAktif) -> dict[str, int]:
    """Langkah keputusan saat tiap tindakan disetujui operator (persetujuan yang berlaku di T-0)."""
    ep = params.episode
    return {tid: ep.langkah_dari_jam(jam) for tid, jam in tindakan_disetujui(log, 0).items()}


def klasifikasi(langkah: int | None, langkah_sigap: int | None, batas: int, terganggu: bool) -> str:
    """Label keputusan satu tindakan.

    - sia-sia: dijalankan tetapi gangguan tidak terjadi;
    - terlambat: gangguan terjadi tetapi tindakan tidak dijalankan sampai batas waktu;
    - terlalu awal: dijalankan (gangguan terjadi) lebih awal daripada saat SIGAP menyarankannya;
    - tepat: selain itu (termasuk bertindak saat SIGAP tidak menyarankan dan gangguan terjadi).
    """
    bertindak = langkah is not None and langkah <= batas
    if bertindak and not terganggu:
        return "sia-sia"
    if not bertindak and terganggu:
        return "terlambat"
    if bertindak and langkah_sigap is not None and langkah < langkah_sigap:
        return "terlalu awal"
    return "tepat"


def _hitung(params: ParamsAktif, rencana_op: dict[str, int], rencana_sigap: dict[str, int | None],
            terganggu: bool, faktor_L_aktual: float) -> dict:
    """Biaya dan label per tindakan untuk satu kemungkinan hasil."""
    ep, diskon = params.episode, params.gating.diskon_biaya_awal_per_langkah
    baris, total_op, total_sg = [], 0.0, 0.0
    for t in params.daftar_tindakan():
        batas = ep.langkah_dari_jam(t.param.waktu_siap_jam)
        L = t.param.L * faktor_L_aktual
        k_op, k_sg = rencana_op.get(t.id), rencana_sigap.get(t.id)
        b_op = biaya_rencana(t.param.C, L, t.param.P, k_op, batas, terganggu, diskon)
        b_sg = biaya_rencana(t.param.C, L, t.param.P, k_sg, batas, terganggu, diskon)
        total_op += b_op
        total_sg += b_sg
        baris.append({
            "tindakan": t.id, "nama": t.nama,
            "operator": {"jam_sebelum_t0": None if k_op is None else ep.jam_sebelum_t0(k_op),
                         "biaya": round(b_op, 2), "label": klasifikasi(k_op, k_sg, batas, terganggu)},
            "sigap": {"jam_sebelum_t0": None if k_sg is None else ep.jam_sebelum_t0(k_sg),
                      "biaya": round(b_sg, 2), "label": klasifikasi(k_sg, k_sg, batas, terganggu)},
        })
    return {"terganggu": terganggu, "faktor_L": faktor_L_aktual, "tindakan": baris,
            "total_operator": round(total_op, 2), "total_sigap": round(total_sg, 2),
            "selisih_operator_minus_sigap": round(total_op - total_sg, 2)}


def ringkasan_episode(episode, estimator: Estimator | None = None, log: list[dict] | None = None,
                      params: ParamsAktif | None = None) -> dict:
    """Ringkasan T-0 untuk episode.

    Hasil episode diambil dari episode.kebenaran (sintetis) bila status hasil diketahui; bila
    belum terkonfirmasi (episode nyata tanpa katalog), dihitung untuk dua kemungkinan.
    """
    params = params or muat_params()
    estimator = estimator or Estimator(params=params)
    ep = params.episode
    hasil_inf = estimator.estimasi_episode(episode)
    peluang = [h.peluang for h in hasil_inf]
    faktor = [h.lama_tutup["faktor_L"] for h in hasil_inf]
    rencana_sigap = {t.id: langkah_putuskan(t, peluang, faktor, params) for t in params.daftar_tindakan()}
    rencana_op = langkah_operator(log or [], params)
    kebenaran = getattr(episode, "kebenaran", None) or {}
    skenario = []
    if kebenaran.get("terganggu") is not None:
        f = 1.0
        if kebenaran.get("terganggu") and kebenaran.get("skenario_lama_tutup"):
            f = params.lama_tutup.skenario[kebenaran["skenario_lama_tutup"]].faktor_L
        skenario.append(_hitung(params, rencana_op, rencana_sigap, bool(kebenaran["terganggu"]), f))
        status_hasil = "diketahui"
    else:
        skenario.append(_hitung(params, rencana_op, rencana_sigap, True, 1.0))
        skenario.append(_hitung(params, rencana_op, rencana_sigap, False, 1.0))
        status_hasil = "belum terkonfirmasi"
    return pastikan_tanpa_klaim_aman({
        "episode_id": getattr(episode, "id", None),
        "status_hasil": status_hasil,
        "mekanisme_teramati": kebenaran.get("mekanisme"),
        "peluang_per_jam": [{"jam_sebelum_t0": ep.jam_sebelum_t0(k), "peluang": round(p, 4)}
                            for k, p in enumerate(peluang)],
        "skenario": skenario,
        "catatan": ["Biaya memakai parameter dummy (juta rupiah); bukan biaya nyata KAI."],
    })
