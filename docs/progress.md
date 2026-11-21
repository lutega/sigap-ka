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
