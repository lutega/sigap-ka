# SIGAP-KA: Matriks Keterlacakan Kebutuhan

Setiap kebutuhan fungsional (FR) dan nonfungsional (NFR) spesifikasi dipetakan ke modul yang
mengimplementasikannya dan tes yang membuktikannya. Berkas tes ada di `tests/` (pytest) dan
`dashboard/src/__tests__/` (vitest).

## Kebutuhan fungsional

| Kebutuhan | Modul | Tes |
| --- | --- | --- |
| FR-S1 hujan lokal dan hulu | `sensing/hujan_nasa_power.py`, `hujan_gpm_imerg.py`, `hujan_gsmap.py`, `registri.py` | `test_sensing_sumber.py` (NASA POWER, IMERG, GSMaP), `test_sensing_dummy.py::test_rantai_cadangan_*` |
| FR-S2 muka air Glapan, prakiraan | `sensing/muka_air_glapan.py`, `muka_air_sintetis.py`, `muka_air_bbws.py`, `prakiraan_bmkg.py` | `test_sensing_sumber.py::test_glapan_*`, `test_bmkg_*`, `test_sensing_dummy.py::test_muka_air_sintetis_*` |
| FR-S3 katalog kejadian | `sensing/kejadian_manual.py`, `kejadian_ocr_llm.py`, tabel `kejadian` | `test_sensing_kejadian.py` |
| FR-S4 label `is_simulated`, sumber, riwayat | `sensing/standar.py`, `sensing/jalankan.py`, tabel `log_pengambilan` | `test_sensing_sumber.py::test_validasi_*`, `test_db_model.py::test_catat_pengambilan_*`, `test_sensing_dummy.py::test_cli_*` |
| FR-S5 dummy dari params preset | `sensing/dummy_generator.py` | `test_sensing_dummy.py::test_generator_dapat_diulang`, `test_laju_gangguan_*`, `test_semua_keluaran_dummy_*` |
| FR-I1 peluang gangguan per jam | `inference/peluang_gangguan.py`, `estimasi.py` | `test_inferensi.py::test_peluang_*`, `test_kinerja_*` |
| FR-I2 mekanisme genangan/gerusan | `inference/mekanisme.py` | `test_inferensi.py::test_mekanisme_*`, `test_kasus_mirip_e3_e6_*` |
| FR-I3 lama penutupan | `inference/lama_tutup.py` | `test_inferensi.py::test_lama_tutup_*` |
| FR-I4 pembaruan bukti (rolling horizon) | `inference/estimasi.py`, `perbarui_dengan_laporan`, `inference/fitur.py` | `test_inferensi.py::test_laporan_*`, `test_fitur_tanpa_intip_masa_depan` |
| FR-G1 parameter per tindakan | `config/params.json`, `config/pengaturan.py` | `test_pengaturan.py` |
| FR-G2 kurva pemicu DP, ambang (C+P)/(L+P) | `gating/kurva_pemicu.py`, `gating/cost_loss.py` | `test_gating.py::test_kurva_di_batas_*`, `test_dp_sama_dengan_integral_*`, `test_kurva_tinggi_*` |
| FR-G3 Putuskan sekarang / Tunggu / Terlambat | `gating/status.py` | `test_gating.py::test_status_*` |
| FR-G4 slider parameter | `POST /kurva/hitung`, `dashboard/src/tab/TabKurva.jsx` | `test_api.py::test_tindakan_dan_kurva`, `test_gating.py::test_slider_*` |
| FR-A1 papan tindakan | `action/papan_tindakan.py`, `dashboard/src/komponen/PapanTindakan.jsx` | `test_aksi.py::test_papan_*`, `konsol.test.jsx` |
| FR-A2 setujui/tolak | `action/log_keputusan.py`, `POST /episode/{id}/keputusan` | `test_aksi.py::test_log_*`, `test_api.py::test_papan_keputusan_*` |
| FR-A3 log dengan waktu | tabel `keputusan_operator` | `test_aksi.py::test_log_setujui_*`, `test_api.py` |
| FR-A4 biaya operator vs SIGAP di T−0 | `action/ringkasan.py`, `GET /episode/{id}/ringkasan` | `test_aksi.py::test_ringkasan_*`, `test_demo.py::test_alur_demo_*` |
| FR-A5 tidak pernah menyatakan jalur aman | `action/penjaga_klaim.py`, `api/deps.keluaran` | `test_aksi.py::test_penjaga_*`, `test_api.py::test_tidak_ada_respons_*`, `test_alur_menyeluruh.py`, `konsol.test.jsx` (teks antarmuka) |
| FR-P1 denda alarm palsu eksplisit | `config/params.json`, `gating/` | `test_gating.py::test_denda_alarm_palsu_menaikkan_ambang` |
| FR-P2 berbagi data antarinstansi | tidak diimplementasikan (dibahas kualitatif di laporan, sesuai spesifikasi) | - |
| FR-E1 enam kebijakan | `simulation/kebijakan.py` | `test_simulasi.py::test_kebijakan_*` |
| FR-E2 biaya per episode | `gating/cost_loss.biaya_rencana`, `simulation/evaluasi.biaya_episode` | `test_gating.py::test_biaya_aktual_fr_e2`, `test_simulasi.py::test_biaya_episode_fr_e2` |
| FR-E3 seed dapat diulang; konsol = model | `simulation/evaluasi.py`, `dashboard/export_dashboard.py` | `test_simulasi.py::test_simulasi_dapat_diulang`, `test_konsol.py::test_angka_konsol_*` |
| FR-E4 POD, FAR, CSI, lead time LOEO | `simulation/evaluasi.py` | `test_simulasi.py::test_metrik_*`, `test_loeo_dan_pembanding` |

## Kebutuhan nonfungsional dan bagian implementasi

| Kebutuhan | Modul | Tes |
| --- | --- | --- |
| NFR-1 human in the loop | papan hanya usulan; status "Sudah disetujui" hanya dari keputusan operator | `test_aksi.py::test_papan_status_*`, `test_log_*` |
| NFR-2 transparansi data | `is_simulated`, `Episode.label_seri`, `LabelData` | `test_sensing_*`, `test_api.py::test_daftar_dan_detail_*`, `konsol.test.jsx` |
| NFR-3 satu sumber parameter; konsol satu perintah | `config/params.json` (C, L, P tidak di DB), `dashboard/export_dashboard.py` | `test_db_model.py::test_tabel_tindakan_tanpa_parameter_biaya`, `test_konsol.py` |
| NFR-4 keterulangan | seed di generator, Monte Carlo, simulasi, skenario cadangan | `test_sensing_dummy.py`, `test_simulasi.py`, `test_demo.py::test_skenario_cadangan_*` |
| NFR-5 ketahanan data | `sensing/registri.py` (cadangan berlabel) | `test_sensing_dummy.py::test_rantai_cadangan_*`, `test_sensing_sumber.py::test_data_bersurat_*` |
| 12.4 pengecekan maladaptasi | `action/papan_tindakan.peringatan_maladaptasi` | `test_aksi.py::test_peringatan_maladaptasi_*` |
| 14.2 endpoint | `api/routers/*` | `test_api.py::test_openapi_memuat_endpoint_spesifikasi` |
| 14.5 database dan hypertable | `db/` | `test_db_model.py`, `test_db_timescale.py` |
| 15 login dan pengguna | `auth/`, `api/routers/auth.py`, `pengguna.py`, `KelolaPengguna.jsx` | `test_api.py` (auth), `konsol.test.jsx` |
| 16 mode demo | `simulation/demo.py`, `api/routers/demo.py`, `PanelDemo.jsx`, `simulation/skenario_cadangan.py` | `test_demo.py`, `konsol.test.jsx::panel mode demo` |
| Tanpa intip masa depan | `inference/fitur.py`, `db/repositori.ambil_prakiraan_tersedia`, potongan API | `test_inferensi.py::test_fitur_tanpa_intip_*`, `test_db_model.py::test_prakiraan_hanya_*`, `test_api.py::test_daftar_dan_detail_*`, `test_demo.py` |

## Tambahan 22 Nov 2026 · evaluasi pada data nyata

| Kebutuhan | Modul | Tes |
| --- | --- | --- |
| Kejadian kandidat dari sumber publik (pendukung FR-S3) | `data/manual/kejadian_kandidat.csv`, `src/sigap_ka/inputs/kejadian_kandidat.py` | `test_kejadian_kandidat.py` |
| Hujan IMERG Late per jam dan rerata DAS (pendukung FR-S1) | `sensing/hujan_gpm_imerg.py` (`late_jam`), `sensing/hujan_imerg_das.py` | `test_sensing_sumber.py::test_imerg_setengah_jam_*`, `test_imerg_das_*` |
| Episode nyata T−0 sembarang, prakiraan persistensi, muka air tertunda (tanpa intip masa depan) | `simulation/episode.bangun_episode_hujan_nyata`, `prakiraan_persistensi` | `test_uji_balik.py::test_prakiraan_persistensi_*`, `test_muka_air_tertunda_*`, `test_akumulasi_tidak_bergantung_menit_t0` |
| Uji balik, kepekaan bias, AUC dengan selang (pendukung FR-E4) | `simulation/uji_balik.py`, `simulation/realisme_generator.py` | `test_uji_balik.py`, `test_realisme_generator.py` |
| Tampilan evaluasi nyata (pendukung FR-A, NFR-2 label) | `simulation/ringkasan_nyata.py`, `GET /data/evaluasi-nyata`, `EvaluasiNyata.jsx` | `test_api.py::test_evaluasi_nyata_*`, `konsol.test.jsx::evaluasi data nyata` |
| Pemuatan ulang sumber manual tanpa baris basi | `sensing/standar.simpan_olahan(ganti=True)`, `db/repositori.hapus_muka_air_umum`, `hapus_seri_episode` | `test_sensing_sumber.py::test_simpan_olahan_ganti_*`, `test_db_model.py::test_hapus_*`, `test_simulasi.py::test_episode_dibangun_ulang_*` |
