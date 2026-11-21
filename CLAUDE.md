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
