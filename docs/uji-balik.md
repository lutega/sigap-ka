# Uji balik pada hujan nyata (IMERG Late) dan kejadian kandidat

Perintah: `python -m simulation.uji_balik`. Run selesai sekitar 40 detik dan menulis hasil ke
`data/processed/uji_balik/`:

- `kandidat.csv`
- `kepekaan_bias.csv`
- `pindai_harian.csv`
- `ringkasan.json`

Status: **bukan validasi resmi.** Ada tiga alasan:

- Label kejadian berasal dari berita (kandidat, A-055).
- Model lapis I dilatih pada episode sintetis (A-026).
- Muka air per jam masih sintetis.

Angka di bawah memakai preset base dan prakiraan persistensi, yang hanya memakai informasi yang
tersedia pada jam keputusan (A-058).

## 1. Kandidat satu per satu

Keterangan kolom:

- **Hulu 72 j aktual**: hujan yang benar-benar turun dalam 72 jam sebelum T-0 (diagnosis saja).
- **Hulu 3 hari tersedia**: hujan yang sudah bisa dilihat model pada T-0.

| ID | T-0 | Hulu 72 j aktual (mm) | Hulu 3 hari tersedia (mm) | p T-24 | p T-0 | p maks (T-72..T-0) | Rencana SIGAP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| K01 | 6 Feb 2024 00.00 | 94 | 96 | 0,17 | 0,20 | 0,20 | T1@T-36; T5@T-6 |
| K02 | 21 Jan 2025 00.00 | 90 | 68 | 0,13 | 0,19 | 0,19 | T1@T-36; T5@T-6 |
| K03 | 24 Jan 2025 22.25 | 41 | 45 | 0,22 | 0,06 | 0,82 | T1@T-42; T2@T-6; T5@T-6 |
| K04 | 9 Mar 2025 05.27 | 74 | 35 | 0,15 | 0,15 | 0,16 | T5@T-6 |
| K05 | 18 Jun 2025 03.11 | 21 | 10 | 0,06 | 0,08 | 0,08 | – |
| K06 | 21 Okt 2025 18.00 | 36 | 9 | 0,09 | 0,10 | 0,12 | – |
| K07 | 16 Feb 2026 04.35 | 79 | 40 | 0,11 | 0,15 | 0,22 | T1@T-36; T5@T-6 |
| K08 | 16 Feb 2026 11.43 | 83 | 40 | 0,14 | 0,10 | 0,21 | T1@T-36; T5@T-6 |
| K09 | 3 Apr 2026 01.45 | 51 | 43 | 0,09 | 0,09 | 0,13 | T1@T-36 |

## 2. Pemindaian harian 2024–2026

Pengaturan:

- T-0 pukul 12.00 WIB setiap hari, 1.044 hari.
- 8 hari kejadian.
- 992 hari "lain".
- 44 hari dalam ±3 hari dari kejadian dibuang dari pembanding.

| Skor | AUC (hari kejadian vs hari lain) |
| --- | --- |
| Peluang SIGAP pada T-0 | 0,83 |
| Peluang SIGAP pada T-24 | 0,79 |
| Hujan hulu 3 hari yang **tersedia** pada T-0 (tanpa model) | 0,79 |
| Hujan hulu 72 jam yang **benar-benar turun** (tidak tersedia saat itu) | 0,87 |
| Hujan lokal 72 jam yang benar-benar turun | 0,84 |

Sebaran skor pada kedua kelompok hari:

- **Median peluang T-0:** 0,11 pada hari kejadian, 0,063 pada hari lain.
- **Ambang 0,3:** tidak ada hari kejadian yang mencapainya. Hari lain melewati 0,3 sekitar 7 kali
  per tahun dan 0,5 sekitar 1 kali per tahun.
- **Rencana SIGAP:** minimal satu tindakan pada 5 dari 8 hari kejadian, dan pada 34% hari lain.
  Kebanyakan tindakan itu T1 (murah).

## 3. Kepekaan terhadap bias IMERG

Seluruh hujan dikalikan 0,79; 0,8; 0,852; 1,0; dan 1,2. Faktor 1/1,266 dan 1/1,174 diambil dari
validasi Semarang (A-054).

- **Peluang T-0** bergeser paling banyak sekitar 0,1. Contoh: K01 naik dari 0,15 ke 0,26 dari skala
  0,79 sampai 1,2.
- **Rencana SIGAP** sebagian besar tetap.
  - Pada skala ≤ 0,852, K01 kehilangan T5 dan K08 kehilangan T1.
  - Pada skala 1,2, K03 memicu T1 sejak T-72 dan K06 memicu T5.
- **Kesimpulan:** bias IMERG ±20% tidak mengubah urutan kejadian, tetapi menggeser tindakan yang
  berada dekat ambang.

## 4. Temuan

1. **Urutan benar, skala belum.** Model memberi peluang lebih tinggi pada hari kejadian (AUC 0,83).
   Namun nilainya rendah, maksimum sekitar 0,2 pada T-0. Penyebabnya, skala peluang diturunkan dari
   generator sintetis. Kalibrasi butuh label nyata yang terverifikasi (E1–E6 dan kandidat).
2. **Model belum jauh melampaui hujan mentah.** AUC 0,83 dibanding 0,79 untuk hujan hulu tersedia.
   Fitur muka air dan prakiraan belum menambah banyak karena muka air masih sintetis dan prakiraan
   hanya persistensi.
3. **Latensi data adalah batas utama.** Hujan yang benar-benar turun memisahkan lebih baik (0,87)
   daripada hujan yang tersedia, karena IMERG Late harian baru bisa dipakai 14–38 jam kemudian
   (A-057).
   - Contoh K03: hujan besar 24 Jan belum terlihat pada T-0 22.25.
   - Peluang tinggi K03 di awal horizon berasal dari hujan 20–21 Jan, yang juga memicu K02.
   - Data setengah jam IMERG atau pos hujan/TMA telemetri BBWS akan memperpendek jeda ini.
4. **Ada kejadian yang tidak dipicu hujan.** K05 (tanggul jebol, Jun 2025) dan K06 (Okt 2025)
   terjadi dengan hujan hulu tersedia sekitar 10 mm, sehingga tidak terdeteksi dari hujan saja. Ini
   sejalan dengan catatan E3 pada spesifikasi (gangguan dengan hujan lokal rendah).
5. **Hari "lain" berpeluang tinggi belum tentu alarm palsu.** Contohnya 24–28 Okt 2025: hujan hulu
   72 jam sampai 200 mm dan peluang sampai 0,75. Pada 28 Okt 2025 ada banjir yang mengganggu jalur
   Semarang Tawang–Alastua (di luar koridor). Untuk koridor Brumbung–Karangjati belum ditemukan
   berita gangguan pada tanggal itu.

## 5. Realisme generator dummy (penyebab peluang rendah)

Perintah: `python -m simulation.realisme_generator` (jalankan sesudah uji balik). Hasil ditulis ke
`data/processed/uji_balik/realisme_generator.csv` dan `realisme_kelas_hujan.csv`.

Yang dibandingkan: 400 episode latih lapis I dari generator dummy, 1.044 hari nyata IMERG Late, dan
8 hari kejadian kandidat. Median tiap besaran:

| Besaran (median) | Episode latih sintetis | Semua hari nyata | Hari kejadian kandidat |
| --- | --- | --- | --- |
| Hujan hulu 72 jam (mm) | 81 | 12,5 | 66 |
| Hujan hulu 3 hari tersedia pada T-0 (mm) | 80 | 12 | 42 |
| Hujan lokal 3 hari tersedia pada T-0 (mm) | 69 | 11 | 44 |
| Glapan relatif Awas pada T-0 (cm) | −63 | −187 | −104 |

- **Episode latih jauh lebih basah daripada hari nyata.** Median hujan hulu 72 jam episode
  sintetis (81 mm) setara persentil 98 hari nyata. Sebanyak 36% episode sintetis melewati 100 mm,
  padahal hanya 2 hari nyata (0,2%) yang mencapainya.
- **Kejadian nyata terjadi pada hujan sedang.** Pada hujan 40–100 mm, model kebenaran generator
  hanya memberi peluang gangguan 6–29%. Akibatnya model belajar bahwa gangguan butuh hujan lebih
  besar daripada yang terlihat pada kejadian nyata.
- **Muka air sintetis dari hujan nyata tetap jauh di bawah Awas.** Medianya −104 cm pada hari
  kejadian, sedangkan Glapan nyata 25 Jan 2025 mencapai +65 cm. Episode latih yang terganggu sering
  melewati Awas.

Frekuensi gangguan per kelas hujan hulu 72 jam (nyata = porsi hari dengan kejadian kandidat; hari
"sekitar" dibuang):

| Hujan hulu 72 jam | Episode sintetis (n) | Terganggu sintetis | Hari nyata (n) | Hari kejadian nyata |
| --- | --- | --- | --- | --- |
| 0–20 mm | 5 | 0% | 589 | 1 (0,2%) |
| 20–40 mm | 37 | 0% | 233 | 1 (0,4%) |
| 40–60 mm | 83 | 6% | 122 | 2 (1,6%) |
| 60–80 mm | 72 | 15% | 39 | 1 (2,6%) |
| 80–100 mm | 58 | 29% | 15 | 2 (13%) |
| ≥ 100 mm | 145 | 55% | 2 | 1 (50%) |

Satuannya berbeda: episode sintetis dihitung per kejadian, data nyata per hari. Data nyata hanya
punya 8 kejadian. Karena itu tabel ini hanya menunjukkan arah. Pada hujan tinggi, frekuensi
sintetis dan nyata mirip. Pada hujan sedang, generator memberi frekuensi lebih tinggi per episode,
tetapi episode sedang itu jarang dilatihkan.

Pilihan tindak lanjut, keduanya keputusan tim karena parameter generator berstatus dummy
(A-001, A-010, A-061):

- **(a) Kalibrasi ulang keluaran model.** Generator dipertahankan sebagai skenario uji tekanan,
  lalu peluang keluaran model dikalibrasi ulang (mis. Platt/isotonik) dengan label nyata
  terverifikasi.
- **(b) Parameterisasi ulang generator.** Median badai disesuaikan dengan sebaran hari basah
  IMERG, dan intersep model kebenaran diturunkan agar gangguan muncul pada 40–100 mm. Setelah itu
  lapis I dilatih ulang dan simulasi kebijakan diulang.

## 6. Batas klaim

- n = 8 hari kejadian, semuanya kandidat.
- Hari tanpa berita belum tentu tanpa gangguan.
- AUC dan frekuensi ambang di atas hanya gambaran kemampuan membedakan hari, bukan janji kinerja
  operasional.
- Sistem tidak menyatakan jalur bebas risiko pada hari berpeluang rendah.
