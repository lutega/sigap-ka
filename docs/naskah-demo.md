# SIGAP-KA: Naskah Demo Ujian dan Presentasi

Mode demo memutar ulang satu episode banjir jam demi jam secara offline. Semua data dibaca dari
database lokal (spesifikasi 16). Penguji berperan sebagai pengendali operasi KA.

## 1. Persiapan (sekali, sebelum hari presentasi)

```bash
docker compose up -d
.venv/Scripts/python -m db.inisialisasi
.venv/Scripts/python -m sensing.jalankan muat                 # data nyata dari data/processed (tanpa internet)
.venv/Scripts/python -m simulation.episode muat               # episode nyata 24 Jan 2025, cadangan, sintetis
.venv/Scripts/python -m simulation.jalankan --semua-preset --loeo 100 --sensitivitas --simpan-db
.venv/Scripts/python dashboard/export_dashboard.py            # build konsol + cek angka konsol = model
.venv/Scripts/python -m simulation.skenario_cadangan --periksa   # harus "SAMA"
```

## 2. Sesaat sebelum presentasi

1. Pastikan Docker Desktop berjalan, lalu `docker compose up -d`.
2. Jalankan server: `.venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8765`.
3. Buka `http://127.0.0.1:8765/`, login `admin`/`admin`, buka tab Operasi sekali agar model lapis I
   terlatih dan episode termuat (permintaan pertama sekitar 5–10 detik).
4. Di Kelola pengguna, buat akun operator untuk penguji (mis. `penguji`).
5. Tidak perlu internet. Bila koneksi database lambat, tunggu permintaan pertama selesai; permintaan
   berikutnya dilayani dari memori.

## 3. Alur demo (penguji login sebagai operator)

1. Tab **Operasi** → pilih episode **Skenario cadangan presentasi** (sintetis, seed 2025).
   Label "data dummy" tampil di episode dan grafik.
2. Pilih kecepatan (disarankan 1 jam episode = 2 detik, yaitu 12 detik per jam keputusan), lalu
   **Mulai mode demo**. Lencana "mode demo" menandakan log keputusan dicatat dengan `mode=demo`.
3. Gunakan **Jeda** untuk berdiskusi, **Lompat ke jam berikutnya** untuk maju manual.
4. Di setiap jam, minta penguji membaca papan: status SIGAP, peluang vs kurva, sisa jam ke batas,
   alasan singkat, dan peringatan maladaptasi; lalu **Setujui** atau **Tolak** (dengan alasan).
5. Di **T−0** muncul ringkasan: biaya keputusan penguji vs biaya bila saran SIGAP diikuti, serta
   label terlalu awal, terlambat, sia-sia, atau tepat per tindakan.
6. Admin dapat **Reset demo** untuk mengulang. Reset hanya menghapus log demo sesi itu; log lain
   tidak tersentuh.

### Yang akan terlihat pada skenario cadangan (dari `data/processed/demo/skenario_cadangan.json`)

| Jam | Peluang | Mekanisme dominan | Putuskan sekarang | Terlambat |
| --- | --- | --- | --- | --- |
| T-72 | 31% | genangan | - | - |
| T-66 | 22% | genangan | - | - |
| T-60 | 45% | genangan | - | - |
| T-54 | 20% | genangan | - | - |
| T-48 | 28% | genangan | - | - |
| T-42 | 30% | genangan | - | - |
| T-36 | 49% | genangan | T1 | - |
| T-30 | 54% | gerusan | - | T1 |
| T-24 | 47% | gerusan | - | T1 |
| T-18 | 36% | genangan | T6 | T1, T9 |
| T-12 | 36% | genangan | T5, T7 | T1, T6, T9 |
| T-6 | 30% | genangan | T2, T5 | T1, T3, T4, T6, T7, T9 |
| T-0 | 26% | genangan | - | semua |

Hasil episode (kebenaran sintetis): terganggu, genangan, lama tutup skenario sedang. Bila penguji
tidak menyetujui apa pun, biayanya 3070 (juta rupiah, dummy); bila mengikuti saran SIGAP, 2110.
Skenario ini adalah episode terganggu pertama dari seed 2025 (tidak dipilih agar SIGAP tampak
baik): peluang model justru turun menjelang T−0, sehingga beberapa tindakan mahal tidak disarankan.
Ini contoh nyata keterbatasan model yang dapat dibahas.

Poin narasi:
- **T−72 s.d. T−42**: semua "Tunggu prakiraan berikutnya". Kurva pemicu masih tinggi karena menunggu
  prakiraan berikutnya bernilai (informasi membaik mendekati kejadian).
- **T−36**: batas waktu T1 (informasi penumpang). Kurva T1 sudah turun ke ambang (C+P)/(L+P) yang
  rendah, peluang 49% melewatinya → "Putuskan sekarang". Tindakan murah dipicu lebih awal.
- **T−18 s.d. T−6**: tindakan lain mencapai batas waktunya; yang tidak diputuskan menjadi
  "Terlambat". T9 (pembatalan) butuh peluang di atas sekitar 73% sehingga tidak disarankan.
- Tunjukkan tab **Kurva pemicu**: geser P (denda alarm palsu) dan lihat ambang naik (FR-P1).
- Tunjukkan tab **Simulasi**: enam kebijakan pada 300 episode dan batas klaim.

## 4. Episode nyata 24 Januari 2025

Pilih **Banjir malam 24 Januari 2025**. Hujan berasal dari NASA POWER (nyata), sedangkan prakiraan
dan muka air per jam sintetis (label "campuran"). Hasil episode belum terkonfirmasi, jadi ringkasan
T−0 menampilkan dua kemungkinan. Sampaikan temuan jujurnya: hujan NASA POWER di sel grid koridor
pada 24 Jan hanya sekitar 6 mm, sehingga peluang model tetap rendah (sekitar 10–16%) dan muka air
sintetis jauh di bawah nilai nyata 1970. Bukti hulu butuh IMERG/GSMaP atau data BBWS.

## 5. Pertanyaan penguji yang mungkin muncul

- *Apakah sistem menyatakan jalur aman?* Tidak. Status jalur ditetapkan KAI; sistem hanya
  mengusulkan kapan tindakan diputuskan.
- *Mengapa SIGAP hanya sedikit lebih murah dari cost-loss di batas waktu?* Keunggulannya bergantung
  pada biaya menunggu (diskon biaya awal). Dengan diskon dummy 2% per 6 jam, selisihnya 0–3%; pada
  5% sekitar 7%. Biaya keterlambatan nyata perlu digali dari praktisi KAI.
- *Dari mana angka biaya?* Dummy (params.json, juta rupiah). Jangkar nyata satu-satunya: refund
  Pekalongan Rp3,5 miliar untuk 124 perjalanan.
- *Apakah model memakai data masa depan?* Tidak. Fitur dihitung hanya dari data yang tersedia pada
  jam keputusan (latensi tiap sumber dihormati) dan diuji otomatis.

## 6. Cadangan tanpa Docker

Di mesin pengembang, jaringan Docker Desktop (localhost:5432) sempat lambat (0,3–0,7 detik per
perintah, 2–3 detik per koneksi) dan sesekali memutus koneksi. Siapkan cadangan SQLite sebelum hari H:

```bash
.venv/Scripts/python -m simulation.cadangan_sqlite        # sekitar 1 menit, berkas data/demo_cadangan.sqlite
DATABASE_URL=sqlite:///data/demo_cadangan.sqlite .venv/Scripts/python -m uvicorn api.main:app --host 127.0.0.1 --port 8765
```

Isi cadangan sama (data nyata olahan, tujuh episode demo, hasil simulasi tiga preset); demo 12 langkah
selesai dalam kurang dari 1 detik. Sebutkan bahwa basis data utama sistem tetap PostgreSQL +
TimescaleDB; SQLite hanya cadangan presentasi.

## 7. Bila ada gangguan saat presentasi

| Gejala | Tindakan |
| --- | --- |
| Konsol tidak bisa login | Periksa server uvicorn berjalan; database baru otomatis membuat admin/admin |
| Episode tidak muncul | Jalankan `python -m simulation.episode muat` |
| Database tidak terjangkau atau sangat lambat | `docker compose up -d`; bila tetap bermasalah, pakai cadangan SQLite (bagian 6) |
| Hasil skenario cadangan berbeda | `python -m simulation.skenario_cadangan --periksa`; bila params sengaja diubah, bangun ulang cuplikan |
