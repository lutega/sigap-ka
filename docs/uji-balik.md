# Uji balik pada hujan nyata (IMERG Late) dan kejadian kandidat

## Cara menjalankan

```bash
.venv/Scripts/python -m simulation.uji_balik             # sekitar 7-8 menit untuk 3 sumber hujan
.venv/Scripts/python -m simulation.realisme_generator    # sesudah uji balik
```

Hasil ditulis ke `data/processed/uji_balik/`:

- `kandidat[_jam|_harian_das].csv`
- `kepekaan_bias.csv`
- `pindai_harian[...].csv`
- `realisme_*.csv`
- `ringkasan.json`

Hasil juga ditampilkan di konsol, tab **Data**, bagian *Evaluasi pada data nyata* (`GET /data/evaluasi-nyata`).

## Status hasil

Hasil ini **bukan validasi resmi**, karena:

- label kejadian berasal dari berita dan masih berstatus kandidat (A-055);
- model lapis I dilatih pada episode sintetis (A-026);
- muka air per jam masih sintetis.

## Pengaturan utama

Semua angka di bawah memakai pengaturan ini. Tujuannya agar model hanya memakai informasi yang sudah
tersedia pada jam keputusan.

- **Preset:** base.
- **Prakiraan:** persistensi (A-058).
- **Muka air sintetis:** tertunda sesuai latensi hujan masukannya (A-062).

Ada tiga sumber hujan:

| Kode | Isi | Jeda informasi |
| --- | --- | --- |
| `harian` | IMERG Late harian, satu sel per titik | 14–38 jam |
| `jam` | IMERG Late per jam (dari produk setengah jam) | sekitar 14 jam |
| `harian_das` | Seperti harian, tetapi hujan hulu = rerata 9 sel DAS Tuntang (A-063) | 14–38 jam |

## 1. Kandidat satu per satu (sumber harian)

Keterangan kolom:

- **Hulu 72 j aktual**: hujan yang benar-benar turun dalam 72 jam sebelum T-0 (untuk diagnosis saja).
- **Hulu 3 hari tersedia**: hujan yang sudah bisa dilihat model pada T-0.

| ID | T-0 | Hulu 72 j aktual (mm) | Hulu 3 hari tersedia (mm) | p T-24 | p T-0 | p maks (T-72..T-0) | Rencana SIGAP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| K01 | 6 Feb 2024 00.00 | 94 | 96 | 0,14 | 0,25 | 0,25 | T1@T-36; T5@T-6 |
| K02 | 21 Jan 2025 00.00 | 90 | 68 | 0,11 | 0,16 | 0,16 | T1@T-36 |
| K03 | 24 Jan 2025 22.25 | 41 | 45 | 0,23 | 0,05 | 0,84 | T1@T-60; T2@T-6; T5@T-6 |
| K04 | 9 Mar 2025 05.27 | 74 | 35 | 0,16 | 0,13 | 0,16 | T5@T-6 |
| K05 | 18 Jun 2025 03.11 | 21 | 10 | 0,06 | 0,07 | 0,08 | – |
| K06 | 21 Okt 2025 18.00 | 36 | 9 | 0,08 | 0,06 | 0,13 | – |
| K07 | 16 Feb 2026 04.35 | 79 | 40 | 0,10 | 0,11 | 0,23 | T1@T-36; T5@T-6 |
| K08 | 16 Feb 2026 11.43 | 83 | 40 | 0,10 | 0,11 | 0,23 | T1@T-36; T5@T-6 |
| K09 | 3 Apr 2026 01.45 | 51 | 43 | 0,08 | 0,09 | 0,13 | T1@T-36 |

Hasil untuk sumber `jam` dan `harian_das` ada di CSV masing-masing. Polanya serupa.

- **Sumber `jam`:** K01 dan K02 sempat mencapai peluang sekitar 0,3–0,35, dan T7 terpicu pada T-12.
- **K03:** peluang tinggi di awal horizon berasal dari hujan 20–21 Jan, yaitu hujan yang juga memicu
  K02.

## 2. Pemindaian harian 2024–2026

Pengaturan:

- T-0 pukul 12.00 WIB setiap hari (sekitar 1.044 hari).
- 8 hari kejadian dibanding sekitar 992 hari "lain".
- Hari dalam ±3 hari dari kejadian dibuang dari pembanding.
- AUC = peluang skor hari kejadian lebih tinggi daripada hari lain; 0,5 = acak.
- Angka dalam kurung = selang kepercayaan 95% (bootstrap 2.000 kali).

| Skor | harian | jam | harian_das |
| --- | --- | --- | --- |
| Peluang SIGAP T-0 | **0,80** (0,68–0,91) | 0,76 (0,61–0,90) | 0,80 (0,68–0,91) |
| Peluang SIGAP T-24 | 0,73 (0,63–0,84) | 0,78 (0,64–0,91) | 0,73 (0,62–0,84) |
| Hujan hulu 3 hari **tersedia** (tanpa model) | 0,79 (0,65–0,92) | 0,80 (0,61–0,95) | 0,79 (0,65–0,91) |
| Hujan hulu 72 jam **aktual** (belum tersedia saat keputusan) | 0,87 (0,76–0,97) | 0,85 (0,69–0,97) | 0,88 (0,79–0,97) |
| Hujan lokal 72 jam aktual | 0,84 (0,75–0,93) | 0,82 (0,70–0,93) | 0,84 (0,75–0,93) |
| *Pembanding: peluang T-0 bila muka air sintetis dianggap waktu nyata* | 0,83 (0,73–0,91) | 0,73 (0,59–0,88) | 0,82 (0,72–0,90) |

**Frekuensi ambang (sumber harian):**

- Tidak ada hari kejadian yang mencapai peluang 0,3 pada T-0.
- Hari lain melewati 0,3 sekitar 8 kali per tahun dan 0,5 sekitar 1,5 kali per tahun.
- Pada sumber `jam`, 3 dari 8 hari kejadian mencapai 0,3, dengan hari lain melewati 0,3 sekitar 9 kali
  per tahun.

## 3. Kepekaan terhadap bias IMERG (sumber harian)

Seluruh hujan dikalikan 0,79; 0,8; 0,852; 1,0; dan 1,2. Faktor 1/1,266 dan 1/1,174 diambil dari
validasi Semarang (A-054, A-060).

- **Peluang T-0** bergeser paling banyak sekitar 0,15. Contoh: K01 naik dari 0,18 ke 0,33 dari skala
  0,79 sampai 1,2.
- **Rencana SIGAP** sebagian besar tetap. Yang berubah adalah tindakan yang dekat ambang:
  - Pada skala ≤ 0,852, K08 kehilangan T1 dan T5, dan K07 kehilangan T5.
  - K01 kehilangan T1 pada skala 0,8 dan seluruh tindakannya pada skala 0,79.
  - Pada skala 1,2, K03 memicu T1, T5, dan T6 jauh lebih awal, dan K02 mendapat T5.
- **Kesimpulan:** bias ±20% tidak mengubah urutan kejadian, tetapi menggeser tindakan di dekat ambang.

## 4. Temuan

1. **Urutan cukup baik, skala belum.** Semua varian membedakan hari kejadian lebih baik daripada acak:
   batas bawah selang 95% berada di atas 0,6. Namun peluang absolutnya rendah, maksimum sekitar
   0,25 pada T-0, karena skala peluang diturunkan dari generator sintetis (bagian 5).
2. **Model belum melampaui hujan mentah.** AUC model (0,76–0,80) setara dengan hujan hulu tersedia
   tanpa model (0,79–0,80), dan selangnya tumpang tindih. Fitur muka air dan prakiraan belum menambah
   informasi karena muka air masih sintetis dan prakiraan hanya persistensi.
3. **Batas utama adalah informasi beberapa jam terakhir.** Hujan yang benar-benar turun dalam 72 jam
   memisahkan lebih baik (0,85–0,88) daripada hujan yang tersedia.
   - Data per jam (jeda sekitar 14 jam, bukan 14–38 jam) **tidak** menaikkan AUC model, karena hujan
     pemicu sering turun dalam 14 jam terakhir.
   - Contoh K03: hujan besar 24 Jan belum terlihat pada T-0 22.25.
   - Yang dibutuhkan adalah pengamatan waktu nyata, yaitu pos hujan atau TMA telemetri BBWS. Satelit
     dengan jeda pendek saja tidak cukup.
4. **Muka air sintetis "waktu nyata" memberi AUC sedikit lebih tinggi pada data harian** (0,83 vs
   0,80), tetapi itu karena memakai hujan yang belum tersedia (A-062). Ini menunjukkan nilai sebuah pos
   TMA waktu nyata, bukan kemampuan sistem saat ini.
5. **Rerata 9 sel DAS hampir tidak mengubah hasil.** Korelasi harian dengan sel titik hulu 0,97 dan
   total sama (rasio 1,01). Rerata hanya meratakan puncak: maksimum harian 68 mm, sel titik 109 mm.
6. **Ada kejadian yang tidak dipicu hujan.** K05 (tanggul jebol, Jun 2025) dan K06 (Okt 2025) terjadi
   dengan hujan hulu tersedia sekitar 10 mm. Ini sejalan dengan catatan E3 pada spesifikasi
   (gangguan dengan hujan lokal rendah).
7. **Hari "lain" berpeluang tinggi belum tentu alarm palsu.** Contohnya 24–28 Okt 2025, dengan hujan
   hulu 72 jam sampai 200 mm. Pada 28 Okt 2025 ada banjir yang mengganggu jalur Semarang
   Tawang–Alastua (di luar koridor). Untuk koridor Brumbung–Karangjati belum ditemukan berita
   gangguan pada tanggal itu.

## 5. Realisme generator dummy (penyebab peluang rendah)

Yang dibandingkan: 400 episode latih lapis I dari generator dummy, 1.044 hari nyata IMERG Late, dan
8 hari kejadian kandidat. Median tiap besaran:

| Besaran (median) | Episode latih sintetis | Semua hari nyata | Hari kejadian kandidat |
| --- | --- | --- | --- |
| Hujan hulu 72 jam (mm) | 81 | 12,5 | 66 |
| Hujan hulu 3 hari tersedia pada T-0 (mm) | 80 | 12 | 42 |
| Hujan lokal 3 hari tersedia pada T-0 (mm) | 69 | 11 | 44 |
| Glapan relatif Awas pada T-0, muka air tertunda (cm) | −63 | −189 | −147 |

- **Episode latih jauh lebih basah daripada hari nyata.** Median hujan hulu 72 jam episode sintetis
  (81 mm) setara persentil 98 hari nyata. Sebanyak 36% episode sintetis melewati 100 mm, padahal hanya
  2 hari nyata (0,2%) yang mencapainya.
- **Kejadian nyata terjadi pada hujan sedang.** Pada hujan 40–100 mm, model kebenaran generator hanya
  memberi peluang gangguan 6–29%. Akibatnya model belajar bahwa gangguan butuh hujan lebih besar
  daripada yang terlihat pada kejadian nyata.
- **Muka air sintetis dari hujan nyata tetap jauh di bawah Awas.** Glapan nyata 25 Jan 2025 mencapai
  +65 cm. Episode latih yang terganggu sering melewati Awas.

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
punya 8 kejadian. Karena itu tabel ini hanya menunjukkan arah.

Pilihan tindak lanjut, keduanya keputusan tim (A-001, A-010, A-061):

- **(a) Kalibrasi ulang keluaran model.** Generator dipertahankan sebagai skenario uji tekanan, lalu
  peluang keluaran model dikalibrasi ulang (mis. Platt/isotonik) dengan label nyata terverifikasi.
- **(b) Parameterisasi ulang generator.** Median badai disesuaikan dengan sebaran hari basah IMERG,
  dan intersep model kebenaran diturunkan agar gangguan muncul pada 40–100 mm. Setelah itu lapis I
  dilatih ulang dan simulasi kebijakan diulang.

## 6. Batas klaim

- n = 8 hari kejadian, semuanya kandidat. Selang AUC lebar, dan perbedaan antarvarian tidak
  bermakna.
- Hari tanpa berita belum tentu tanpa gangguan.
- AUC dan frekuensi ambang hanya gambaran kemampuan membedakan hari, bukan janji kinerja
  operasional.
- Sistem tidak menyatakan jalur bebas risiko pada hari berpeluang rendah. Status jalur tetap
  ditetapkan KAI.
