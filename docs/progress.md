# SIGAP-KA: Progres dan Laporan Serah Terima

Format tiap tahap: yang dikerjakan; berkas yang berubah; data yang masih dummy; asumsi baru;
hambatan; keputusan yang perlu diambil manusia; hasil tes.

---

## Tahap 0 · Kerangka repo (selesai 21 Nov 2026)

**Yang dikerjakan**
- Mengganti nama `docs/arsitekur.md` menjadi `docs/arsitektur.md` sesuai CLAUDE.md.
- Lingkungan Python 3.12 (`.venv`), `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` (konfigurasi pytest, marker `db`).
- `docker-compose.yml` TimescaleDB 2.17.2 / PostgreSQL 16 dengan healthcheck; `db/init/01_init.sql` mengaktifkan ekstensi dan membuat database uji `sigap_test`.
- `.env.example` ditulis ulang tanpa BOM, ditambah variabel database, JWT, CORS, kredensial opsional (Earthdata, JAXA, Claude API, Tesseract). BOM di `.env` lokal dibuang tanpa mengubah isinya.
- `config/params.json`: T1–T9 dengan preset low/base/high, lokasi, episode, lama tutup, gating, inferensi (prior), muka air, generator dummy, jadwal dummy, simulasi, daftar sumber data, demo; blok `_nyata` untuk angka dari dokumen.
- `config/pengaturan.py`: pembaca `.env` (tahan BOM) dan params.json dengan validasi Pydantic.
- `README.md` awal, `docs/asumsi.md` (A-001 s.d. A-015), `.gitattributes`, `.gitignore`.

**Berkas berubah:** `config/*`, `db/init/01_init.sql`, `docker-compose.yml`, `.env.example`, `.gitignore`, `.gitattributes`, `pyproject.toml`, `requirements*.txt`, `tests/conftest.py`, `tests/test_pengaturan.py`, paket kosong lapis, `README.md`, `docs/*`.

**Data masih dummy:** seluruh parameter kecuali blok `_nyata` (Glapan 1970, ambang Awas 1905, sintetis lama 1768, refund Rp3,5 miliar/124 perjalanan).

**Asumsi baru:** A-001 s.d. A-015.

**Hambatan:** tidak ada.

**Keputusan manusia:** nama dan batas waktu T6–T8; verifikasi koordinat dan kode wilayah BMKG.

**Hasil tes:** `pytest` → 19 lulus. `docker compose up -d` → kontainer `sigap-db` healthy; ekstensi `timescaledb` 2.17.2 aktif di `sigap` dan `sigap_test`.

---

## Tahap 1 · db/ (selesai 21 Nov 2026)

**Yang dikerjakan**
- `db/model.py`: 10 tabel spesifikasi 14.5 ditambah `pengguna`, `episode`, `laporan_lapangan`, `simulasi_run`, `sesi_demo`. Hypertable memakai kunci primer gabungan yang memuat kolom waktu; kolom `episode_id` ('' = observasi umum) memisahkan data episode sintetis dari observasi nyata.
- `db/inisialisasi.py` (`python -m db.inisialisasi`): tabel, 3 hypertable (`obs_hujan`, `prakiraan_hujan`, `obs_muka_air`), continuous aggregate `hujan_harian` (real-time aggregation aktif), view `hujan_akumulasi` 1/3/5 hari, isi awal `sumber_data` dan `tindakan` dari params.json. Idempoten; pada SQLite hanya membuat tabel.
- `db/repositori.py`: upsert tabel standar (PostgreSQL dan SQLite), ambil seri hujan/muka air, ambil prakiraan yang sudah terbit pada jam keputusan, catatan asal data, kejadian, jadwal, episode, laporan lapangan.
- `db/koneksi.py`: engine dan sesi; URL `postgresql://` otomatis memakai driver psycopg 3.

**Berkas berubah:** `db/*`, `tests/conftest.py`, `tests/test_db_model.py`, `tests/test_db_timescale.py`, `README.md`.

**Data masih dummy:** tidak ada data baru.

**Asumsi baru:** A-016 (kolom `episode_id` dan tabel tambahan di luar 14.5).

**Hambatan:** latensi Docker Desktop di Windows cukup tinggi (sekitar 0,3 detik per perintah SQL); penyisipan massal dibuat per potongan 500 baris.

**Keputusan manusia:** tidak ada.

**Hasil tes:** `pytest` → 38 lulus (termasuk 6 tes integrasi TimescaleDB bertanda `db`).

---

## Tahap 2 · sensing/ (selesai 21 Nov 2026)

**Yang dikerjakan**
- Kontrak bersama `sensing/standar.py`: kolom standar, validasi (termasuk prakiraan tidak boleh berlaku sebelum terbit), penanda kualitas (baik/kosong/janggal, batas dari params.json), penyimpanan raw/processed.
- 12 modul sumber dengan pola `ambil() -> ke_format_standar() -> cek_kualitas()`: `hujan_nasa_power`, `hujan_gpm_imerg`, `hujan_gsmap`, `prakiraan_bmkg` (+ peringatan dini RSS), `hujan_bmkg_stasiun` dan `muka_air_bbws` (bersurat, opsional), `muka_air_glapan`, `muka_air_sintetis` (waduk linear), `kejadian_manual`, `kejadian_ocr_llm` (OCR Tesseract -> Claude API structured outputs -> kode periksa K1-K3 -> presisi/recall), `jadwal_ka`, `dummy_generator`.
- `sensing/registri.py`: rantai cadangan hujan hulu (IMERG -> GSMaP -> NASA POWER -> dummy berlabel), pemilih metode katalog, status kesiapan sumber.
- `sensing/jalankan.py`: CLI `nasa_power`, `bmkg`, `manual`, `muat`, `status`; log asal data di `data/processed/log_pengambilan.csv`.
- **Data nyata yang berhasil diambil:** NASA POWER harian 1 Jan 2024 s.d. 20 Nov 2026 untuk titik lokal, hulu, Gundih (1055 hari, 2 hari terakhir belum tersedia); prakiraan BMKG terkini untuk Desa Penadaran, Kec. Gubug (kode wilayah ditemukan dengan menelusuri respons API karena kode awal 404). Keduanya dimuat ke TimescaleDB; view akumulasi 1/3/5 hari bekerja pada data nyata.
- Generator dummy disetel: laju gangguan low 13%, base 28%, high 44%; sekitar 30% gerusan; ada kasus gangguan dengan hujan lokal rendah (pola E3/E6).

**Berkas berubah:** `sensing/*`, `data/manual/*.csv`, `data/processed/*.csv`, `config/params.json` (blok kualitas, prakiraan dummy, kode BMKG), `config/pengaturan.py` (model LLM bawaan), `db/koneksi.py` (batas waktu koneksi), `db/inisialisasi.py` (upsert massal), `tests/test_sensing_*.py`, `README.md`.

**Data masih dummy:** episode sintetis, muka air sintetis, jadwal KA (placeholder KA-A s.d. KA-F), katalog E1-E6 (kerangka tanpa jam/mekanisme). Nyata: hujan NASA POWER, prakiraan BMKG terkini, satu titik Glapan.

**Asumsi baru:** A-017 s.d. A-024. Temuan penting A-017: titik lokal, hulu, dan Gundih jatuh di sel grid NASA POWER yang sama (nilai identik), sehingga bukti hulu nyata butuh IMERG/GSMaP/BBWS.

**Hambatan:** latensi penerusan port Docker Desktop sekitar 0,3 detik per perintah SQL (lonjakan sampai 4,8 detik; di dalam kontainer 0 detik). Tes database butuh sekitar 1 menit. Ditangani dengan upsert massal dan batas waktu koneksi 10 detik.

**Keputusan manusia:** akun Earthdata/JAXA bila ingin hujan hulu satelit; pengisian katalog E1-E6 dan jadwal KA nyata; uji metode OCR+LLM butuh ANTHROPIC_API_KEY dan Tesseract.

**Hasil tes:** `pytest` -> 77 lulus (71 unit + 6 integrasi TimescaleDB).

---

## Tahap 3 · inference/ (selesai 21 Nov 2026)

**Yang dikerjakan**
- `inference/fitur.py`: `IndeksEpisode` menghitung 8 fitur spesifikasi 9.1 pada jam keputusan dengan larik numpy, menghormati latensi tiap sumber dan waktu terbit prakiraan (tanpa intip masa depan).
- `inference/peluang_gangguan.py`: logistik multinomial Bayesian dua mekanisme (kelas tidak/genangan/gerusan, saling lepas sehingga p_total = p_genangan + p_gerusan), prior dari params.json per preset, MAP Newton + Laplace, prediktif Monte Carlo berseed; pembaruan rasio kemungkinan untuk laporan air di badan rel.
- `inference/mekanisme.py` (mekanisme dominan, bukti utama), `inference/lama_tutup.py` (skenario pendek/sedang/panjang, harapan jam, faktor L efektif untuk lapis G), `inference/estimasi.py` (`Estimator`, data latih, model bawaan per preset).
- Generator dummy diperbaiki: prakiraan tiap terbitan mencakup sampai T−0 + 6 jam (sebelumnya hanya 24 jam, sehingga prakiraan awal tidak melihat badai).
- Kinerja pada episode sintetis uji: AUC 0,68 (T−72) → 0,84 (T−24) → 0,95 (T−0); kalibrasi baik (mis. kelompok p 0,59 teramati 0,65; p 0,89 teramati 0,86).

**Berkas berubah:** `inference/*`, `sensing/dummy_generator.py`, `sensing/standar.py`, `sensing/jalankan.py`, `sensing/kejadian_ocr_llm.py` (akhir baris CSV), `config/params.json` (cakupan dan skala prakiraan), `tests/test_inferensi.py`.

**Data masih dummy:** prior, rasio kemungkinan laporan, model dilatih pada episode sintetis.

**Asumsi baru:** A-025 s.d. A-027; A-021 diperbarui.

**Hambatan:** tidak ada.

**Keputusan manusia:** konfirmasi pilihan model (pertanyaan terbuka spesifikasi 7); prior dari ahli bila tersedia.

**Hasil tes:** `pytest` → 94 lulus.

---

## Tahap 4 · gating/ (selesai 21 Nov 2026)

**Yang dikerjakan**
- `gating/cost_loss.py`: ambang (C + P) / (L + P), biaya harapan, L efektif, biaya aktual FR-E2, diskon biaya awal.
- `gating/kurva_pemicu.py`: pemrograman dinamis mundur pada grid peluang 201 titik dengan matriks transisi Beta martingale (bias rerata 0,0001); ambang tepat (C + P) / (L + P) di batas waktu; `kurva_untuk_tindakan` dengan parameter pengganti untuk slider (FR-G4) tanpa mengubah params.json; cache ambang.
- `gating/status.py`: Putuskan sekarang / Tunggu prakiraan berikutnya / Terlambat / Sudah disetujui.
- Pola preset base (dummy): kurva T1 turun ke 0,5 paling awal (T−48), lalu ke 0,094 di T−36; T9 tidak pernah di bawah 0,73; tindakan lain turun dari sekitar 0,8–0,9 ke ambang statisnya.

**Berkas berubah:** `gating/*`, `tests/test_gating.py`.

**Data masih dummy:** k = 12, diskon 2%, seluruh C, L, P, waktu siap.

**Asumsi baru:** A-028, A-029.

**Hambatan:** tidak ada.

**Keputusan manusia:** tidak ada.

**Hasil tes:** `pytest tests/test_gating.py` → 21 lulus (termasuk pembanding integral Beta kontinu dan uji resolusi grid).

---

## Tahap 5 · action/ (selesai 21 Nov 2026)

**Yang dikerjakan**
- `action/papan_tindakan.py`: papan 9 tindakan per jam keputusan (status, peluang, ambang kurva, selisih, sisa jam, alasan singkat dengan bukti utama, peringatan maladaptasi Gundih dan jalan putus, label parameter dummy, catatan kewenangan KAI).
- `action/log_keputusan.py`: catat Setujui/Tolak/Batalkan dengan waktu, status SIGAP, peluang, nilai kurva, username, mode normal/demo; validasi; tindakan berlaku disetujui tanpa intip keputusan masa depan; hapus log demo per sesi.
- `action/ringkasan.py`: biaya keputusan operator vs saran SIGAP di T−0, label terlalu awal/terlambat/sia-sia/tepat; dua kemungkinan hasil bila episode belum terkonfirmasi.
- `action/penjaga_klaim.py`: menolak kata utuh "aman"/"safe" di seluruh keluaran (FR-A5).
- `gating/status.langkah_putuskan` dan `gating/cost_loss.biaya_rencana`: satu logika SIGAP dan satu rumus biaya untuk papan, ringkasan, dan simulasi.

**Berkas berubah:** `action/*`, `gating/status.py`, `gating/cost_loss.py`, `inference/fitur.py` (hujan Gundih), `config/params.json` (blok maladaptasi), `tests/test_aksi.py`.

**Data masih dummy:** ambang hujan Gundih, seluruh biaya.

**Asumsi baru:** A-030 s.d. A-033.

**Hambatan:** tidak ada.

**Keputusan manusia:** konfirmasi definisi label ringkasan (A-032).

**Hasil tes:** `pytest` → 135 lulus.

---

## Tahap 6 · simulation/ (selesai 21 Nov 2026)

**Yang dikerjakan**
- `simulation/episode.py`: struktur `Episode` (label nyata/dummy per seri), episode sintetis, skenario cadangan presentasi (seed tetap), episode nyata 24 Jan 2025, simpan/muat database, CLI `python -m simulation.episode muat`.
- `simulation/kebijakan.py`: enam kebijakan dengan informasi setara.
- `simulation/evaluasi.py`: biaya per episode (FR-E2), simulasi N episode, ringkasan dengan selisih berpasangan dan galat baku, sensitivitas biaya menunggu, POD/FAR/CSI/lead time leave-one-episode-out, pembanding aturan hujan lokal dan indeks adaptasi H-MHEWS.
- `simulation/jalankan.py`: CLI simulasi; hasil ke `data/processed/simulasi/` dan tabel `hasil_simulasi`/`simulasi_run`.
- Konsentrasi Beta lapis G dikalibrasi dari lintasan peluang lapis I (12 → 7).

**Hasil (300 episode sintetis, seed 42, parameter dummy; rerata biaya, juta rupiah)**

| Kebijakan | low | base | high |
| --- | --- | --- | --- |
| SIGAP | 254 | 644 | 1257 |
| Jam tetap 24 jam | 273 | 655 | 1340 |
| Ambang tetap 0,5 | 280 | 719 | 1423 |
| Cost-loss di batas | 259 | 644 | 1299 |
| Reaktif | 313 | 972 | 2525 |
| Informasi sempurna | 105 | 312 | 703 |
| SIGAP vs pembanding terbaik | −1,9% | −0,01% | −3,3% |

Metrik deteksi LOEO (100 episode, base): SIGAP POD 0,84 FAR 0,46 CSI 0,49; aturan hujan lokal CSI 0,43; indeks H-MHEWS CSI 0,36.

**Temuan yang perlu dibaca tim**
1. Keunggulan SIGAP atas cost-loss di batas waktu kecil (0–3%), jauh di bawah angka 14% deck lama. Keunggulan hampir seluruhnya bergantung pada biaya menunggu (diskon biaya awal): base 0% (diskon 0), 0% (2%), −7% (5%), −2% (10%). Pada diskon 10%, ambang tetap 0,5 bisa lebih murah dari SIGAP (low +0,9%, high +4,7%) karena asumsi martingale DP tidak persis sama dengan lintasan peluang sebenarnya. Biaya keterlambatan tiap tindakan perlu digali dari praktisi KAI.
2. Episode nyata 24 Jan 2025: dengan hujan NASA POWER (lokal = hulu, sel grid sama; hujan harian 24 Jan hanya 5,9 mm), peluang model tetap 0,09–0,16 dan muka air sintetis mencapai 1734, sedangkan nyata 1970 (Awas 1905). Model sintetis baru meleset lebih jauh daripada model lama (1768). Ini menegaskan batas klaim: bukti hulu butuh IMERG/GSMaP/BBWS.

**Berkas berubah:** `simulation/*`, `inference/estimasi.py` (lintasan), `inference/fitur.py`, `sensing/dummy_generator.py` (prakiraan dapat dipakai ulang), `config/params.json` (k = 7), `data/processed/simulasi/*`, `tests/test_simulasi.py`, `README.md`.

**Data masih dummy:** seluruh biaya, generator, prakiraan dan muka air episode nyata.

**Asumsi baru:** A-034 s.d. A-037.

**Hambatan:** tidak ada.

**Keputusan manusia:** biaya keterlambatan tiap tindakan (penentu utama nilai SIGAP); akses IMERG/BBWS untuk bukti hulu; konfirmasi definisi kebijakan (A-035).

**Hasil tes:** `pytest` → 150 lulus.

---

## Tahap 7 · api/ + auth/ (selesai 21 Nov 2026)

**Yang dikerjakan**
- `auth/`: hash bcrypt, token JWT, layanan pengguna (akun awal admin dari .env bila tabel kosong, tambah, nonaktifkan, ubah level, atur ulang password, penjaga admin aktif terakhir), dependensi `pengguna_aktif` dan `wajib_admin`.
- `api/`: `main.py` (lifespan: skema + akun awal, CORS, penahan klaim, `/kesehatan`, penyaji dashboard), `deps.py` (konteks, cache episode dan estimator, pembersih JSON + penjaga klaim, validasi jam), `schemas.py`, router `auth`, `pengguna`, `data`, `prediksi` (episode, detail terpotong, prediksi, lintasan), `kurva` (tindakan, kurva, hitung ulang slider), `tindakan` (papan, keputusan, log, ringkasan), `simulasi` (tugas latar belakang).
- Uji asap server nyata (uvicorn port 8765) terhadap TimescaleDB: login admin, daftar 7 episode, papan episode nyata dan cadangan, status sumber.

**Berkas berubah:** `api/*`, `auth/*`, `tests/test_api.py`, `README.md`, `.env.example` (API_PORT).

**Data masih dummy:** sama dengan tahap sebelumnya.

**Asumsi baru:** A-038 s.d. A-040.

**Hambatan:** port 8000 terpakai proses lain di mesin ini; API memakai port 8765.

**Keputusan manusia:** konfirmasi pembagian hak operator/admin (A-039).

**Hasil tes:** `pytest tests/test_api.py` → 27 lulus (seluruh endpoint 14.2, 401/403, bcrypt, keputusan dengan username, simulasi latar, tanpa klaim jalur aman).

---

## Tahap 8 · dashboard/ (selesai 21 Nov 2026)

**Yang dikerjakan**
- Konsol React 18 + Vite 5 + Recharts 2: halaman login, lima tab (Operasi, Data, Prediksi, Kurva pemicu, Simulasi), Kelola pengguna khusus admin, tema terang/gelap (pilihan pengguna atau sistem), catatan kewenangan KAI dan batas klaim di kaki halaman.
- Tab Operasi: pilih episode, langkah/putar ulang per jam keputusan (2/4/8 detik per 6 jam episode), angka utama (peluang, mekanisme, lama tutup), grafik peluang vs kurva pemicu tindakan terpilih dengan garis batas waktu dan "sekarang", bukti utama, papan 9 tindakan (Setujui/Tolak dengan alasan/Batalkan, peringatan maladaptasi), ringkasan biaya T−0.
- Setiap grafik punya tampilan tabel; label nyata/dummy; satu sumbu per grafik; palet tervalidasi.
- Endpoint baru `/info` (empat batas klaim; nilai muka air sintetis 24 Jan dihitung model, bukan ditulis tangan).
- `dashboard/export_dashboard.py`: satu perintah build + cek kesesuaian angka API vs model untuk low/base/high: 75/75 sesuai.

**Berkas berubah:** `dashboard/*` (kecuali `node_modules`, `dist`), `api/routers/info.py`, `api/main.py`, `tests/test_konsol.py`, `README.md`.

**Data masih dummy:** sama; konsol menandainya.

**Asumsi baru:** A-041, A-042.

**Hambatan:** tidak ada alat peramban di sesi ini, jadi tampilan konsol belum diperiksa secara visual oleh agen (hanya build, vitest, dan uji API). Mohon dicek sekali di peramban.

**Keputusan manusia:** tidak ada.

**Hasil tes:** `npm test` → 6 lulus; `npm run build` sukses; `pytest tests/test_konsol.py` → 3 lulus; `export_dashboard.py` → 75/75 angka konsol = model.
