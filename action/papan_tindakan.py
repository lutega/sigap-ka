"""
Tujuan      : Menyusun papan 9 tindakan untuk operator pada jam keputusan: status SIGAP per
              tindakan, peluang, nilai kurva, selisih, sisa waktu, alasan singkat, dan peringatan
              maladaptasi (spesifikasi 12.1 dan 12.4).
Lapis       : A (Aksi).
Sumber      : Lapis I (inference/estimasi.py), lapis G (gating/status.py), log keputusan operator.
Masukan     : Episode, jam keputusan (jam sebelum T-0), estimator, log keputusan.
Keluaran    : dict papan siap kirim ke API/dashboard (sudah diperiksa penjaga klaim).
Keterbatasan: Papan hanya usulan; human in the loop (NFR-1). Status jalur tetap ditetapkan KAI.
"""

from __future__ import annotations

from config import ParamsAktif, muat_params
from action.log_keputusan import tindakan_disetujui
from action.penjaga_klaim import pastikan_tanpa_klaim_aman
from gating.status import DISETUJUI, PUTUSKAN, TERLAMBAT, TUNGGU, tentukan_status
from inference.estimasi import Estimator, HasilInferensi

CATATAN_KEWENANGAN = [
    "Usulan SIGAP-KA bersifat saran; setiap tindakan diputuskan operator.",
    "Status jalur ditetapkan pihak berwenang KAI berdasarkan pemeriksaan lapangan.",
]


def _persen(x: float) -> str:
    """Format peluang sebagai persen bulat."""
    return f"{100 * x:.0f}%"


def alasan_singkat(status: str, peluang: float, ambang: float | None, waktu_siap: int,
                   jam_disetujui: int | None, inferensi: HasilInferensi) -> str:
    """Alasan singkat usulan: bukti utama dan selisih peluang terhadap kurva (spesifikasi 12.1)."""
    if status == DISETUJUI:
        return f"Disetujui operator pada T-{jam_disetujui}; tidak dihitung ulang kecuali dibatalkan."
    if status == TERLAMBAT:
        return f"Batas waktu siap (T-{waktu_siap}) sudah lewat tanpa tindakan; dicatat sebagai kerugian potensial."
    arah = "di atas" if status == PUTUSKAN else "di bawah"
    teks = f"Peluang {_persen(peluang)} {arah} kurva pemicu {_persen(ambang)} (selisih {100 * (peluang - ambang):+.0f} poin)."
    if inferensi.bukti:
        b = inferensi.bukti[0]
        teks += f" Bukti utama: {b['keterangan']} = {b['nilai']} {b['satuan']}."
    return teks


def peringatan_maladaptasi(tindakan_id: str, indeks, t_rel: float, params: ParamsAktif) -> list[str]:
    """Peringatan maladaptasi 12.4 untuk tindakan memutar (T3) dan bus pengganti (T4)."""
    hasil = []
    if tindakan_id == "T3":
        ambang = params.mentah["maladaptasi"]["ambang_hujan_gundih_24j_mm"]
        hujan = indeks.hujan_24j("gundih", t_rel)
        if hujan >= ambang:
            hasil.append(f"Rute alternatif via Gundih juga diguyur hujan {hujan:.0f} mm/24 jam; "
                         "periksa kondisi lintas alternatif sebelum memutar.")
    if tindakan_id == "T4" and indeks.ada_laporan_jalan_putus(t_rel):
        hasil.append("Jalan Semarang-Purwodadi dilaporkan terputus; bus pengganti mungkin tidak dapat lewat.")
    return hasil


def susun_papan(episode, jam_sebelum_t0: int, estimator: Estimator | None = None,
                log: list[dict] | None = None, params: ParamsAktif | None = None) -> dict:
    """Papan tindakan lengkap pada satu jam keputusan.

    Parameter:
        episode: objek episode (atribut id, t0, hujan, prakiraan, muka_air, laporan).
        jam_sebelum_t0: jam keputusan (mis. 24 = T-24).
        estimator: estimator lapis I; bawaan model preset aktif.
        log: keputusan operator episode ini (dari action.log_keputusan.daftar).
    Kembali:
        dict {episode_id, jam_sebelum_t0, waktu, inferensi, tindakan[9], catatan, ringkas_status}.
    """
    params = params or muat_params()
    estimator = estimator or Estimator(params=params)
    inferensi = estimator.estimasi(episode, jam_sebelum_t0)
    indeks = estimator._indeks(episode)
    aktif = tindakan_disetujui(log or [], jam_sebelum_t0)
    faktor = inferensi.lama_tutup["faktor_L"]
    baris = []
    for t in params.daftar_tindakan():
        st = tentukan_status(t, inferensi.peluang, jam_sebelum_t0, params, faktor, disetujui=t.id in aktif)
        peringatan = peringatan_maladaptasi(t.id, indeks, -float(jam_sebelum_t0), params) \
            if st.status in (PUTUSKAN, TUNGGU) else []
        baris.append({
            **st.ke_dict(),
            "nama": t.nama,
            "keputusan_sebelum": t.keputusan_sebelum,
            "terkonfirmasi": t.terkonfirmasi,
            "label_parameter": t.status,
            "jam_disetujui": aktif.get(t.id),
            "alasan": alasan_singkat(st.status, inferensi.peluang, st.ambang, t.param.waktu_siap_jam,
                                     aktif.get(t.id), inferensi),
            "peringatan": peringatan,
        })
    ringkas = {s: sum(1 for b in baris if b["status"] == s) for s in (PUTUSKAN, TUNGGU, TERLAMBAT, DISETUJUI)}
    papan = {
        "episode_id": getattr(episode, "id", None),
        "jam_sebelum_t0": int(jam_sebelum_t0),
        "waktu": inferensi.waktu,
        "preset": params.preset,
        "inferensi": inferensi.ke_dict(),
        "tindakan": baris,
        "ringkas_status": ringkas,
        "catatan": CATATAN_KEWENANGAN + inferensi.catatan,
    }
    return pastikan_tanpa_klaim_aman(papan)
