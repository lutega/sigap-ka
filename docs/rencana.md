# SIGAP-KA: Rencana Implementasi

Status: **disetujui 21 November 2026**. Disusun 21 November 2026 dari `CLAUDE.md`,
`docs/arsitektur.md`, `docs/spesifikasi-fungsional.md` (acuan utama bagian 4 dan 8–16),
dan `docs/peran-agen.md`.

---

## A. Prinsip yang berlaku di semua tahap

- Tiap tahap: tulis kode dan tes → jalankan `pytest` → laporan serah terima di
  `docs/progress.md` (yang dikerjakan, berkas yang berubah, data yang masih dummy, asumsi baru,
  hambatan, keputusan yang perlu diambil manusia) → commit kecil per langkah dan `git push`
  → lanjut otomatis ke tahap berikutnya bila tes lulus.
- Berhenti hanya bila buntu: data bersurat menjadi jalur kritis, ada keputusan lingkup, atau
  tes gagal 3 kali pada masalah yang sama. Alasannya ditulis di `docs/progress.md`.
- Setiap file diawali komentar tujuan, lapis, sumber, masukan, keluaran, keterbatasan;
  setiap fungsi punya docstring bahasa Indonesia.
- Parameter hanya dari `config/params.json` dan `.env`; tidak ada angka model di dalam kode.
- **Tanpa intip masa depan:** lapis I, G, A, dan mode demo diuji bahwa mengubah data sesudah
  jam keputusan tidak mengubah hasil pada jam itu.
- **Tidak pernah menyatakan jalur aman:** satu penjaga klaim dipakai semua keluaran
  (API dan dashboard), dan ada tes yang memindai seluruh respons serta teks tampilan.
- **Angka nyata** hanya dari dokumen proyek (Glapan 1970 pada 24 Jan 2025, ambang Awas 1905,
  muka air sintetis lama 1768, refund Pekalongan Rp3,5 miliar untuk 124 perjalanan) atau dari
  unduhan sumber terbuka yang tercatat di `log_pengambilan`. Selebihnya dummy, berlabel
  `is_simulated = true`, dan dicatat di `docs/asumsi.md`.

## B. Kondisi lingkungan (temuan awal)

| Temuan | Tindak lanjut |
| --- | --- |
| `python` di PATH adalah 3.9.13, tidak memenuhi 3.11+ | Memakai `py -3.12 -m venv .venv` (Python 3.12.10 terpasang) |
| Docker Desktop 29.9 aktif | TimescaleDB lewat `docker compose` |
| Node 24 dan npm 11 terpasang | Dipakai untuk dashboard |
| Berkas bernama `docs/arsitekur.md`, sedangkan CLAUDE.md menyebut `docs/arsitektur.md` | Diganti nama di tahap 0 |
| `.env` dan `.env.example` ditulis PowerShell dengan BOM UTF-8 | Ditulis ulang tanpa BOM; pembaca env memakai `utf-8-sig` agar tahan BOM |
| `sigap_data_proyek_minor.zip` (model.py, params.json lama, generator, konsol) tidak ada di repo | Kode dibangun dari awal, sesuai peran-agen ("belum ada kode yang ditulis") |

## C. Strategi pengujian

- Satu berkas tes per modul di `tests/`; satu perintah `pytest` untuk backend dan
  `npm test` untuk dashboard.
- **Dua lapis uji database:**
  1. Tes unit dan API memakai SQLite di memori dengan skema SQLAlchemy yang sama
     (tanpa fitur khusus TimescaleDB), sehingga bisa jalan di mana saja.
  2. Tes integrasi bertanda `@pytest.mark.db` berjalan terhadap TimescaleDB di Docker
     (database terpisah `sigap_test`). Bila DB tidak terjangkau, tes ini dilewati dan
     dilaporkan sebagai **dilewati**, bukan lulus.
- Tes tidak mengakses internet: HTTP di-mock dengan fixture berbentuk respons API asli
  yang berisi angka uji (bukan data nyata).
- Keterulangan: seluruh bilangan acak memakai seed dari `SIM_SEED`.

## D. Keputusan awal yang saya ambil (default, dapat dikoreksi)

| No | Hal | Pilihan default | Dasar |
| --- | --- | --- | --- |
| D1 | Letak paket | Paket Python langsung di akar repo (`config/`, `sensing/`, `inference/`, `gating/`, `action/`, `simulation/`, `api/`, `auth/`, `db/`, `dashboard/`) | Spesifikasi 14.1 |
| D2 | Tabel di luar 14.5 | Tambah `pengguna` (bagian 15), `episode` (untuk `/episode`), `sesi_demo` (bagian 16); `keputusan_operator` ditambah kolom `username` dan `mode` (normal/demo) | Bagian 15 dan 16 |
| D3 | Daftar T1–T9 | T1 informasi penumpang dan refund, T2 menahan KA di stasiun asal, T3 memutar via Gundih/Solo, T4 bus pengganti, T5 siaga Dapsus dan AMUS, T9 pembatalan. **T6–T8 placeholder "belum dikonfirmasi"** dengan parameter dummy, tampil berlabel | Spesifikasi 10.4 dan 12.2; pertanyaan terbuka 7 |
| D4 | Model lapis I | Regresi logistik **multinomial** Bayesian (kelas: tidak terganggu, genangan, gerusan) dengan prior ahli Gaussian dari params.json dan aproksimasi Laplace. Bentuk ini menjamin kedua mekanisme saling lepas, sehingga p_total = p_genangan + p_gerusan ≤ 1. Laporan petugas lapangan masuk sebagai pembaruan rasio kemungkinan | Spesifikasi 9.2–9.5 (usulan *asumsi*) |
| D5 | Model lapis G | Pemrograman dinamis mundur pada grid peluang. Peluang antarprakiraan diperlakukan sebagai martingale (langkah acak di skala logit, simpangan per langkah di params.json). Agar menunggu tidak selalu menang, biaya tindakan naik mendekati batas waktu dan tepat sama dengan C di batas waktu (pola model keputusan dinamis Regnier & Harr, 2006). Di batas waktu ambang tepat (C + P) / (L + P). L efektif = L × faktor skenario lama tutup (9.4) | Spesifikasi 10.2; rujukan dicek tim |
| D6 | Langkah waktu | Jam keputusan tiap 6 jam (siklus prakiraan), horizon episode 72 jam sebelum T−0; nilai dummy di params.json | Asumsi |
| D7 | Definisi enam kebijakan | **SIGAP**: bertindak saat p ≥ kurva pemicu. **Jam tetap 24 jam**: semua tindakan diputuskan sekali pada T−24 jam (atau di batas waktunya bila lebih awal) dengan ambang statis. **Ambang tetap 0,5**: bertindak begitu p ≥ 0,5 sebelum batas waktu. **Cost-loss di batas**: diputuskan tepat di batas waktu dengan ambang statis. **Reaktif**: bertindak hanya setelah ada bukti gangguan teramati (laporan lapangan atau air di badan rel) selama batas waktu belum lewat. **Informasi sempurna**: mengetahui hasil episode, bertindak hanya bila gangguan terjadi (batas bawah biaya). Semua kebijakan menerima p yang sama pada jam yang sama | FR-E1, FR-E4 |
| D8 | Alur data | Sensing menulis `data/raw/` (diabaikan git) dan `data/processed/` (di-commit, ukuran kecil), lalu dimuat ke DB. API dan demo membaca DB lokal, sehingga berjalan offline | Spesifikasi 14.4, 16 |
| D9 | Data nyata dari internet | NASA POWER dan prakiraan BMKG publik diunduh sungguhan di tahap 2 bila internet tersedia (yang dikirim hanya koordinat koridor dan kode wilayah). Modul GPM IMERG (akun Earthdata) dan GSMaP (akun JAXA) disiapkan; tanpa kredensial di `.env`, sistem beralih ke cadangan berlabel | NFR-5 |
| D10 | OCR + LLM | Dalam lingkup sebagai metode opsional (`KEJADIAN_METODE=ocr_llm`). OCR dengan Tesseract (dipasang terpisah), LLM lewat Claude API (`ANTHROPIC_API_KEY` dan nama model di `.env`). Tanpa kunci atau Tesseract, metode `manual` tetap berjalan; tes memakai klien LLM tiruan | Pertanyaan terbuka 7; urutan tahap dari Anda |
| D11 | Katalog E1–E6 dan jadwal KA | Hanya fakta yang ada di dokumen. Kolom yang belum diketahui dibiarkan kosong dengan status "belum terkonfirmasi", tidak ditebak. Jadwal KA memakai placeholder KA-A s.d. KA-F berlabel dummy sampai tim mengisi `data/manual/jadwal_ka.csv` | CLAUDE.md, peran-agen |
| D12 | Episode nyata 24 Jan 2025 | Hujan NASA POWER nyata + titik Glapan nyata + prakiraan dan muka air sintetis; label nyata/dummy tampil per seri | Spesifikasi 16 |
| D13 | Klaim "14% lebih murah" | Tidak dipakai ulang. Yang dilaporkan adalah angka dari simulasi baru, berlabel "parameter dummy, batas atas menurut asumsi model" | Spesifikasi 6 |

## E. Pertanyaan untuk Anda (tidak menghalangi; default di bagian D dipakai bila tidak dijawab)

1. Apakah `sigap_data_proyek_minor.zip` tersedia? Bila ya, taruh di `data/raw/` agar nilai
   dummy, katalog kejadian, dan definisi kebijakan disamakan dengan versi lama.
2. Nama dan batas waktu siap tindakan T6–T8.
3. Bila punya akun Earthdata/JAXA atau kunci API LLM, isi sendiri di `.env`
   (jangan ditempel di chat).
4. Konfirmasi definisi kebijakan "jam tetap 24 jam" dan "reaktif" pada D7.

---

## F. Tahapan

### Tahap 0 · Kerangka repo, docker-compose, `.env.example`, `params.json`

**Tujuan:** lingkungan bisa dipasang dan dijalankan dengan beberapa perintah; satu sumber
parameter siap dipakai semua lapis.

**File yang dibuat atau diubah:**
- `docs/arsitektur.md` (ganti nama dari `arsitekur.md`)
- `pyproject.toml` (konfigurasi pytest dan marker `db`), `requirements.txt`, `requirements-dev.txt`
- `docker-compose.yml` (image TimescaleDB untuk PostgreSQL 16, healthcheck, volume, port dan kredensial dari `.env`)
- `.env.example` ditulis ulang tanpa BOM; tambahan: `POSTGRES_*`, `DATABASE_URL_TEST`,
  `JWT_SECRET`, `JWT_MENIT_KEDALUWARSA`, `EARTHDATA_TOKEN`, `JAXA_USER`, `JAXA_PASSWORD`,
  `ANTHROPIC_API_KEY`, `LLM_MODEL`, `CORS_ORIGINS`
- `config/__init__.py`, `config/pengaturan.py` (membaca `.env` dengan pydantic-settings,
  membaca params.json, memilih preset, validasi Pydantic)
- `config/params.json` dengan blok: `_meta` (versi, status nilai), `lokasi` (koordinat
  perkiraan Gubug–Karangjati, hulu Tuntang, Gundih), `tindakan` T1–T9 (C, L, P, waktu siap;
  low/base/high), `inferensi` (prior koefisien, rasio kemungkinan laporan lapangan, latensi
  tiap sumber), `lama_tutup` (tiga skenario), `gating` (grid, simpangan, kenaikan biaya),
  `episode`, `dummy` (generator), `simulasi` (N = 300), `muka_air` (ambang Awas 1905),
  `sumber_data` (sumber aktif, inti/tambahan, opsional), `demo`
- `data/raw/`, `data/processed/`, `data/manual/` (dengan `.gitkeep`)
- `__init__.py` untuk `sensing`, `inference`, `gating`, `action`, `simulation`, `api`,
  `api/routers`, `auth`, `db`
- `tests/conftest.py`, `tests/test_pengaturan.py`
- `README.md` (awal), `docs/asumsi.md`, `docs/progress.md`, `.gitignore` (ditambah)

**Kriteria selesai:**
- `.venv` (Python 3.12) dibuat dan `pip install -r requirements-dev.txt` sukses.
- `docker compose up -d` menghasilkan kontainer sehat dan ekstensi `timescaledb` aktif.
- `pytest` lulus: params.json valid untuk ketiga preset, T1–T9 lengkap,
  0 < (C + P) / (L + P) < 1 untuk tiap tindakan, nilai dummy bertanda dummy, `.env` terbaca
  walau ber-BOM.
- README memuat cara pasang awal.

### Tahap 1 · `db/`: skema tabel dan hypertable (spesifikasi 14.5)

**Tujuan:** skema 14.5 beserta tabel pendukung, hypertable dan continuous aggregate,
dan fungsi baca-tulis yang dipakai lapis lain.

**File yang dibuat:**
- `db/koneksi.py` (engine dan sesi dari `DATABASE_URL`)
- `db/model.py` (ORM SQLAlchemy 2.0: `obs_hujan`, `prakiraan_hujan`, `obs_muka_air`,
  `sumber_data`, `log_pengambilan`, `kejadian`, `jadwal_ka`, `tindakan`, `keputusan_operator`,
  `hasil_simulasi`, ditambah `pengguna`, `episode`, `sesi_demo`)
- `db/inisialisasi.py` (`python -m db.inisialisasi`: ekstensi, tabel, `create_hypertable`
  untuk tiga hypertable, continuous aggregate `hujan_harian`, view `hujan_akumulasi`
  1/3/5 hari; idempoten; pada SQLite hanya membuat tabel)
- `db/repositori.py` (simpan tabel standar dengan upsert, ambil seri per rentang waktu,
  ambil prakiraan yang terbit ≤ jam keputusan, catat `log_pengambilan`)
- `tests/test_db_model.py` (SQLite), `tests/test_db_timescale.py` (marker `db`)

**Kriteria selesai:**
- Inisialisasi dijalankan dua kali tanpa galat; tiga tabel terdaftar sebagai hypertable;
  continuous aggregate terbentuk.
- Upsert tidak menggandakan baris.
- Tes "hanya prakiraan yang sudah terbit pada jam keputusan" lulus.
- Tidak ada kolom C, L, P di DB (tabel `tindakan` hanya id, nama, batas waktu siap).

### Tahap 2 · `sensing/`: semua sumber data

**Tujuan:** semua sumber menghasilkan tabel standar (`waktu, lokasi, nilai, satuan, sumber,
is_simulated`) dengan pola `ambil() → ke_format_standar() → cek_kualitas()`; data mentah ke
`data/raw/`, olahan ke `data/processed/` dan DB, asal data tercatat.

**File yang dibuat:**
- `sensing/standar.py` (kolom standar, validasi skema, penanda kualitas, simpan raw/processed, catatan asal data)
- `sensing/registri.py` (nama sumber → modul; sumber aktif dan cadangan dari params.json/.env;
  pemilih metode kejadian via `KEJADIAN_METODE`; cadangan berlabel bila sumber opsional kosong)
- `sensing/hujan_nasa_power.py` (API publik, tanpa akun)
- `sensing/hujan_gpm_imerg.py` (NASA GES DISC, token Earthdata)
- `sensing/hujan_gsmap.py` (JAXA, akun gratis)
- `sensing/prakiraan_bmkg.py` (API publik prakiraan dan peringatan dini; menyimpan waktu terbit dan waktu valid)
- `sensing/muka_air_glapan.py` (membaca `data/manual/muka_air_glapan.csv` dari rilis BNPB)
- `sensing/muka_air_sintetis.py` (model hujan–limpasan tangki linear, parameter di params.json, `is_simulated = true`)
- `sensing/muka_air_bbws.py`, `sensing/hujan_bmkg_stasiun.py` (data bersurat, opsional:
  membaca CSV bila ada, kosong bila belum)
- `sensing/kejadian_manual.py` (`data/manual/kejadian.csv`)
- `sensing/kejadian_ocr_llm.py` (OCR → LLM → baris terstruktur → kode periksa K1–K3;
  presisi dan recall terhadap koding manual)
- `sensing/jadwal_ka.py` (`data/manual/jadwal_ka.csv`; placeholder KA-A s.d. KA-F dummy)
- `sensing/dummy_generator.py` (episode sintetis: hujan lokal dan hulu, prakiraan dengan galat
  yang mengecil terhadap lead time, muka air via model sintetis, kejadian/mekanisme/lama tutup
  sebagai "kebenaran"; seed dan preset)
- `sensing/jalankan.py` (CLI: ambil satu atau semua sumber → raw → processed → DB)
- `data/manual/*.csv` (templat berisi fakta dari dokumen saja), `data/processed/*`
- `tests/test_<modul>.py` per modul, `tests/fixtures/`

**Kriteria selesai:**
- Semua modul lulus satu tes kontrak bersama yang berparameter (kolom, tipe,
  `is_simulated` boolean, `sumber` terisi).
- Seluruh keluaran generator dummy, muka air sintetis, dan jadwal placeholder berlabel
  `is_simulated = true`.
- Generator dengan seed sama memberi keluaran identik.
- Sumber tanpa kredensial memberi pesan jelas dan registri beralih ke cadangan berlabel (NFR-5).
- Setiap pengambilan tercatat di `log_pengambilan` (waktu ambil, rentang, tautan/versi, status).
- Bila internet tersedia: hujan NASA POWER 2024–2026 untuk titik lokal dan hulu tersimpan di
  `data/processed/` dan DB dengan `is_simulated = false`.

### Tahap 3 · `inference/`: peluang gangguan, mekanisme, lama tutup

**Tujuan:** pada tiap jam keputusan menghasilkan peluang gangguan, peluang per mekanisme,
sebaran lama tutup, dan bukti paling berpengaruh, hanya dari informasi yang sudah tersedia.

**File yang dibuat:**
- `inference/fitur.py` (fitur 9.1 pada jam t: hujan lokal 1/3/5 hari, hujan hulu, prakiraan,
  muka air Glapan dan trennya, laporan lapangan; menghormati latensi tiap sumber dan waktu terbit prakiraan)
- `inference/peluang_gangguan.py` (logistik multinomial Bayesian, prior ahli, Laplace,
  pembaruan laporan lapangan)
- `inference/mekanisme.py` (genangan vs gerusan, kontribusi tiap bukti)
- `inference/lama_tutup.py` (skenario pendek/sedang/panjang bersyarat mekanisme)
- `inference/estimasi.py` (satu pintu: `estimasi(episode, jam)` → hasil lapis I)
- `tests/test_fitur.py`, `test_peluang_gangguan.py`, `test_mekanisme.py`, `test_lama_tutup.py`, `test_estimasi.py`

**Kriteria selesai:**
- 0 ≤ p ≤ 1 dan p_total = p_genangan + p_gerusan.
- Tes tanpa intip masa depan lulus.
- Kasus mirip E3/E6 (hujan lokal rendah, hulu dan Glapan tinggi) memberi peluang lebih tinggi
  daripada kasus kering, menandakan bobot bukti hulu.
- Laporan lapangan air di badan rel menaikkan peluang tajam.
- Uji sensitivitas prior low/base/high tercatat.
- Sebaran lama tutup berjumlah 1; genangan condong pendek, gerusan condong panjang.

### Tahap 4 · `gating/`: cost-loss dan kurva pemicu

**Tujuan:** ambang cost-loss dan kurva pemicu tiap tindakan, serta status per tindakan.

**File yang dibuat:**
- `gating/cost_loss.py` (ambang (C + P) / (L + P), biaya harapan bertindak dan tidak, L efektif dari skenario lama tutup)
- `gating/kurva_pemicu.py` (pemrograman dinamis mundur, grid peluang, transisi martingale,
  kurva per jam keputusan; hitung ulang dengan parameter pengganti untuk slider)
- `gating/status.py` (Putuskan sekarang / Tunggu prakiraan berikutnya / Terlambat;
  tindakan yang disetujui tidak dihitung ulang kecuali dibatalkan)
- `tests/test_cost_loss.py`, `test_kurva_pemicu.py`, `test_status.py`

**Kriteria selesai:**
- Di batas waktu siap, kurva = (C + P) / (L + P) (dalam toleransi grid).
- Sebelum batas waktu, kurva ≥ ambang statis dan tidak naik menuju batas waktu (preset dummy).
- Kurva T1 turun paling awal; ambang T9 pada preset base > 0,7 (dummy, sesuai 10.4).
- Menaikkan P menaikkan ambang (FR-P1).
- Hasil DP sama dengan perhitungan brute force untuk kasus kecil (2–3 langkah).
- Status mengikuti aturan 10.3, termasuk Terlambat.

### Tahap 5 · `action/`: papan tindakan dan log keputusan

**Tujuan:** papan 9 tindakan, log keputusan operator, ringkasan T−0, pengecekan maladaptasi.

**File yang dibuat:**
- `action/papan_tindakan.py` (status, p, nilai kurva, selisih, sisa waktu, alasan singkat,
  peringatan maladaptasi 12.4: rute Gundih ikut terdampak hujan, jalan Semarang–Purwodadi putus)
- `action/log_keputusan.py` (setujui/tolak/batalkan; waktu, status SIGAP saat itu, username, alasan, mode)
- `action/ringkasan.py` (biaya keputusan operator vs saran SIGAP di T−0; klasifikasi
  terlalu awal, terlambat, sia-sia, tepat)
- `action/penjaga_klaim.py` (menolak teks yang menyatakan jalur aman di semua keluaran)
- `tests/test_papan_tindakan.py`, `test_log_keputusan.py`, `test_ringkasan.py`, `test_penjaga_klaim.py`

**Kriteria selesai:**
- Papan selalu 9 baris; tindakan placeholder berlabel.
- Keputusan tercatat lengkap; tindakan yang disetujui tidak berubah status sampai dibatalkan.
- Ringkasan biaya sama dengan rumus FR-E2 pada kasus uji yang dihitung tangan.
- Peringatan Gundih dan jalan putus muncul pada kondisi pemicunya.
- Penjaga klaim menolak frasa seperti "jalur aman" dan "aman dilalui", tanpa salah tangkap
  kata seperti "keamanan".

### Tahap 6 · `simulation/`: episode, enam kebijakan, evaluasi

**Tujuan:** simulasi banyak episode, perbandingan enam kebijakan, evaluasi biaya dan metrik deteksi.

**File yang dibuat:**
- `simulation/episode.py` (struktur episode; episode sintetis dari generator; episode nyata dari DB/processed)
- `simulation/kebijakan.py` (enam kebijakan sesuai D7)
- `simulation/evaluasi.py` (biaya per episode FR-E2; POD, FAR, CSI, lead time dengan
  leave-one-episode-out; pembanding aturan hujan lokal dan indeks adaptasi H-MHEWS)
- `simulation/jalankan.py` (CLI `python -m simulation.jalankan --preset base --n 300 --seed 42`
  → tabel `hasil_simulasi` dan CSV)
- `tests/test_episode.py`, `test_kebijakan.py`, `test_evaluasi.py`

**Kriteria selesai:**
- Seed sama → hasil identik (NFR-4, FR-E3).
- Biaya informasi sempurna ≤ semua kebijakan pada tiap episode.
- Rata-rata biaya SIGAP ≤ cost-loss di batas pada preset base (dengan catatan bahwa ini batas
  atas menurut asumsi model sendiri).
- Tabel biaya per kebijakan untuk preset low/base/high tersimpan.
- POD, FAR, CSI benar pada kasus uji yang dihitung tangan.

### Tahap 7 · `api/` + `auth/`: endpoint FastAPI, login JWT, kelola pengguna

**Tujuan:** REST API sesuai 14.2 dan bagian 15, sebagai lapisan tipis di atas modul.

**File yang dibuat:**
- `api/main.py`, `api/schemas.py`, `api/deps.py`
- `api/routers/data.py` (`/data/sumber`, `/data/hujan`, `/data/muka-air`, `/data/kejadian`)
- `api/routers/prediksi.py` (`/episode`, `/episode/{id}/prediksi`)
- `api/routers/kurva.py` (`/tindakan`, `/kurva/{tindakan}`, `/kurva/hitung`)
- `api/routers/tindakan.py` (`/episode/{id}/papan`, `/episode/{id}/keputusan`, `/episode/{id}/ringkasan`)
- `api/routers/simulasi.py` (`/simulasi`, `/simulasi/{id}`, tugas latar belakang)
- `api/routers/auth.py` (`/auth/login`, `/auth/saya`), `api/routers/pengguna.py` (`/pengguna`, khusus admin)
- `auth/keamanan.py` (hash bcrypt), `auth/token.py` (JWT), `auth/pengguna.py` (layanan pengguna;
  akun awal dari `ADMIN_USER`/`ADMIN_PASSWORD`), `auth/dependensi.py` (wajib token, wajib admin)
- `tests/test_api_*.py`, `tests/test_auth.py`

**Kriteria selesai:**
- Semua endpoint 14.2 tersedia dan terdokumentasi di `/docs`.
- Tanpa token → 401; operator ke `/pengguna` atau `POST /simulasi` → 403.
- Login `admin`/`admin` berhasil pada DB baru; password tersimpan sebagai hash bcrypt.
- Admin dapat menambah, menonaktifkan, dan mengatur ulang password pengguna.
- Keputusan tercatat dengan username pelaku.
- Tes memindai semua respons: tidak ada pernyataan jalur aman.
- README memuat cara menjalankan API.

### Tahap 8 · `dashboard/`: login, lima tab, papan tindakan

**Tujuan:** konsol web React + Vite + Recharts yang hanya berkomunikasi lewat API.

**File yang dibuat:**
- `dashboard/package.json`, `vite.config.js`, `index.html`
- `dashboard/src/main.jsx`, `App.jsx`, `api.js` (klien REST dan token), konteks login
- Halaman: `Login.jsx`, `TabOperasi.jsx`, `TabData.jsx`, `TabPrediksi.jsx`, `TabKurva.jsx`,
  `TabSimulasi.jsx`, `KelolaPengguna.jsx`
- Komponen: `PapanTindakan.jsx`, `GrafikPeluangKurva.jsx`, `LabelData.jsx` (nyata/dummy), slider parameter
- `dashboard/src/__tests__/*.test.jsx` (vitest + Testing Library)
- `dashboard/export_dashboard.py` (satu perintah: build dashboard dan cek kesesuaian angka API
  vs model untuk tiap preset; NFR-3, FR-E3)
- API menyajikan hasil build di `/`, sehingga demo cukup satu server

**Kriteria selesai:**
- `npm run build` dan `npm test` lulus.
- Semua seri berlabel nyata/dummy; tidak ada teks pernyataan jalur aman (dicek tes).
- Menu kelola pengguna hanya tampil untuk admin.
- `export_dashboard.py` melaporkan angka konsol sama dengan model untuk low/base/high.

### Tahap 9 · Mode demo (spesifikasi 16) dan skenario cadangan presentasi

**Tujuan:** memutar ulang episode jam demi jam secara offline, dengan skenario cadangan yang
hasilnya selalu sama.

**File yang dibuat:**
- `simulation/demo.py` (mesin status sesi demo: mulai, langkah, jeda, kecepatan, reset)
- `api/routers/demo.py` (`POST /demo/mulai`, `POST /demo/{id}/langkah`, `POST /demo/{id}/jeda`,
  `GET /demo/{id}/status`, `POST /demo/{id}/reset`)
- Kendali demo dan ringkasan akhir episode di `dashboard/src/TabOperasi.jsx`
- `simulation/skenario_cadangan.py` (skenario seed tetap → `data/processed/demo/skenario_cadangan.json`)
- `docs/naskah-demo.md` (langkah presentasi untuk penguji)
- `tests/test_demo.py`, `tests/test_api_demo.py`

**Kriteria selesai:**
- Alur mulai → langkah sampai T−0 → ringkasan berjalan tanpa internet.
- Status pada jam h tidak memuat data sesudah h.
- Reset (admin) hanya menghapus log bertanda `mode=demo` dari sesi itu.
- Skenario cadangan diputar dua kali memberi hasil identik (hash sama).
- Episode nyata 24 Jan 2025 dan episode sintetis tampil dengan labelnya.

### Tahap 10 · Uji menyeluruh, README, daftar asumsi

**Tujuan:** sistem siap diserahkan dan didemokan.

**File yang dibuat atau diperbarui:**
- `tests/test_alur_menyeluruh.py` (DB Docker → muat data → API → demo sampai ringkasan)
- `docs/keterlacakan.md` (matriks FR/NFR → modul → tes)
- `README.md` lengkap (pasang, jalankan, demo, uji, struktur, variabel env, batas klaim)
- `docs/asumsi.md` final, `docs/progress.md` laporan akhir

**Kriteria selesai:**
- `pytest` (termasuk marker `db`) dan `npm test` lulus; cakupan lapis inti (inference, gating,
  action, simulation) ≥ 80%.
- Uji asap mengikuti README dari awal berhasil.
- Setiap FR punya modul dan tes, atau alasan tertulis bila tidak diimplementasikan (misalnya FR-P2).
- Empat batas klaim (spesifikasi bagian 6) tercantum di README dan konsol.

---

## G. Risiko yang sudah terlihat

- Modul IMERG dan GSMaP tidak bisa diuji terhadap layanan aslinya tanpa kredensial; hanya diuji
  dengan fixture. Dicatat sebagai keterbatasan.
- Kode wilayah BMKG (adm4) untuk Gubug dan koordinat titik hulu Tuntang adalah perkiraan yang
  perlu diverifikasi tim.
- Seluruh parameter C, L, P, waktu siap, dan prior adalah dummy; hasil simulasi hanya
  menggambarkan perilaku model, bukan biaya nyata.
- Katalog E1–E6 belum lengkap, sehingga validasi lapis I dengan leave-one-episode-out pada data
  nyata terbatas; validasi utama memakai episode sintetis.
