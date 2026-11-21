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

---

## Tahap 9 · Mode demo dan skenario cadangan (selesai 21 Nov 2026)

**Yang dikerjakan**
- `simulation/demo.py`: mesin status sesi demo (mulai di T−72, langkah per jam keputusan, jeda/lanjut, kecepatan, reset yang hanya menghapus log demo sesi itu).
- `api/routers/demo.py`: `POST /demo/mulai`, `POST /demo/{id}/langkah`, `POST /demo/{id}/jeda`, `GET /demo/{id}/status`, `POST /demo/{id}/reset` (admin), `POST /demo/{id}/kecepatan`. Status memuat papan, lintasan sampai jam berjalan, log demo, dan ringkasan di T−0. Keputusan demo hanya pada jam yang sedang diputar.
- Konsol: panel mode demo di tab Operasi (mulai, lompat, jeda/lanjutkan, kecepatan, reset untuk admin, keluar).
- `simulation/skenario_cadangan.py`: cuplikan deterministik skenario cadangan (seed 2025) dengan sidik SHA-256 di `data/processed/demo/skenario_cadangan.json`; `--periksa` membuktikan hasil sama.
- `docs/naskah-demo.md`: persiapan, alur demo, tabel status per jam (dari cuplikan), episode nyata, pertanyaan penguji, penanganan gangguan.

**Berkas berubah:** `simulation/demo.py`, `simulation/skenario_cadangan.py`, `api/routers/demo.py`, `dashboard/src/tab/PanelDemo.jsx`, `dashboard/src/__tests__/konsol.test.jsx`, `data/processed/demo/skenario_cadangan.json`, `tests/test_demo.py`, `docs/naskah-demo.md`, `README.md`.

**Data masih dummy:** skenario cadangan sintetis; episode nyata memakai prakiraan dan muka air sintetis.

**Asumsi baru:** A-043 s.d. A-045.

**Hambatan:** tidak ada. Catatan: pada skenario cadangan, peluang model turun menjelang T−0 walau gangguan terjadi; disajikan apa adanya sebagai bahan diskusi keterbatasan.

**Keputusan manusia:** tidak ada.

**Hasil tes:** `pytest tests/test_demo.py` → 7 lulus (alur lengkap offline, tanpa intip masa depan, reset terbatas, hak akses, episode nyata, keterulangan cuplikan); `npm test` → 7 lulus; build sukses.

---

## Tahap 10 · Uji menyeluruh, README, daftar asumsi (selesai 21 Nov 2026)

**Yang dikerjakan**
- `tests/test_alur_menyeluruh.py` (marker `db`): TimescaleDB uji → muat data olahan nyata → episode demo → API (data, prediksi, papan, keputusan) → demo sampai T−0 → reset; agregat akumulasi hujan nyata 24 Jan 2025 (1 hari 5,92 mm).
- **Akar masalah tes yang menggantung ditemukan** (py-spy): ping pool SQLAlchemy menunggu tanpa batas pada koneksi "setengah terbuka" yang ditinggalkan penerus port Docker Desktop. Perbaikan: tes integrasi memakai koneksi baru per operasi (NullPool), pool API didaur ulang tiap 60 detik, batas waktu koneksi 10 detik.
- Jalur localhost:5432 di mesin ini tetap lambat dan kadang putus (0,3–0,7 detik per perintah, 2–3 detik per koneksi; restart kontainer tidak membantu). Karena itu ditambahkan layanan `uji` di docker-compose untuk menjalankan pytest di dalam jaringan Docker, serta cadangan presentasi SQLite (`python -m simulation.cadangan_sqlite`).
- Uji asap server nyata dengan cadangan SQLite: konsol tersaji di `/`, 8 permintaan paralel berhasil, demo 12 langkah 0,3 detik.
- `docs/keterlacakan.md` (FR/NFR → modul → tes), README lengkap (mulai cepat, konfigurasi, status data, batas klaim, struktur), naskah demo diperbarui, komentar pembuka di semua `__init__.py`.

**Hasil tes**
- Di dalam jaringan Docker (`docker compose --profile uji run --rm uji`): **190 lulus** (termasuk 8 tes integrasi TimescaleDB dan uji menyeluruh).
- Di host tanpa database: `pytest -m "not db"` → 182 lulus. Dari host, tes `db` lulus pada sebagian putaran dan gagal pada putaran lain karena koneksi diputus jaringan Docker Desktop (bukan karena logika).
- Konsol: `npm test` → 7 lulus; `npm run build` sukses; `export_dashboard.py` → 75/75 angka konsol = model (low/base/high).
- Cakupan (tanpa tes db): total 90%; inference 99%, gating 97%, action 98%, simulation 84%.

**Berkas berubah:** `db/koneksi.py`, `api/main.py`, `simulation/evaluasi.py` (pengaman pembagian nol), `simulation/cadangan_sqlite.py`, `docker-compose.yml` (layanan `uji`), `tests/conftest.py`, `tests/test_alur_menyeluruh.py`, `tests/test_demo.py`, `*/__init__.py`, `README.md`, `docs/keterlacakan.md`, `docs/naskah-demo.md`, `docs/asumsi.md`, `.gitignore`.

**Asumsi baru:** A-046, A-047 (total A-001 s.d. A-047).

---

# Laporan akhir serah terima (tahap 0–10)

**Yang selesai:** seluruh tahap rencana: kerangka dan konfigurasi, database TimescaleDB, 12 modul sumber data (dua sumber nyata berhasil diunduh), lapis I Bayesian dua mekanisme, lapis G kurva pemicu pemrograman dinamis, lapis A papan/log/ringkasan/penjaga klaim, simulasi enam kebijakan dengan metrik LOEO, REST API + JWT + kelola pengguna, konsol React lima tab, mode demo offline dengan skenario cadangan, uji menyeluruh, dan dokumentasi.

**Data yang masih dummy:** semua parameter biaya (C, L, P), waktu siap, prior lapis I, generator episode sintetis, muka air sintetis, jadwal KA (placeholder), prakiraan dan muka air per jam episode nyata. Nyata: hujan harian NASA POWER 2024–2026, prakiraan BMKG terkini, titik Glapan 1970 (24 Jan 2025) dan ambang Awas 1905.

**Temuan yang perlu diketahui tim**
1. Keunggulan SIGAP atas cost-loss di batas waktu kecil (0–3% pada diskon menunggu dummy 2%), bukan 14% seperti deck lama; besarnya ditentukan biaya menunggu/keterlambatan tiap tindakan.
2. NASA POWER tidak membedakan hujan hulu dari lokal (satu sel grid); pada episode nyata 24 Jan 2025 peluang model tetap rendah dan muka air sintetis 1734 vs nyata 1970.
3. Pada skenario cadangan, peluang model turun menjelang T−0 walaupun gangguan terjadi; disajikan apa adanya.
4. Jaringan Docker Desktop di laptop pengembang lambat dan kadang memutus koneksi; gunakan layanan `uji` untuk pengujian dan cadangan SQLite untuk presentasi bila perlu.

**Keputusan yang perlu diambil manusia**
- Nama dan batas waktu T6–T8; nilai C, L, P dan biaya keterlambatan dari praktisi KAI.
- Akun Earthdata/JAXA (hujan hulu satelit) atau data BBWS; pengisian katalog E1–E6 dan jadwal KA nyata.
- Konfirmasi definisi kebijakan "jam tetap 24 jam" dan "reaktif" (A-035), label ringkasan (A-032), hak operator/admin (A-039).
- Pemeriksaan visual konsol di peramban (agen tidak memiliki alat peramban di sesi ini).
- Pemeriksaan jaringan Docker Desktop (restart Docker Desktop, VPN/antivirus, mode jaringan WSL) sebelum presentasi.

---

## Pembaruan 22 Nov 2026 · Data historis GPM IMERG

**Yang dikerjakan**
- Token Earthdata dipasang di `.env` (tidak di-commit). Akses GES DISC awalnya ditolak "EULA Acceptance Failure"; setelah pemilik akun menyetujui aplikasi NASA GESDISC DATA ARCHIVE, akses berhasil. Modul kini menampilkan tautan persetujuan bila penolakan itu terjadi.
- `sensing/hujan_gpm_imerg.py` ditulis ulang: jalur utama Giovanni Time Series API (satu permintaan per titik untuk seluruh rentang), cadangan OPeNDAP per hari; produk Late (`gpm_imerg_late`) dan Final (`gpm_imerg_final`) disimpan terpisah; latensi masing-masing 14 dan 2520 jam di params.json.
- CLI `python -m sensing.jalankan imerg`; `muat` ikut memuat IMERG.
- **Data nyata baru:** IMERG Late 1053 hari (1 Jan 2024 s.d. 18 Nov 2026) dan Final 639 hari (s.d. 30 Sep 2025) untuk lokal, hulu, Gundih. Hulu kini terpisah dari lokal.
- Episode nyata 24 Jan 2025 memakai IMERG Late: peluang model sekitar 34–43% (T−72 s.d. T−30) lalu sekitar 23% (sebelumnya 9–16% dengan NASA POWER); SIGAP menyarankan T1 (T−42), T6 (T−18), T2 dan T5 (T−6); muka air sintetis berpuncak 1875 (24 Jan: 1763) vs nyata 1970.
- Konsol tab Data: pilihan sumber hujan (IMERG Late, IMERG Final, NASA POWER).

**Hasil tes:** `pytest -m "not db"` → 187 lulus (5 tes baru: pengurai Giovanni, jalur Late, Final tanpa cadangan OPeNDAP, EULA, episode nyata berbasis IMERG); `npm test` → 7 lulus. Catatan: satu putaran sempat menggantung karena kebuntuan event loop anyio di Windows (sinyal bangun lewat soket localhost tidak sampai); putaran ulang lulus.

---

## Pembaruan 22 Nov 2026 · Modul input dan fitur modular (src/sigap_ka)

**Yang dikerjakan**
- `src/sigap_ka/inputs/base.py`: skema keluaran `tanggal, zona, nilai, sumber, status_data`, validator, adapter ke tabel standar lapis S lama.
- `src/sigap_ka/inputs/bmkg.py`: pembaca .csv/.xlsx toleran (metadata "Nama Stasiun", baris judul Tanggal/RR, catatan kaki), pembersihan 8888/9999/negatif/teks/tanggal ganda → NaN dengan alasan di `catatan_qc`, pemetaan zona lewat `config/stasiun_bmkg.json`, keluaran `data/interim/bmkg_clean.csv`.
- `src/sigap_ka/inputs/imerg.py`: adapter IMERG Late/Final ke skema standar.
- `src/sigap_ka/features/hujan.py`: fitur hujan harian per zona dengan prioritas BMKG → IMERG Late; jendela berisi hari kosong → NaN.
- `src/sigap_ka/inputs/glapan_synth.py` + `features/glapan.py`: TMA Glapan sintetis per jam (dua waduk linear, lonjakan di atas 40 mm/hari, peluruhan 12 dan 120 jam), anchoring ke titik nyata dengan faktor dibatasi 0,5–3; fitur `glapan_relatif` dan `tren_glapan_6j`.
- Dijalankan pada data nyata: belum ada berkas BMKG (folder kosong, tidak galat); fitur hujan 1053 hari dari IMERG Late; TMA sintetis 25.272 jam, faktor anchor 1,91, puncak 24 Jan 2025 = 1970, maksimum 2338, di atas Awas sekitar 14% waktu (lihat A-051).

**Berkas berubah:** `src/sigap_ka/**`, `config/stasiun_bmkg.json`, `config/params.json` (muka_air.glapan_api, fitur_hujan, bmkg_stasiun), `pyproject.toml` (pythonpath src, saringan peringatan pandas/numpy), `requirements.txt` (openpyxl), `.gitignore` (data/interim), `tests/test_input_bmkg.py`, `tests/test_glapan_synth.py`, `data/processed/hujan_features.csv`, `data/processed/glapan_features.csv`, `README.md`.

**Asumsi baru:** A-049 s.d. A-052.

**Keputusan manusia:** berkas BMKG asli untuk memverifikasi format pembaca dan konvensi hari (A-049); seri TMA BBWS untuk menggantikan estimasi sintetis.

**Hasil tes:** `pytest tests/test_input_bmkg.py tests/test_glapan_synth.py` → 18 lulus; `pytest -m "not db"` → 205 lulus.

---

## Pembaruan 22 Nov 2026 · Data BMKG asli dan validasi IMERG

**Yang dikerjakan**
- Berkas asli `data/raw/bmkg/DataIklimBulanan_2024-11_2026-10_ahmadyani_x.xlsx` (tidak di-commit) diperiksa: dua lembar (96835 Stasiun Klimatologi Jawa Tengah, 96839 Stasiun Meteorologi Ahmad Yani), metadata ID WMO/lintang/bujur/elevasi, tabel `Periode | rainfall` **bulanan**, catatan kaki kode 8888/9999.
- `inputs/bmkg.py` disesuaikan dengan format asli: membaca semua lembar, mengenali `Periode` (YYYY-MM → resolusi bulanan) maupun format harian, mengambil ID WMO dan koordinat dari metadata, mencocokkan stasiun lewat ID WMO. Hasil: 48 baris (24 bulan × 2 stasiun), tanpa nilai anomali.
- `config/stasiun_bmkg.json` diisi ID WMO dan koordinat dari metadata berkas BMKG; zona tetap `semarang_pembanding`.
- IMERG Late (730 hari) dan Final (334 hari) diunduh untuk sel stasiun Semarang; `features/validasi_imerg.py` membandingkan total bulanan → `data/processed/validasi_imerg_bmkg.csv`.
- **Temuan:** IMERG Late bias +17,4%, korelasi 0,82, MAE 78 mm/bulan (24 bulan); IMERG cenderung lebih tinggi dari penakar dengan selisih bulanan bisa besar (mis. Feb 2026 455 vs 225 mm; Mei 2026 139 vs 369 mm). Antarstasiun: −5,6%, korelasi 0,96.

**Hasil tes:** `pytest -m "not db"` → 210 lulus (5 tes baru: format bulanan multi-lembar seperti berkas asli, bulanan tidak masuk fitur harian, validasi IMERG).

**Keputusan manusia:** data BMKG harian/per jam (bila bisa diminta lewat PTSP) dan pos hujan BBWS di Grobogan/hulu Tuntang tetap dibutuhkan untuk koreksi IMERG di koridor.

---

## Perbaikan lanjutan 22 Nov 2026 · Langkah 1–3: kejadian kandidat, uji balik, kepekaan bias

**Yang dikerjakan**
- **Katalog kejadian kandidat** `data/manual/kejadian_kandidat.csv` (K01–K09, Feb 2024–Apr 2026) dari berita publik dan rilis BNPB/KAI yang dikutip media. Setiap baris memuat kutipan mekanisme, dampak KA, penyebab, tautan yang dibaca, tautan yang gagal dibuka, dan status `kandidat`. E1–E6 tidak diubah. Pembaca dan validator ada di `src/sigap_ka/inputs/kejadian_kandidat.py`; ringkasan katalog di `docs/kejadian-kandidat.md`.
- **Titik Glapan 1970** kini berjam 25/1/2025 00.00 WIB sesuai rilis BNPB (A-056). Sumber manual sekarang **mengganti** berkas olahan (`simpan_olahan(..., ganti=True)`), tidak lagi digabung.
- **T−0 episode nyata 24 Jan 2025 = 22.25 WIB** (jam tutup menurut detikTravel/Liputan6, A-014).
- **Pembangun episode umum** `bangun_episode_hujan_nyata(t0, ...)` untuk T−0 sembarang. Ada skala hujan dan tiga mode prakiraan: sintetis, persistensi (tanpa informasi masa depan, A-058), dan kosong.
- **Uji balik** `simulation/uji_balik.py` menjalankan tiga analisis: kandidat × varian prakiraan, kepekaan bias IMERG (skala 0,79–1,2), dan pemindaian harian 2024–2026 dengan AUC. Hasil di `data/processed/uji_balik/`, ringkasan di `docs/uji-balik.md`.
- **Dua bug laten diperbaiki.** Keduanya muncul hanya bila T−0 bermenit:
  - batas jendela akumulasi hujan meleset karena galat titik mengambang (hujan 3 hari 8 mm, seharusnya 70 mm);
  - grid per jam prakiraan sintetis tidak sejajar sehingga semua prakiraan bernilai nol.
- **Menyimpan ulang episode ke database** kini menghapus seri lama episode itu lebih dulu (`hapus_seri_episode`).

**Temuan utama** (rinci di `docs/uji-balik.md`)
- Hari kejadian berpeluang lebih tinggi daripada hari lain (AUC 0,83 pada T−0), tetapi peluang absolutnya rendah (maksimum sekitar 0,2) karena model dilatih pada data sintetis.
- Model hanya sedikit di atas hujan hulu mentah (AUC 0,79).
- Hujan yang benar-benar turun memisahkan lebih baik (0,87). Batas utamanya latensi IMERG Late harian (14–38 jam, A-057).
- Bias IMERG ±20% hanya menggeser tindakan yang dekat ambang.
- K05 (tanggul jebol) dan K06 terjadi dengan hujan rendah, sehingga tidak terdeteksi dari hujan saja.

**Berkas berubah:** `data/manual/kejadian_kandidat.csv`, `data/manual/muka_air_glapan.csv`, `src/sigap_ka/inputs/kejadian_kandidat.py`, `simulation/episode.py`, `simulation/uji_balik.py`, `inference/fitur.py`, `sensing/standar.py`, `sensing/jalankan.py`, `db/repositori.py`, `config/params.json` (`_nyata.glapan_24jan2025`, `demo.episode_nyata.t0`, blok `uji_balik`), `config/pengaturan.py`, tes baru (`test_kejadian_kandidat.py`, `test_uji_balik.py`, tambahan di `test_sensing_sumber.py` dan `test_simulasi.py`), `docs/kejadian-kandidat.md`, `docs/uji-balik.md`, `docs/asumsi.md` (A-014, A-022, A-051, A-055–A-060), `README.md`.

**Hasil tes:** `pytest -m "not db"` → 229 lulus.

**Keputusan manusia:**
- Verifikasi K01–K09 dan pemetaannya ke E1–E6.
- Konfirmasi T−0 22.25 untuk episode 24 Jan 2025.
- Kalibrasi peluang dengan label nyata.

---

## Perbaikan lanjutan 22 Nov 2026 · Langkah 4–7: realisme generator, IMERG per jam, rerata DAS, muka air tertunda, dasbor

**Yang dikerjakan**
- **Realisme generator** (`simulation/realisme_generator.py`): episode latih lapis I jauh lebih basah daripada hari nyata (median hujan hulu 72 jam 81 mm ≈ persentil 98). Ini menjelaskan peluang absolut yang rendah pada data nyata (A-061). Parameter generator tidak diubah; perubahannya keputusan tim.
- **IMERG Late per jam** (`imerg --produk late_jam`): 25.288 jam × 3 titik dari produk setengah jam lewat Giovanni (A-064). Jumlah hariannya identik dengan produk harian.
- **Rerata DAS Tuntang** (`sensing/hujan_imerg_das.py`, `imerg-das`): 9 sel IMERG (A-063). Korelasi harian dengan sel titik hulu 0,97.
- **Muka air sintetis tertunda** (A-062). Uji balik sebelumnya memakai muka air sintetis tanpa latensi, padahal dihitung dari hujan satelit yang belum tersedia (terlalu optimistis). Uji balik utama kini memakai muka air tertunda; varian waktu nyata tetap dilaporkan sebagai pembanding.
- **Uji balik untuk tiga sumber hujan** (harian, jam, harian_das) dengan selang 95% bootstrap AUC (`docs/uji-balik.md`).
- **Prakiraan persistensi** kini memakai rerata 24 jam terakhir yang tersedia, sehingga berlaku untuk data harian maupun per jam.
- **Dasbor:** bagian *Evaluasi pada data nyata* di tab Data, lewat `GET /data/evaluasi-nyata` (`simulation/ringkasan_nyata.py`). Isinya validasi IMERG vs BMKG, grafik AUC dengan selang 95%, tabel kandidat dan rencana SIGAP, serta realisme generator. Tautan berita tidak diteruskan, hanya domainnya.
- **Database:** memuat ulang sumber manual kini mengganti baris lama (titik Glapan 24/1 23.00 terhapus). Data per jam dan DAS ikut dimuat (`obs_hujan` 85.169 baris). Episode demo dibangun ulang dengan T−0 22.25.

**Temuan utama**
- AUC peluang T−0 0,80 (0,68–0,91) pada sumber harian. Nilai ini setara hujan hulu tersedia tanpa model (0,79).
- Data per jam dan rerata DAS tidak menaikkan AUC.
- Hujan aktual yang belum tersedia memberi 0,87. Artinya yang dibutuhkan adalah pengamatan waktu nyata (pos hujan atau TMA BBWS), bukan sekadar satelit dengan jeda lebih pendek.

**Berkas berubah:** `sensing/hujan_gpm_imerg.py`, `sensing/hujan_imerg_das.py`, `sensing/jalankan.py`, `simulation/episode.py`, `simulation/uji_balik.py`, `simulation/realisme_generator.py`, `simulation/ringkasan_nyata.py`, `api/routers/data.py`, `db/repositori.py`, `dashboard/src/komponen/EvaluasiNyata.jsx`, `dashboard/src/tab/TabData.jsx`, `dashboard/src/gaya.css`, `config/params.json` (latensi baru, `das_tuntang`, `uji_balik`), tes (`test_uji_balik.py`, `test_realisme_generator.py`, `test_sensing_sumber.py`, `test_db_model.py`, `test_api.py`, `konsol.test.jsx`), data olahan (`hujan_gpm_imerg_jam.csv`, `hujan_gpm_imerg_das.csv`, `uji_balik/*`), `docs/uji-balik.md`, `docs/asumsi.md` (A-061–A-064), `docs/data-input-model.md`, `README.md`.

**Hasil tes:**
- `pytest -m "not db"` → 240 lulus.
- `vitest` → 9 lulus.
- `vite build` → berhasil.
- Tes database lewat layanan `uji` (Docker) → semua lulus pada langkah sebelumnya; diulang sesudah commit ini.

**Keputusan manusia:**
- Pilihan kalibrasi: (a) kalibrasi keluaran atau (b) parameterisasi ulang generator.
- Verifikasi kotak sel DAS dengan poligon BBWS.
- Pemeriksaan visual bagian evaluasi di dasbor.
