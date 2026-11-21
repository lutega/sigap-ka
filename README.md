# SIGAP-KA

Sistem pendukung keputusan untuk pengendali operasi KA di koridor Brumbung–Karangjati
(Grobogan). SIGAP-KA menentukan **kapan** tiap tindakan kontinjensi banjir sebaiknya diputuskan.
Sistem hanya memberi usulan; keputusan ada di tangan operator, dan status jalur tetap ditetapkan
KAI berdasarkan pemeriksaan lapangan. Proyek Minor KS5203, ITB.

> Status: prototipe dalam pengembangan. Rencana tahap ada di `docs/rencana.md`,
> progres di `docs/progress.md`, asumsi di `docs/asumsi.md`.

## Prasyarat

- Python 3.11+ (di Windows: `py -3.12`)
- Docker Desktop (PostgreSQL 16 + TimescaleDB)
- Node.js 20+ (untuk dashboard, tahap 8)

## Pemasangan awal

```bash
# 1. Lingkungan Python
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt     # Windows (Git Bash)
# source .venv/bin/activate && pip install -r requirements-dev.txt  # Linux/macOS

# 2. Konfigurasi
cp .env.example .env          # lalu sesuaikan bila perlu

# 3. Database
docker compose up -d          # tunggu status healthy: docker ps
.venv/Scripts/python -m db.inisialisasi          # buat tabel, hypertable, agregat (idempoten)
# .venv/Scripts/python -m db.inisialisasi --reset  # hapus semua tabel lalu buat ulang
```

## Data (lapis S)

```bash
.venv/Scripts/python -m sensing.jalankan status                       # kesiapan tiap sumber
.venv/Scripts/python -m sensing.jalankan nasa_power --dari 2024-01-01  # unduh hujan harian (internet)
.venv/Scripts/python -m sensing.jalankan bmkg                         # unduh prakiraan BMKG terkini (internet)
.venv/Scripts/python -m sensing.jalankan manual                       # proses data/manual (Glapan, kejadian, jadwal)
.venv/Scripts/python -m sensing.jalankan muat                         # muat data/processed ke database (offline)
```

Data mentah disimpan di `data/raw/` (tidak di-commit), data olahan di `data/processed/` (di-commit,
sehingga database bisa diisi ulang tanpa internet), dan setiap pengambilan dicatat di
`data/processed/log_pengambilan.csv` serta tabel `log_pengambilan`. Berkas isian manual ada di
`data/manual/`. Sumber yang butuh akun (GPM IMERG: `EARTHDATA_TOKEN`; GSMaP: `JAXA_USER`,
`JAXA_PASSWORD`) dilewati bila kredensial kosong, dan sistem beralih ke cadangan berlabel.

## Simulasi dan episode

```bash
.venv/Scripts/python -m simulation.jalankan --preset base --n 300 --seed 42      # 6 kebijakan, 300 episode
.venv/Scripts/python -m simulation.jalankan --semua-preset --loeo 100 --sensitivitas --simpan-db
.venv/Scripts/python -m simulation.episode muat     # episode demo (nyata 24 Jan 2025, cadangan, sintetis) ke database
```

Hasil disimpan di `data/processed/simulasi/` (CSV biaya per episode dan JSON ringkasan) serta tabel
`hasil_simulasi` dan `simulasi_run`. Seed yang sama memberi hasil yang sama.

## API (FastAPI)

```bash
.venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8765
```

- Dokumentasi interaktif: http://127.0.0.1:8765/docs
- Login awal: `admin` / `admin` (dari `ADMIN_USER`/`ADMIN_PASSWORD`; ganti di luar demo, begitu juga
  `JWT_SECRET`). Admin dapat menambah operator lewat `/pengguna` atau dashboard.
- Semua endpoint selain `/auth/login` dan `/kesehatan` butuh header `Authorization: Bearer <token>`;
  `/pengguna`, `POST /simulasi`, dan reset demo khusus admin.
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
Setujui/Tolak, ringkasan T−0), **Data** (status sumber, hujan, muka air, kejadian, jadwal),
**Prediksi** (peluang per mekanisme, lama tutup, bukti utama), **Kurva pemicu** (slider C, L, P,
batas waktu), **Simulasi** (enam kebijakan, metrik deteksi, batas klaim). Admin juga melihat
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

Langkah lengkap presentasi ada di `docs/naskah-demo.md`.

## Menjalankan tes

```bash
.venv/Scripts/python -m pytest
cd dashboard && npm test
```

Tes bertanda `db` membutuhkan database dari `docker compose`; bila database tidak terjangkau,
tes itu dilewati (bukan lulus).

## Struktur

| Folder | Isi |
| --- | --- |
| `config/` | `params.json` (satu-satunya sumber parameter) dan pembaca `.env` |
| `db/` | Skema tabel dan hypertable TimescaleDB |
| `sensing/` | Lapis S: satu file per sumber data |
| `inference/` | Lapis I: peluang gangguan, mekanisme, lama tutup |
| `gating/` | Lapis G: cost-loss dan kurva pemicu |
| `action/` | Lapis A: papan tindakan dan log keputusan |
| `simulation/` | Episode, enam kebijakan, evaluasi |
| `api/`, `auth/` | REST API FastAPI dan login JWT |
| `dashboard/` | Konsol React + Vite + Recharts |
| `tests/` | pytest |
