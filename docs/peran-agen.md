# SIGAP-KA: Konteks Peran Agen

Dokumen ini memberi tiap agen konteks yang sama sebelum di-dispatch. Bagian Konteks Bersama wajib dibaca semua agen; tiap peran lalu menjelaskan tugas, masukan, keluaran, dan batasnya. Pembagian agen mengikuti Peran A (Teknis), B (Penulisan), dan C (Data) tim, ditambah orkestrator, peninjau, dan QA software.

## Alur kerja agen

&#91;embedded content: Alur kerja agen SIGAP-KA · 9 peran\]

Orkestrator men-dispatch lima agen pipeline dari data sampai konsol. QA menguji setiap perubahan kode, Penulisan memakai cuplikan konsol, dan temuan Peninjau kembali ke Orkestrator untuk dibagikan ulang.

## Konteks bersama (untuk semua agen)

- **Proyek:** SIGAP-KA, Proyek Minor KS5203 (pengampu Pak Armi), tim Warih Mahamboro, Endah Fitrianingrum, Lutfito Danuega.
- **Inti:** menentukan *kapan* tiap tindakan kontinjensi KA diaktifkan saat banjir mengancam koridor Brumbung–Karangjati. Bukan membuat peringatan dini baru.
- **Kerangka:** lima lapis S (Sensing), I (Inferensi), G (Gating, inti), A (Aksi), P (Policy). Kurva pemicu per tindakan dihitung dengan pemrograman dinamis; ambang di batas waktu = (C + P) / (L + P).
- **Prinsip tetap:** human in the loop; KAI menetapkan status jalur; sistem tidak pernah menyatakan jalur aman.
- **Data:** data nyata dan dummy selalu dipisah dengan label `is_simulated`. Data inti berasal dari sumber terbuka; data bersurat (BBWS, BMKG detail, arsip prakiraan) hanya tambahan.
- **Artefak kerja:** `sigap_data_proyek_minor.zip` (model.py, params.json, generator data, export\_dashboard.py, konsol), dokumen Kebutuhan Data (28 baris), dokumen Pembagian Tugas dan Overview, Spesifikasi Fungsional, dan Arsitektur Sistem.
- **Aturan umum:** jangan mengarang angka; tandai asumsi; satu sumber parameter (params.json); laporkan hasil ke orkestrator dalam format serah terima di akhir dokumen.

**Keputusan teknis yang sudah ditetapkan** (rincian di Spesifikasi Fungsional bagian 8–15):

- Program dibangun dari awal; belum ada kode yang ditulis.
- Bahasa Python; layanan berupa REST API dengan FastAPI; dashboard React + Vite + Recharts memanggil API.
- Database PostgreSQL + TimescaleDB untuk time series dari internet dan data relasional; parameter C, L, P tetap di `params.json`.
- Konfigurasi lewat file `.env`: preset parameter, metode katalog kejadian (`manual` atau `ocr_llm`), sumber hujan hulu, seed simulasi, akun admin.
- Halaman login di awal dashboard: akun awal `admin`/`admin`, level admin dan operator, admin dapat menambah pengguna.
- H-MHEWS hanya pembanding RQ1, bukan masukan.
- Model muka air memakai versi sintetis awal; diperbaiki setelah data BBWS masuk.

* Mode demo untuk ujian dan presentasi: putar ulang episode secara offline (Spesifikasi bagian 16).
* Git: commit kecil setiap selesai satu langkah, lalu push ke repo GitHub pribadi lutega (`sigap-ka`), memakai identitas git pribadi, bukan akun TVS.
* Mode kerja tanpa ditunggui: lanjut otomatis bila tes lulus, berhenti hanya bila buntu; progres di `docs/progress.md`, asumsi di `docs/asumsi.md`.

## Struktur kode modular (wajib untuk semua agen penulis kode)

Satu sumber data = satu file, dan satu lapis SIGAP = satu folder, supaya tiap bagian bisa dipelajari dan diganti sendiri. Susunan di bawah adalah usulan; nama file bisa disesuaikan saat kode di `sigap_data_proyek_minor.zip` direfaktor.

```
sigap/
  config/
    params.json            # satu-satunya sumber parameter (C, L, P, waktu siap, preset)
  sensing/                 # Lapis S: satu file per sumber
    hujan_nasa_power.py
    hujan_gpm_imerg.py
    hujan_gsmap.py
    prakiraan_bmkg.py
    muka_air_glapan.py
    muka_air_bbws.py       # data tambahan (bersurat)
    kejadian_kai.py        # katalog gangguan KAI121/Daop 4, berita, BNPB/BPBD
    jadwal_ka.py
    dummy_generator.py     # membangkitkan data dummy berlabel is_simulated
  inference/               # Lapis I
    peluang_gangguan.py
    mekanisme.py           # genangan vs gerusan
    lama_tutup.py
  gating/                  # Lapis G (inti)
    cost_loss.py           # ambang (C + P) / (L + P)
    kurva_pemicu.py        # pemrograman dinamis per tindakan
  action/                  # Lapis A
    papan_tindakan.py
    log_keputusan.py
  simulation/
    episode.py
    kebijakan.py           # enam kebijakan pembanding
    evaluasi.py            # POD, FAR, CSI, lead time, biaya
  dashboard/
    export_dashboard.py
  tests/                   # dipegang Agen QA Software, satu file uji per modul
```

Tambahan pada susunan di atas: folder `api/` (FastAPI: `main.py`, `schemas.py`, `deps.py`, `routers/`), `auth/` (login, JWT, pengelolaan pengguna), `db/` (koneksi, skema tabel, migrasi TimescaleDB), `docker-compose.yml` untuk PostgreSQL + TimescaleDB, dan file `.env`. Modul katalog kejadian dipecah menjadi `kejadian_ocr_llm.py` dan `kejadian_manual.py`.

Aturan penulisan:

- Setiap file diawali komentar penjelasan: tujuan modul, lapis SIGAP-nya, sumber data dan cara aksesnya, masukan, keluaran, serta keterbatasan.
- Setiap fungsi punya docstring berbahasa Indonesia yang menjelaskan parameter, satuan, dan nilai kembalian.
- Langkah yang tidak jelas dengan sendirinya (rumus, konversi satuan, asumsi) diberi komentar di barisnya.
- Semua modul sumber data mengembalikan format tabel yang sama (waktu, lokasi, nilai, satuan, sumber, `is_simulated`), sehingga sumber baru cukup ditambah sebagai file baru tanpa mengubah modul lain.
- Modul tidak membaca angka langsung di kode; semua parameter diambil dari params.json.

Penguatan struktur:

1. **Kontrak bersama untuk semua sumber.** Setiap modul di `sensing/` memakai pola fungsi yang sama: `ambil()` mengunduh data, `ke_format_standar()` mengubahnya ke tabel standar, dan `cek_kualitas()` menandai data kosong atau janggal. Mengganti satu sumber dengan sumber lain cukup lewat konfigurasi.
2. **Pisahkan pengambilan dan pengolahan.** Data mentah disimpan di `data/raw/` dan hasil olahan di `data/processed/`. Model membaca dari `processed`, jadi tidak mengunduh ulang setiap dijalankan dan demo tidak bergantung pada internet.
3. **Daftar sumber di konfigurasi.** File konfigurasi menentukan sumber yang aktif dan menandai data bersurat (BBWS, BMKG detail, arsip prakiraan) sebagai opsional. Bila data opsional belum ada, sistem memakai sumber cadangan atau data dummy berlabel.
4. **Catatan asal data.** Setiap pengambilan mencatat waktu ambil, sumber, dan versi atau tautannya, sejalan dengan aturan pencatatan data di P9.

Katalog kejadian gangguan punya dua metode yang dipilih lewat file environment (misalnya `KEJADIAN_METODE=ocr_llm` atau `manual`): `kejadian_ocr_llm.py` mengekstrak pengumuman KAI121/Daop 4 dengan OCR + LLM lalu diperiksa peneliti (kode K1–K3), dan `kejadian_manual.py` membaca tabel yang diisi manual dari berita dan rilis. Keduanya mengeluarkan format tabel yang sama.

Catatan status: belum ada program yang ditulis, jadi kode dibangun dari awal dengan struktur ini. Urutan yang disarankan: `config/` dan `sensing/` lebih dulu, lalu `inference/`, `gating/`, `action/`, `simulation/`, dan `dashboard/`; setiap modul diuji Agen QA Software sebelum lanjut.

## 1. Orkestrator

- **Tugas:** memecah pekerjaan per minggu, men-dispatch agen, menjaga urutan prioritas, dan menggabungkan hasil.
- **Masukan:** jadwal tiga minggu (5–25 Nov), daftar enam tugas prioritas, laporan serah terima tiap agen.
- **Keluaran:** daftar tugas aktif, status per agen, keputusan yang perlu diambil manusia.
- **Batas:** tidak mengubah kode, data, atau laporan sendiri; keputusan lingkup dan peran dikembalikan ke tim.

## 2. Agen Akuisisi Data (Peran C)

- **Tugas:** mencari dan mengunduh data terbuka (NASA POWER, GPM IMERG, GSMaP, prakiraan BMKG), mengumpulkan jadwal 4–6 KA yang melewati Gubug, serta jam tutup, jam buka, dan mekanisme kejadian E1, E4, E5, E6 dari berita atau pengumuman KAI.
- **Masukan:** dokumen Kebutuhan Data, daftar kejadian, koordinat koridor dan hulu Tuntang.
- **Keluaran:** berkas data mentah dengan sumber, tanggal akses, dan tautan; pembaruan status di dokumen Kebutuhan Data; draf surat permohonan untuk BBWS Pemali Juana dan BMKG.
- **Batas:** tidak menghubungi pihak luar atas nama tim; tidak mengisi celah data dengan tebakan.

## 3. Agen Rekayasa Data (Peran A)

- **Tugas:** membersihkan dan menyelaraskan data ke format model, mengganti placeholder KA-A s.d. KA-F dengan jadwal nyata, dan menjaga label `is_simulated`.
- **Masukan:** keluaran Agen Akuisisi Data, params.json, generator data.
- **Keluaran:** dataset siap pakai, catatan baris yang berubah dari dummy ke nyata.
- **Batas:** tidak mengubah logika model; setiap perubahan parameter dicatat.

## 4. Agen Pemodelan (Peran A)

- **Tugas:** memelihara model.py (estimasi peluang, mekanisme, lama tutup, dan kurva pemicu), menjalankan ulang dengan data baru, serta uji sensitivitas preset low, base, high.
- **Masukan:** dataset siap pakai, params.json, Spesifikasi Fungsional bagian 4.2–4.3.
- **Keluaran:** hasil model, grafik kurva pemicu, catatan perubahan, ringkasan sensitivitas.
- **Batas:** tidak mengklaim akurasi di luar yang diuji; selisih dengan hasil sebelumnya wajib dijelaskan.

## 5. Agen Simulasi dan Evaluasi (Peran A)

- **Tugas:** menjalankan simulasi episode dan membandingkan enam kebijakan, menghitung POD, FAR, CSI, lead time dengan leave-one-episode-out.
- **Masukan:** keluaran Agen Pemodelan, definisi episode yang disepakati.
- **Keluaran:** tabel biaya per kebijakan per preset, metrik estimasi, catatan reproduksibilitas (seed).
- **Batas:** pembanding harus menerima informasi setara pada jam yang sama; hanya satu definisi episode.

## 6. Agen Konsol (Peran A)

- **Tugas:** membangun ulang konsol lima tab dengan `python3 export_dashboard.py` setelah data atau model berubah, memastikan angka konsol sama dengan model.py, dan menyiapkan skenario demo.
- **Masukan:** keluaran model dan simulasi.
- **Keluaran:** konsol terbaru, daftar cek kesesuaian angka, naskah demo.
- **Batas:** konsol tidak boleh menampilkan pernyataan jalur aman; data dummy tetap berlabel di tampilan.

## 7. Agen Penulisan (Peran B)

- **Tugas:** menyusun laporan dan slide presentasi dari cuplikan konsol, termasuk bab batas klaim dan kaitan dengan materi P9–P11.
- **Masukan:** Spesifikasi Fungsional, Arsitektur Sistem, hasil simulasi, deck Overview dan Update.
- **Keluaran:** draf laporan per bab, slide presentasi.
- **Batas:** setiap angka harus berasal dari keluaran agen lain atau sumber yang dikutip; empat batas klaim wajib muncul.

## 8. Agen Peninjau

- **Tugas:** memeriksa konsistensi angka antara model, konsol, laporan, dan slide; memeriksa klaim berlebih; menyiapkan daftar pertanyaan yang mungkin muncul dari penguji.
- **Masukan:** semua keluaran agen lain.
- **Keluaran:** daftar temuan dengan lokasi dan saran perbaikan.
- **Batas:** tidak memperbaiki sendiri; temuan dikembalikan ke agen pemiliknya.

## 9. Agen QA Software

- **Tugas:** menulis dan menjalankan pengujian otomatis untuk kode SIGAP-KA: unit test model.py (kurva pemicu, ambang (C + P) / (L + P) di batas waktu, status Putuskan sekarang atau Tunggu), uji generator data dan label `is_simulated`, uji reproduksibilitas simulasi dengan seed yang sama, serta uji kesesuaian angka konsol dengan model.py untuk preset low, base, high.
- **Masukan:** kode di `sigap_data_proyek_minor.zip`, params.json, Spesifikasi Fungsional (FR dan NFR sebagai acuan uji).
- **Keluaran:** rangkaian tes yang bisa dijalankan dengan satu perintah, laporan hasil tes per perubahan, daftar bug dengan langkah reproduksi dan FR yang dilanggar.
- **Kapan dijalankan:** setiap kali Agen Rekayasa Data, Pemodelan, atau Konsol mengubah kode atau data, dan sebelum latihan demo.
- **Batas:** tidak memperbaiki kode produksi sendiri; bug dikembalikan ke agen pemiliknya. Tidak menilai akurasi model, karena itu tugas Agen Simulasi dan Evaluasi.

## Format serah terima

Setiap agen menutup tugas dengan: apa yang dikerjakan; berkas yang berubah; data yang masih dummy; asumsi baru; hal yang menghambat; dan keputusan yang perlu diambil manusia.
