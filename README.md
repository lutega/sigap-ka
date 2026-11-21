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

## Menjalankan tes

```bash
.venv/Scripts/python -m pytest
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
