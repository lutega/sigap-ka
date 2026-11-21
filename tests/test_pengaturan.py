"""
Tujuan      : Menguji pembaca .env dan params.json (tahap 0).
Lapis       : QA, lintas lapis.
Sumber      : config/params.json.
Masukan     : -
Keluaran    : -
Keterbatasan: Menguji struktur dan konsistensi, bukan kebenaran nilai dummy.
"""

import json

import pytest

from config import ID_TINDAKAN, Pengaturan, muat_params_mentah, selesaikan_preset


def test_tindakan_lengkap_t1_sampai_t9(params_semua_preset):
    """Setiap preset memuat T1-T9 lengkap."""
    assert list(params_semua_preset.tindakan) == list(ID_TINDAKAN)


def test_ambang_statis_di_antara_nol_dan_satu(params_semua_preset):
    """0 < (C + P) / (L + P) < 1 untuk tiap tindakan (FR-G2)."""
    for t in params_semua_preset.daftar_tindakan():
        assert 0 < t.param.ambang_statis < 1, t.id


def test_waktu_siap_kelipatan_interval(params_semua_preset):
    """Batas waktu siap jatuh tepat pada jam keputusan."""
    ep = params_semua_preset.episode
    for t in params_semua_preset.daftar_tindakan():
        assert t.param.waktu_siap_jam % ep.interval_keputusan_jam == 0
        assert t.param.waktu_siap_jam <= ep.horizon_jam


def test_nilai_dummy_bertanda_dummy():
    """Bagian parameter yang belum nyata wajib berstatus dummy (NFR-2)."""
    mentah = muat_params_mentah()
    for bagian in ["episode", "lama_tutup", "gating", "inferensi", "muka_air", "dummy",
                   "jadwal_dummy", "simulasi", "demo"]:
        assert mentah[bagian]["status"] == "dummy", bagian
    for tid in ID_TINDAKAN:
        assert mentah["tindakan"][tid]["status"] == "dummy", tid


def test_tindakan_placeholder_t6_t8_belum_terkonfirmasi(params_base):
    """T6-T8 belum disebut di deck sehingga harus berlabel belum dikonfirmasi."""
    for tid in ["T6", "T7", "T8"]:
        assert params_base.tindakan[tid].terkonfirmasi is False
    for tid in ["T1", "T2", "T3", "T4", "T5", "T9"]:
        assert params_base.tindakan[tid].terkonfirmasi is True


def test_angka_nyata_dari_dokumen_tidak_berubah():
    """Angka nyata yang dikutip spesifikasi tetap sama."""
    nyata = muat_params_mentah()["_nyata"]
    assert nyata["glapan_24jan2025"]["nilai"] == 1970
    assert nyata["glapan_ambang_awas"]["nilai"] == 1905
    assert nyata["glapan_model_sintetis_lama_24jan2025"]["nilai"] == 1768
    assert nyata["refund_pekalongan"]["nilai_juta"] == 3500
    assert nyata["refund_pekalongan"]["perjalanan_batal"] == 124


def test_ambang_t9_base_di_atas_tujuh_puluh_persen(params_base):
    """Pola spesifikasi 10.4: pembatalan butuh peluang di atas sekitar 70% (dummy)."""
    assert params_base.tindakan["T9"].param.ambang_statis > 0.7


def test_peluang_lama_tutup_berjumlah_satu(params_base):
    """Sebaran skenario lama tutup tiap mekanisme berjumlah 1."""
    for sebaran in params_base.lama_tutup.peluang_bersyarat.values():
        assert sum(sebaran.values()) == pytest.approx(1.0)


def test_preset_tidak_valid_ditolak():
    """Preset selain low/base/high ditolak."""
    with pytest.raises(ValueError):
        selesaikan_preset(muat_params_mentah(), "sedang")


def test_c_lebih_besar_dari_l_ditolak(tmp_path):
    """Validasi menolak tindakan dengan C >= L."""
    mentah = muat_params_mentah()
    mentah["tindakan"]["T1"]["base"]["C"] = 999
    with pytest.raises(ValueError):
        selesaikan_preset(mentah, "base")


def test_env_dengan_bom_terbaca(tmp_path, monkeypatch):
    """File .env ber-BOM (ditulis PowerShell) tetap terbaca dengan benar."""
    env = tmp_path / ".env"
    env.write_bytes("\ufeffPARAMS_PRESET=high\nSIM_SEED=7\n".encode("utf-8"))
    monkeypatch.delenv("PARAMS_PRESET", raising=False)
    monkeypatch.delenv("SIM_SEED", raising=False)
    peng = Pengaturan(_env_file=str(env))
    assert peng.params_preset == "high"
    assert peng.sim_seed == 7


def test_params_json_valid_tanpa_bom():
    """params.json adalah JSON valid UTF-8 tanpa BOM."""
    from config import AKAR_REPO
    raw = (AKAR_REPO / "config" / "params.json").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    json.loads(raw.decode("utf-8"))


def test_konversi_jam_dan_langkah(params_base):
    """Indeks langkah dan jam sebelum T-0 saling balik."""
    ep = params_base.episode
    assert ep.jumlah_langkah == ep.horizon_jam // ep.interval_keputusan_jam + 1
    for k in range(ep.jumlah_langkah):
        assert ep.langkah_dari_jam(ep.jam_sebelum_t0(k)) == k
