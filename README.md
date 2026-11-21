# SIGAP-KA

Sistem pendukung keputusan untuk pengendali operasi KA di koridor Brumbung–Karangjati
(Grobogan). SIGAP-KA menentukan **kapan** tiap tindakan kontinjensi banjir sebaiknya diputuskan,
dengan lima lapis: S (Sensing), I (Inferensi), G (Gating, inti), A (Aksi), P (Policy). Sistem hanya
memberi usulan; keputusan ada di tangan operator, dan status jalur tetap ditetapkan KAI berdasarkan
pemeriksaan lapangan. Proyek Minor KS5203, ITB.

> **Status:** prototipe lengkap tahap 0–10 (`docs/rencana.md`). Parameter biaya dan generator
> episode masih **dummy**. Progres dan laporan serah terima: `docs/progress.md`. Asumsi:
> `docs/asumsi.md`. Keterlacakan kebutuhan → modul → tes: `docs/keterlacakan.md`. Naskah demo:
> `docs/naskah-demo.md`.

## Mulai cepat (dari klon baru sampai konsol berjalan)

```bash
# Prasyarat: Python 3.11+ (Windows: py -3.12), Docker Desktop, Node.js 20+
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt     # Linux/macOS: .venv/bin/python
cp .env.example .env

docker compose up -d                                   # PostgreSQL 16 + TimescaleDB, tunggu "healthy"
.venv/Scripts/python -m db.inisialisasi                # tabel, hypertable, continuous aggregate
.venv/Scripts/python -m sensing.jalankan muat          # data olahan nyata (repo) -> database, offline
.venv/Scripts/python -m simulation.episode muat        # episode demo -> database
.venv/Scripts/python -m simulation.jalankan --semua-preset --loeo 100 --sensitivitas --simpan-db
.venv/Scripts/python dashboard/export_dashboard.py     # build konsol + cek angka konsol = model

.venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8765
# buka http://127.0.0.1:8765/  -> login admin / admin
```

## Konfigurasi (`.env`)

| Variabel | Bawaan | Arti |
| --- | --- | --- |
| `PARAMS_FILE` | `config/params.json` | Satu-satunya sumber parameter (C, L, P, waktu siap, prior, generator) |
| `PARAMS_PRESET` | `base` | Preset `low`, `base`, atau `high` |
| `KEJADIAN_METODE` | `manual` | Katalog kejadian `manual` atau `ocr_llm` |
| `SUMBER_HUJAN_HULU` | `gpm_imerg` | Sumber hujan hulu pertama; cadangan otomatis GSMaP → NASA POWER → dummy |
| `DATA_DIR` | `data/processed` | Data olahan yang dibaca model |
| `SIM_SEED` | `42` | Seed simulasi (hasil dapat diulang) |
| `ADMIN_USER`, `ADMIN_PASSWORD` | `admin`, `admin` | Akun awal (dibuat bila tabel pengguna kosong); ganti di luar demo |
| `DATABASE_URL`, `DATABASE_URL_TEST` | `postgresql://sigap:sigap@localhost:5432/sigap(_test)` | Database utama dan uji |
| `JWT_SECRET`, `JWT_MENIT_KEDALUWARSA` | nilai pengembangan, `480` | Token login; **ganti rahasia di luar demo** |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Origin dashboard mode pengembangan |
| `EARTHDATA_TOKEN`, `JAXA_USER`, `JAXA_PASSWORD` | kosong | Kredensial opsional IMERG/GSMaP |
| `ANTHROPIC_API_KEY`, `LLM_MODEL`, `TESSERACT_CMD` | kosong, `claude-opus-5-5`, kosong | Metode katalog `ocr_llm` (opsional) |

## Data (lapis S)

```bash
.venv/Scripts/python -m sensing.jalankan status                       # kesiapan tiap sumber
.venv/Scripts/python -m sensing.jalankan nasa_power --dari 2024-01-01  # unduh hujan harian (internet)
.venv/Scripts/python -m sensing.jalankan imerg --dari 2024-01-01       # IMERG Late + Final lewat Giovanni (token Earthdata)
.venv/Scripts/python -m sensing.jalankan bmkg                         # unduh prakiraan BMKG terkini (internet)
.venv/Scripts/python -m sensing.jalankan manual                       # proses data/manual (Glapan, kejadian, jadwal)
.venv/Scripts/python -m sensing.jalankan muat                         # muat data/processed ke database (offline)
```

Data mentah disimpan di `data/raw/` (tidak di-commit), data olahan di `data/processed/` (di-commit,
sehingga database bisa diisi ulang tanpa internet), dan setiap pengambilan dicatat di
`data/processed/log_pengambilan.csv` serta tabel `log_pengambilan`. Berkas isian manual ada di
`data/manual/`. Sumber yang butuh akun (GPM IMERG: `EARTHDATA_TOKEN`; GSMaP: `JAXA_USER`,
`JAXA_PASSWORD`) dilewati bila kredensial kosong, dan sistem beralih ke cadangan berlabel.

| Data | Status |
| --- | --- |
| Hujan harian GPM IMERG Late 2024-01-01 s.d. 2026-11-18 dan Final s.d. 2025-09-30 (lokal, hulu, Gundih, sel 0,1°) | nyata; hulu terpisah dari lokal; Late dipakai episode nyata |
| Hujan harian NASA POWER 2024-01-01 s.d. 2026-11-20 (lokal, hulu, Gundih) | nyata (satu sel grid untuk ketiga titik; cadangan) |
| Prakiraan BMKG Desa Penadaran, Kec. Gubug | nyata, terkini saja (tanpa arsip) |
| Muka air Glapan 1970 (24 Jan 2025), ambang Awas 1905 | nyata, satu titik |
| Katalog E1–E6 | kerangka; jam tutup/buka/mekanisme belum terisi |
| Jadwal KA | placeholder KA-A s.d. KA-F (dummy) |
| Parameter C, L, P, waktu siap, prior, episode sintetis, muka air sintetis | dummy |

## Simulasi dan episode

```bash
.venv/Scripts/python -m simulation.jalankan --preset base --n 300 --seed 42      # 6 kebijakan, 300 episode
.venv/Scripts/python -m simulation.jalankan --semua-preset --loeo 100 --sensitivitas --simpan-db
.venv/Scripts/python -m simulation.episode muat     # episode demo (nyata 24 Jan 2025, cadangan, sintetis) ke database
```

Hasil disimpan di `data/processed/simulasi/` (CSV biaya per episode dan JSON ringkasan) serta tabel
`hasil_simulasi` dan `simulasi_run`. Seed yang sama memberi hasil yang sama.

Hasil utama (300 episode sintetis, seed 42, parameter dummy): SIGAP termurah di antara kebijakan
yang tidak mengetahui hasil, tetapi selisihnya terhadap cost-loss di batas waktu kecil (low −1,9%,
base −0,01%, high −3,3%). Keunggulan itu bergantung pada biaya menunggu (diskon biaya bertindak
lebih awal); lihat `docs/progress.md` tahap 6.

## API (FastAPI)

```bash
.venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8765
```

- Dokumentasi interaktif: http://127.0.0.1:8765/docs
- Login awal: `admin` / `admin` (dari `ADMIN_USER`/`ADMIN_PASSWORD`; ganti di luar demo, begitu juga
  `JWT_SECRET`). Admin dapat menambah operator lewat `/pengguna` atau dashboard.
- Semua endpoint selain `/auth/login` dan `/kesehatan` butuh header `Authorization: Bearer <token>`;
  `/pengguna`, `POST /simulasi`, dan reset demo khusus admin.
- Parameter `jam` dinyatakan sebagai jam sebelum T−0 (mis. `jam=24` berarti T−24).
- Port 8765 dipakai karena port 8000 di mesin pengembang sudah terpakai proses lain.
- Permintaan pertama per preset melatih model lapis I (sekitar 5 detik); episode dimuat sekali lalu
  disimpan di memori.

## Konsol (dashboard React + Vite + Recharts)

Satu perintah membangun konsol dan memeriksa bahwa angka konsol sama dengan model untuk tiap preset:

```bash
.venv/Scripts/python dashboard/export_dashboard.py      # npm install (sekali) + npm run build + cek kesesuaian
.venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8765
# buka http://127.0.0.1:8765/  (login admin/admin)
```

Pengembangan antarmuka dengan muat ulang otomatis:

```bash
cd dashboard
npm install
npm run dev        # http://localhost:5173, permintaan API diteruskan ke port 8765
npm test           # vitest
```

Lima tab: **Operasi** (putar ulang episode, peluang vs kurva pemicu, papan 9 tindakan dengan
Setujui/Tolak, ringkasan T−0, mode demo), **Data** (status sumber, hujan, muka air, kejadian,
jadwal), **Prediksi** (peluang per mekanisme, lama tutup, bukti utama), **Kurva pemicu** (slider C,
L, P, batas waktu), **Simulasi** (enam kebijakan, metrik deteksi, batas klaim). Admin juga melihat
**Kelola pengguna**. Setiap grafik punya tampilan tabel; data nyata/dummy selalu berlabel.

## Mode demo (ujian dan presentasi)

Putar ulang episode jam demi jam secara offline dari tab Operasi → **Mulai mode demo** (kendali:
lompat ke jam berikutnya, jeda/lanjutkan, kecepatan; reset khusus admin). Endpoint:
`POST /demo/mulai`, `POST /demo/{id}/langkah`, `POST /demo/{id}/jeda`, `GET /demo/{id}/status`,
`POST /demo/{id}/reset`. Log keputusan demo ditandai `mode=demo`.

Skenario cadangan presentasi (seed tetap, hasil selalu sama):

```bash
.venv/Scripts/python -m simulation.skenario_cadangan            # bangun cuplikan + sidik SHA-256
.venv/Scripts/python -m simulation.skenario_cadangan --periksa  # pastikan masih sama
```

Cadangan bila Docker/TimescaleDB bermasalah saat presentasi (satu berkas SQLite berisi data nyata,
episode demo, dan hasil simulasi; tidak menggantikan TimescaleDB):

```bash
.venv/Scripts/python -m simulation.cadangan_sqlite
DATABASE_URL=sqlite:///data/demo_cadangan.sqlite .venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8765
```

Langkah lengkap presentasi ada di `docs/naskah-demo.md`.

## Modul input dan fitur modular (`src/sigap_ka/`)

Satu modul per sumber, keluaran berskema `tanggal, zona, nilai, sumber, status_data`
(`inputs/base.py`, dengan adapter ke tabel standar lama):

```bash
export PYTHONPATH=src                                   # pytest sudah mengaturnya sendiri
.venv/Scripts/python -m sigap_ka.inputs.bmkg            # data/raw/bmkg/*.csv|xlsx -> data/interim/bmkg_clean.csv
.venv/Scripts/python -m sigap_ka.features.hujan         # -> data/processed/hujan_features.csv
.venv/Scripts/python -m sigap_ka.features.glapan        # -> data/interim/glapan_tma_synth.csv + data/processed/glapan_features.csv
```

- **BMKG** (`inputs/bmkg.py`): membaca berkas portal/salinan BMKG, kode 8888/9999, nilai negatif,
  dan tanggal ganda yang bertentangan menjadi NaN; stasiun dipetakan ke zona lewat
  `config/stasiun_bmkg.json`. Stasiun Kota Semarang dipetakan ke `semarang_pembanding` (pembanding
  IMERG), bukan ke zona lokal/hulu/Gundih.
- **Fitur hujan** (`features/hujan.py`): `hujan_lokal_1d/3d/5d`, `hujan_hulu_3d`,
  `hujan_gundih_1d/3d`; per zona dipakai BMKG bila ada, selain itu IMERG Late (sumber dicatat).
- **TMA Glapan sintetis** (`inputs/glapan_synth.py`): dua waduk linear (aliran dasar ala API dan
  lonjakan banjir) dengan anchoring opsional ke titik nyata (1970 pada 24 Jan 2025);
  `status_data = sintetis`. Fitur `glapan_relatif` (TMA − 1905) dan `tren_glapan_6j`
  ada di `features/glapan.py`.

## Menjalankan tes

```bash
.venv/Scripts/python -m pytest                       # backend (unit, API, integrasi TimescaleDB bertanda db)
.venv/Scripts/python -m pytest -m "not db"           # tanpa database Docker
.venv/Scripts/python -m pytest --cov --cov-report=term-missing
cd dashboard && npm test                             # konsol (vitest)
```

Tes bertanda `db` membutuhkan database dari `docker compose`; bila database tidak terjangkau,
tes itu dilewati (bukan lulus). Di Windows, tes database memakai koneksi baru per operasi karena
penerus port Docker Desktop dapat meninggalkan koneksi "setengah terbuka".

Bila koneksi `localhost:5432` dari host lambat atau terputus (terjadi di mesin pengembang), jalankan
seluruh tes di dalam jaringan Docker:

```bash
docker compose --profile uji run --rm uji      # pip install + pytest lengkap di kontainer Python
```

## Batas klaim (wajib disebut)

1. Keunggulan SIGAP adalah batas atas menurut asumsi model sendiri; uji penentu butuh prakiraan nyata.
2. Muka air dummy meleset: model lama 1768; model sintetis saat ini (hujan hulu IMERG) 1763 pada
   24 Jan 2025 dengan puncak 1875 pada horizon episode, vs nyata 1970 (ambang Awas 1905).
3. Dua kejadian (E3, E6) terjadi dengan hujan lokal rendah, sehingga perlu bukti dari hulu; IMERG
   memisahkan hulu dari lokal, tetapi baru satu sel grid (belum rerata daerah tangkapan).
4. Laporan memakai satu definisi episode hujan lebat (horizon 72 jam, keputusan tiap 6 jam).

## Struktur

| Folder | Isi |
| --- | --- |
| `config/` | `params.json` (satu-satunya sumber parameter) dan pembaca `.env` |
| `db/` | Koneksi, skema tabel, hypertable, continuous aggregate, repositori |
| `sensing/` | Lapis S: satu file per sumber data, registri cadangan, generator dummy, CLI |
| `inference/` | Lapis I: fitur tanpa intip masa depan, peluang gangguan, mekanisme, lama tutup |
| `gating/` | Lapis G: cost-loss, kurva pemicu (pemrograman dinamis), status tindakan |
| `action/` | Lapis A: papan tindakan, log keputusan, ringkasan T−0, penjaga klaim |
| `simulation/` | Episode, enam kebijakan, evaluasi, mode demo, skenario cadangan |
| `api/`, `auth/` | REST API FastAPI, login JWT, kelola pengguna |
| `dashboard/` | Konsol React + Vite + Recharts, `export_dashboard.py` |
| `data/` | `manual/` (isian tim), `processed/` (olahan, di-commit), `raw/` (tidak di-commit) |
| `tests/` | pytest (satu berkas per modul/lapis) |
| `docs/` | Spesifikasi, rencana, progres, asumsi, keterlacakan, naskah demo |
