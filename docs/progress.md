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
