# Katalog kejadian kandidat (berita publik)

Berkas: `data/manual/kejadian_kandidat.csv`. Pembaca: `src/sigap_ka/inputs/kejadian_kandidat.py`.

Katalog ini **bukan** data resmi KAI dan **tidak menggantikan** E1–E6 di `data/manual/kejadian.csv`.
Isinya dihimpun pada 22 Nov 2026 dari berita daring dan rilis BNPB atau KAI yang dikutip media.
Setiap baris berstatus `kandidat; perlu verifikasi tim`. Kolom `kemungkinan_E` sengaja dikosongkan
karena pemetaan ke E1–E6 adalah keputusan tim.

## Ringkasan

| ID | Tanggal | Jam acuan (WIB) | Petak / KM | Gangguan | Mekanisme |
| --- | --- | --- | --- | --- | --- |
| K01 | 6 Feb 2024 | tidak dinyatakan | Gubug–Karangjati | 5 KA terlambat | genangan |
| K02 | 21 Jan 2025 | tidak dinyatakan | KM 32+5/7 | tutup, rel amblas | gerusan |
| K03 | 24 Jan 2025 | 22.25 (tutup) | KM 32+5/7 | tutup, kembali tergerus/amblas | gerusan |
| K04 | 9 Mar 2025 | 05.27 (air melintasi rel) | KM 32+6/7 | tutup dua jalur; hulu dibuka 12.08 | genangan |
| K05 | 18 Jun 2025 | 03.11 (satu jalur) | KM 27+8/9 Tegowanu–Gubug | satu jalur bergantian | genangan |
| K06 | 21 Okt 2025 | 18.00 (tafsiran "Selasa malam") | KM 27 Gubug–Tegowanu | KA berhenti sementara; dibuka 22/10 05.00 | genangan |
| K07 | 16 Feb 2026 | 04.35 (tutup) | Jembatan 46 (KM 21+9/0) dan 59 (KM 27+9/0) | tutup | genangan |
| K08 | 16 Feb 2026 | 11.43 (tutup) | KM 32+5/7 | tutup dua jalur | genangan |
| K09 | 3 Apr 2026 | 01.45 (deteksi) | KM 32+7/8 jalur hilir | satu jalur bergantian | genangan (25 cm di atas kop rel) |

Kutipan mekanisme, dampak KA, penyebab, dan semua tautan ada di CSV. Tautan yang gagal dibuka
(paywall atau koneksi ditolak) dicatat terpisah di kolom `sumber_belum_dibaca` dan tidak dipakai
sebagai dasar fakta.

## Aturan jam acuan T-0 (A-055)

1. Bila sumber menyebut jam tutup, jam awal gangguan, atau jam deteksi, jam itu dipakai.
2. Bila jam tidak dinyatakan, T-0 = 00.00 hari kejadian. Aturan ini konservatif karena model tidak
   memakai informasi hari itu.
3. "Malam" tanpa jam ditafsirkan paling awal, yaitu 18.00 WIB.

## Perbedaan antarsumber yang perlu dicek tim

- **K02.** Keterangan foto detik menyebut satu jalur "dapat dilalui pada Jumat (24/1)", sedangkan
  BNPB 24/1 menyebut "baru sehari dipulihkan".
- **K03.**
  - Kronologi BNPB: luapan menyentuh tanggul bantalan rel sekitar 21.00, lalu arus menguat sekitar
    22.00.
  - detik dan Liputan6 menyebut jalur ditutup sekitar 22.25.
  - Keterangan foto detik menyebut amblas lagi "Sabtu (26/1)", padahal 26/1/2025 jatuh pada hari
    Minggu.
- **K04.** Kompas dan ringkasan mesin pencari menyebut jalur dibuka 11.32, sedangkan detik
  mencatat KA pertama melintas pukul 12.08.

## Lima titik rawan banjir yang dipantau KAI Daop 4

Sumber: Murianews, 17 Okt 2026. Daftar ini sebagai acuan lokasi, belum dipakai model.

1. Jembatan 46, KM 21+918, Brumbung–Tegowanu
2. Jembatan 59, KM 27+8/9, Tegowanu–Gubug
3. KM 32+5/7, Gubug–Karangjati
4. KM 22+700/750, Brumbung–Tanggung
5. KM 25+800 / 29+200, Tanggung–Kedungjati

## Pemakaian

- `tabel_t0()` menurunkan T-0 per kandidat untuk uji balik pada hujan IMERG Late
  (`simulation/backtest.py`).
- `ringkasan_publik()` hanya meneruskan domain sumber ke API dan dasbor, tidak tautan lengkap.
  Judul berita bisa memuat kata yang dilarang penjaga klaim.
