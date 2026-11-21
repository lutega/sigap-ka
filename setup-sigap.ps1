# setup-sigap.ps1 : menyiapkan perangkat dan repo SIGAP-KA
$ErrorActionPreference = 'Stop'
$Repo = 'C:\Lutfi\Kuliah\SMS1\IntelligenceforMultidisciplinarySystems\Tugas_besar_Pak-Armi\Program\sigap-ka'
# buat dulu repo kosong (private) bernama sigap-ka di github.com akun lutega
$Remote = 'https://github.com/lutega/sigap-ka.git'

# 1. Pasang alat bila belum ada (lewat winget)
function Pasang($cmd, $id) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Host "Memasang $id ..."
    winget install -e --id $id --accept-source-agreements --accept-package-agreements
  } else { Write-Host "$cmd sudah ada" }
}
Pasang git    'Git.Git'
Pasang python 'Python.Python.3.11'
Pasang node   'OpenJS.NodeJS.LTS'
Pasang docker 'Docker.DockerDesktop'
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { npm install -g @anthropic-ai/claude-code }

# 2. Buat repo dan folder
New-Item -ItemType Directory -Force -Path $Repo | Out-Null
Set-Location $Repo
if (-not (Test-Path .git)) { git init -b main | Out-Null }
# identitas akun pribadi khusus repo ini (bukan akun TVS)
git config user.name 'lutega'
git config user.email 'ldanuega.software@gmail.com'
if (-not (git remote | Select-String -Quiet 'origin')) { git remote add origin $Remote }
'docs','config','data\raw','data\processed','sensing','inference','gating','action','simulation','api\routers','auth','db','dashboard','tests' |
  ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

# 3. File dasar
@'
.env
__pycache__/
.venv/
node_modules/
data/raw/
*.pyc
'@ | Set-Content -Encoding UTF8 .gitignore

@'
PARAMS_FILE=config/params.json
PARAMS_PRESET=base
KEJADIAN_METODE=manual
SUMBER_HUJAN_HULU=gpm_imerg
DATA_DIR=data/processed
SIM_SEED=42
ADMIN_USER=admin
ADMIN_PASSWORD=admin
DATABASE_URL=postgresql://sigap:sigap@localhost:5432/sigap
'@ | Set-Content -Encoding UTF8 .env.example
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# 4. CLAUDE.md (isi sama dengan bagian Isi CLAUDE.md di dokumen ini)
@'
# SIGAP-KA
Sistem pendukung keputusan untuk pengendali operasi KA di koridor Brumbung-Karangjati.
Menentukan KAPAN tiap tindakan kontinjensi banjir diaktifkan. Proyek Minor KS5203, ITB.

## Wajib dibaca sebelum menulis kode
- docs/arsitektur.md
- docs/spesifikasi-fungsional.md (bagian 4 dan 8-16 acuan utama)
- docs/peran-agen.md

## Stack
- Python 3.11+, FastAPI, Pydantic, SQLAlchemy
- PostgreSQL + TimescaleDB lewat docker-compose
- pytest + FastAPI TestClient
- Frontend: React + Vite + Recharts di dashboard/, memanggil REST API

## Aturan kode
- Modular: satu sumber data = satu file di sensing/, satu lapis SIGAP = satu folder.
- Tiap file diawali komentar tujuan, lapis, sumber, masukan, keluaran, keterbatasan.
- Tiap fungsi punya docstring bahasa Indonesia.
- Modul sumber: ambil() -> ke_format_standar() -> cek_kualitas();
  kolom: waktu, lokasi, nilai, satuan, sumber, is_simulated.
- Parameter hanya dari config/params.json dan .env.
- Data dummy selalu is_simulated = true.
- Model hanya memakai informasi yang tersedia pada jam keputusan.
- Sistem TIDAK PERNAH menyatakan jalur aman.
- Jangan mengarang angka nyata; catat asumsi di docs/asumsi.md.

## Cara kerja
- Kerjakan per tahap sesuai docs/rencana.md; tulis tes dan jalankan pytest.
- Commit kecil setiap selesai satu langkah, lalu git push ke origin (GitHub pribadi lutega).
- Akhiri tiap tahap dengan laporan serah terima, catat di docs/progress.md, lalu LANJUT OTOMATIS bila tes lulus.
- Berhenti hanya bila buntu (data bersurat, keputusan lingkup, tes gagal 3 kali);
  tulis alasannya di docs/progress.md. Asumsi dicatat di docs/asumsi.md.
- Perbarui README.md setiap ada perubahan cara menjalankan.
'@ | Set-Content -Encoding UTF8 CLAUDE.md

# 5. Izin perintah Claude Code agar bisa berjalan tanpa ditunggui
New-Item -ItemType Directory -Force -Path .claude | Out-Null
@'
{
  "permissions": {
    "allow": [
      "Bash(python:*)", "Bash(pip:*)", "Bash(pytest:*)",
      "Bash(npm:*)", "Bash(npx:*)", "Bash(node:*)",
      "Bash(docker:*)", "Bash(docker compose:*)",
      "Bash(git add:*)", "Bash(git commit:*)", "Bash(git push:*)",
      "Bash(git status:*)", "Bash(git log:*)", "Bash(git diff:*)",
      "Edit", "Write", "Read"
    ],
    "deny": ["Bash(rm -rf:*)", "Bash(git push --force:*)"]
  }
}
'@ | Set-Content -Encoding UTF8 .claude\settings.json

# 6. Laptop tidak tidur saat dicolok charger
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0

# 7. Commit pertama
git add -A
git commit -m 'Kerangka awal repo SIGAP-KA' | Out-Null
git push -u origin main   # login sebagai lutega bila diminta
Write-Host ''
Write-Host 'Selesai. Langkah berikut:'
Write-Host '1) Ekspor 3 dokumen ke Markdown dan simpan di docs/ (arsitektur.md, spesifikasi-fungsional.md, peran-agen.md)'
Write-Host '2) Buka Docker Desktop sekali agar berjalan'
Write-Host "3) cd '$Repo' lalu jalankan: claude"
Write-Host '4) Tempel prompt pembuka dari dokumen panduan'