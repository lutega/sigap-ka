# SIGAP-KA: Dokumen Spesifikasi Fungsional

Versi draf untuk Proyek Minor KS5203, disusun dari deck Overview dan Update Tim SIGAP-KA (posisi 5 November 2026). Butir bertanda *asumsi* belum dikonfirmasi tim.

## 1. Tujuan sistem

SIGAP-KA adalah sistem pendukung keputusan yang membantu pengendali operasi KA di koridor Brumbung–Karangjati, Grobogan, menentukan **kapan** tiap tindakan kontinjensi diaktifkan saat banjir mengancam. Sistem memberi usulan; keputusan tetap di tangan operator, dan status jalur tetap ditetapkan KAI.

## 2. Lingkup

| Dalam lingkup | Di luar lingkup |
| --- | --- |
| Satu koridor Brumbung–Karangjati dan rute alternatif via Gundih atau Solo | Seluruh jaringan lintas utara Jawa |
| Fase kesiapsiagaan sampai transisi respons | Pemulihan dan rekonstruksi prasarana |
| 4–6 KA contoh dari jadwal publik | Penjadwalan ulang penuh semua lintas |
| Gangguan genangan dan gerusan | Prediksi kegagalan struktur tanggul atau rel |
| Model kurva pemicu dan simulasi kebijakan | Reinforcement learning (tahap lanjutan) |
| Skenario kontinjensi yang ditinjau praktisi | Rencana kontinjensi resmi KAI |

## 3. Pengguna dan peran

| Peran | Kebutuhan | Hak di sistem |
| --- | --- | --- |
| Pengendali operasi KA (pengguna utama) | Tahu kapan tiap tindakan perlu diputuskan | Melihat usulan, menyetujui atau menolak tindakan |
| Pihak berwenang KAI | Menetapkan status jalur | Di luar sistem; sistem tidak pernah menyatakan jalur aman |
| Unit jalan rel dan jembatan, humas Daop, BPBD Grobogan | Menerima informasi lebih awal | Penerima informasi |
| Analis atau tim riset | Mengelola data dan parameter, menjalankan simulasi | Mengubah params.json, membangun ulang konsol |

## 4. Kebutuhan fungsional

### 4.1 Lapis S · Sensing (pengumpulan data)

- **FR-S1** Sistem menerima data hujan lokal dan hulu (NASA POWER; IMERG dan GSMaP sebagai rencana).
- **FR-S2** Sistem menerima muka air Bendung Glapan dan, bila tersedia, prakiraan hujan.
- **FR-S3** Sistem menyimpan katalog kejadian gangguan: tanggal, jam tutup dan buka, mekanisme, KA terdampak.
- **FR-S4** Setiap baris data diberi label `is_simulated` dan dicatat sumber, tanggal, serta riwayat pemutakhirannya.
- **FR-S5** Data dummy dibangkitkan dari params.json dengan preset low, base, dan high.

### 4.2 Lapis I · Inferensi (estimasi kondisi)

- **FR-I1** Sistem menghitung peluang gangguan jalur pada tiap jam keputusan.
- **FR-I2** Sistem menaksir mekanisme gangguan: genangan (jam sampai sekitar 1 hari) atau gerusan (hari sampai minggu).
- **FR-I3** Sistem memperkirakan lama penutupan jalur.
- **FR-I4** Estimasi diperbarui setiap ada bukti baru, termasuk laporan petugas lapangan (rolling horizon).

### 4.3 Lapis G · Gating (inti keputusan)

- **FR-G1** Tiap tindakan T1–T9 punya parameter sendiri: biaya tindakan C, kerugian bila tidak bersiap L, denda alarm palsu P, dan batas waktu siap.
- **FR-G2** Sistem menghitung kurva pemicu per tindakan dengan pemrograman dinamis; di batas waktu siap, ambangnya (C + P) / (L + P).
- **FR-G3** Bila peluang gangguan memotong kurva tindakan, status tindakan menjadi **Putuskan sekarang**; bila belum, **Tunggu prakiraan berikutnya**.
- **FR-G4** Pengguna dapat mengubah parameter lewat slider untuk melihat pergeseran kurva.

### 4.4 Lapis A · Aksi (antarmuka keputusan)

- **FR-A1** Konsol menampilkan papan tindakan berisi status SIGAP per tindakan.
- **FR-A2** Operator dapat menyetujui atau menolak tiap tindakan.
- **FR-A3** Setiap keputusan operator tercatat di log beserta waktunya.
- **FR-A4** Di akhir episode (T−0), sistem membandingkan biaya keputusan operator dengan saran SIGAP.
- **FR-A5** Sistem tidak pernah menampilkan pernyataan bahwa jalur aman dilalui.

### 4.5 Lapis P · Policy

- **FR-P1** Denda alarm palsu P menjadi parameter eksplisit agar efeknya pada keterlambatan tindakan bisa dihitung.
- **FR-P2** Aspek kebijakan lain (berbagi data antarinstansi) dibahas kualitatif di laporan, tidak diimplementasikan.

### 4.6 Konsol (lima tab)

| Tab | Fungsi |
| --- | --- |
| Operasi | Putar ulang episode, papan tindakan, keputusan operator |
| Data | Hujan, kejadian, muka air, status data nyata atau dummy |
| Prediksi | Peluang gangguan, mekanisme, lama tutup |
| Kurva pemicu | Ambang per tindakan, slider parameter |
| Simulasi | 300 episode, perbandingan enam kebijakan |

### 4.7 Simulasi dan evaluasi

- **FR-E1** Sistem menjalankan simulasi banyak episode dan membandingkan enam kebijakan: SIGAP, jam tetap 24 jam, ambang tetap 0,5, cost-loss di batas, reaktif, dan informasi sempurna.
- **FR-E2** Biaya per episode = biaya tindakan + kerugian bila terganggu tanpa persiapan + denda alarm palsu, dijumlah untuk sembilan tindakan.
- **FR-E3** Bilangan acak simulasi dapat diulang, dan angka konsol sama dengan model.py untuk tiap preset.
- **FR-E4** Estimasi gangguan diuji dengan POD, FAR, CSI, dan lead time memakai leave-one-episode-out; pembanding menerima informasi setara pada jam yang sama.

## 5. Kebutuhan nonfungsional

- **NFR-1 Human in the loop:** tidak ada keluaran yang dieksekusi otomatis.
- **NFR-2 Transparansi data:** data nyata dan dummy selalu terpisah dan berlabel.
- **NFR-3 Satu sumber parameter:** generator, model, dan konsol membaca params.json yang sama; konsol dibangun ulang dengan satu perintah `python3 export_dashboard.py`.
- **NFR-4 Keterulangan:** hasil simulasi bisa direproduksi.
- **NFR-5 Ketahanan data:** model tetap berjalan bila data tambahan (BBWS, BMKG detail, arsip prakiraan) belum tersedia.

## 6. Batas klaim yang wajib disebut

- Keunggulan SIGAP adalah batas atas menurut asumsinya sendiri; uji penentu butuh prakiraan nyata.
- Muka air dummy meleset: model 1768 vs nyata 1970 pada 24 Jan 2025.
- Dua kejadian (E3, E6) terjadi dengan hujan lokal rendah, sehingga perlu bukti dari hulu.
- Laporan memakai satu definisi episode hujan lebat.

## 7. Pertanyaan terbuka

- Model apa yang dipakai di lapis I sekarang: Bayesian dua mekanisme seperti di Overview, atau pendekatan lain?
- Apakah OCR + LLM untuk ekstraksi pengumuman KAI masih dalam lingkup?
- Nama dan batas waktu siap ketiga tindakan lain dari T1–T9 yang belum disebut di deck.
- Format laporan dan rubrik penilaian dari Pak Armi.

## 8. Elaborasi lapis S · Sensing

Lapis S mengubah semua sumber menjadi satu format tabel standar (waktu, lokasi, nilai, satuan, sumber, `is_simulated`). Setiap sumber adalah satu modul terpisah; data inti dari sumber terbuka, data bersurat bersifat opsional.

### 8.1 Hujan

Dua lokasi dibedakan: **hujan lokal** di sekitar Gubug–Karangjati dan **hujan hulu** di daerah tangkapan Sungai Tuntang, Kabupaten Semarang. Variabel kunci: akumulasi hujan 3–5 hari (anteseden) dan hujan hulu, bukan hujan harian lokal saja.

| Modul | Isi dan resolusi | Akses | Peran di model |
| --- | --- | --- | --- |
| `hujan_nasa_power.py` | Harian, grid kasar | API per koordinat, tanpa akun | Riwayat episode 2024–2026, akumulasi anteseden |
| `hujan_gpm_imerg.py` | Per 30 menit, grid sekitar 10 km | NASA GES DISC, akun Earthdata | Hujan hulu Tuntang; versi final untuk analisis riwayat |
| `hujan_gsmap.py` | Hujan satelit hampir real-time | Portal JAXA, akun gratis | Operasional; cadangan bila IMERG terlambat |
| `prakiraan_bmkg.py` | Prakiraan dan peringatan dini cuaca terkini | Situs dan data terbuka BMKG | Masukan utama keputusan |
| `hujan_bmkg_stasiun.py` | Pos hujan, AWS, radar | Surat permohonan (opsional) | Koreksi data satelit |

Aturan: pada jam keputusan, model hanya memakai informasi yang sudah tersedia saat itu. Hujan teramati tidak dipakai sebagai pengganti prakiraan.

### 8.2 Muka air

| Modul | Isi | Status | Peran |
| --- | --- | --- | --- |
| `muka_air_glapan.py` | Elevasi Bendung Glapan dari rilis BNPB (contoh: 1970 pada 24 Jan 2025, ambang Awas 1905) | Nyata, satu titik | Bukti hulu untuk tindakan memutar dan siaga Dapsus/AMUS |
| `muka_air_bbws.py` | Seri waktu muka air dan pos hujan BBWS Pemali Juana | Bersurat, opsional | Kalibrasi model muka air |
| `muka_air_sintetis.py` | Muka air hulu dan air di badan rel dari model hujan–limpasan | Sintetis, berlabel | Pengisi sementara; versi awal dipertahankan sampai data nyata masuk |

Catatan: model sintetis meleset pada 24 Jan 2025 (1768 vs 1970) dan wajib disebut di batas klaim.

### 8.3 Kejadian gangguan

Dua metode, dipilih lewat file environment (`KEJADIAN_METODE`):

1. `kejadian_ocr_llm.py`: mengumpulkan unggahan KAI121 dan Daop 4, OCR untuk pengumuman berbentuk gambar, LLM mengubahnya menjadi baris terstruktur, lalu peneliti memeriksa tiap baris (kode K1–K3). Presisi dan recall diukur terhadap koding manual.
2. `kejadian_manual.py`: membaca tabel yang diisi manual dari berita, pengumuman KAI, dan rilis BNPB/BPBD.

Kolom katalog: id kejadian (E1–E6), tanggal, jam tutup, jam buka, lokasi KM, mekanisme (genangan atau gerusan), KA terdampak, sumber. Prioritas pengisian: jam tutup, jam buka, dan mekanisme E1, E4, E5, E6. Episode hujan tanpa pengumuman diberi label “belum terkonfirmasi”, bukan dianggap normal.

### 8.4 Jadwal KA dan parameter biaya

- `jadwal_ka.py`: 4–6 KA yang melewati Gubug (nomor, relasi, jam lewat) dari jadwal publik; menggantikan placeholder KA-A s.d. KA-F.
- Parameter per tindakan disimpan di `config/params.json`: C (biaya tindakan), L (kerugian bila tidak bersiap), P (denda alarm palsu), waktu siap, masing-masing dengan rentang low, base, high. File environment hanya memilih preset dan lokasi file parameter (misalnya `PARAMS_PRESET=base`).
- Jangkar nyata saat ini: refund banjir Pekalongan Rp3,5 miliar untuk 124 perjalanan batal. Biaya memutar dan pembatalan dicari lewat wawancara praktisi KAI.

## 9. Elaborasi lapis I · Inferensi

Lapis I menjawab tiga pertanyaan pada setiap jam keputusan: seberapa besar peluang jalur terganggu, lewat mekanisme apa, dan berapa lama. Pendekatannya mengikuti deck Overview: estimasi Bayesian dengan campuran dua mekanisme, diperbarui setiap ada bukti baru. Rincian rumus di bawah adalah usulan rancangan (*asumsi*) yang perlu dikonfirmasi tim.

### 9.1 Masukan per jam keputusan

- Akumulasi hujan lokal 1, 3, dan 5 hari terakhir
- Hujan hulu Tuntang (rata-rata daerah tangkapan)
- Prakiraan hujan untuk jendela ke depan
- Muka air Bendung Glapan dan tren kenaikannya
- Laporan petugas lapangan bila ada

### 9.2 Model dua mekanisme

| Mekanisme | Pemicu fisik | Pemulihan | Bukti terkuat |
| --- | --- | --- | --- |
| Genangan | Hujan beberapa hari, debit Tuntang tinggi | Jam sampai sekitar 1 hari | Akumulasi hujan lokal dan hulu |
| Gerusan atau amblas | Arus deras dari luapan atau tanggul jebol | Hari sampai minggu | Hujan hulu, muka air Glapan, status tanggul |

Peluang gangguan total = peluang genangan + peluang gerusan (diperlakukan saling lepas untuk satu episode). Setiap mekanisme dimodelkan dengan regresi logistik Bayesian sederhana atas masukan 9.1 (*asumsi*).

### 9.3 Prior dari ahli

Kejadian nyata hanya enam penutupan dalam lima episode, terlalu sedikit untuk melatih model dari data saja. Karena itu:

- Prior koefisien ditetapkan ahli secara terbuka dan dicatat di params.json.
- Sensitivitas hasil terhadap prior diuji dengan preset low, base, high.
- Kejadian E3 dan E6 (hujan lokal rendah) menjadi uji bahwa model memberi bobot pada bukti hulu.

### 9.4 Lama penutupan

Lama tutup dinyatakan sebagai tiga skenario, pendek, sedang, dan panjang, dengan peluang masing-masing yang bergantung pada mekanisme. Genangan condong ke skenario pendek, gerusan ke skenario panjang. Skenario ini menjadi masukan lapis G untuk menghitung kerugian L tiap tindakan.

### 9.5 Pembaruan bukti (rolling horizon)

Setiap kali prakiraan baru, data muka air, atau laporan petugas lapangan masuk, peluang dan skenario dihitung ulang, lalu lapis G memperbarui status tindakan. Laporan lapangan yang mengonfirmasi air di badan rel menaikkan peluang tajam; status jalur tetap ditetapkan KAI.

### 9.6 Keluaran dan pengujian

- Keluaran: peluang gangguan, peluang per mekanisme, sebaran lama tutup, dan bukti yang paling memengaruhi hasil.
- Uji: POD, FAR, CSI, dan lead time dengan leave-one-episode-out; pembanding aturan hujan lokal dan indeks adaptasi H-MHEWS, sesuai deck. H-MHEWS hanya pembanding, bukan masukan.

## 10. Elaborasi lapis G · Gating

Lapis G memutuskan, untuk tiap tindakan T1–T9 pada tiap jam keputusan, apakah tindakan itu sebaiknya **diputuskan sekarang** atau **menunggu prakiraan berikutnya**. Dasarnya model cost-loss (Murphy, 1977) dengan denda alarm palsu dan nilai informasi (Howard, 1966).

### 10.1 Parameter per tindakan

| Parameter | Arti | Sumber nilai |
| --- | --- | --- |
| C | Biaya tindakan bila dijalankan | params.json; wawancara praktisi KAI |
| L | Kerugian bila gangguan terjadi tanpa persiapan | params.json; jangkar refund Rp3,5 miliar |
| P | Denda alarm palsu (biaya reputasi dan sanksi) | params.json; lapis P |
| Waktu siap | Batas waktu terakhir tindakan masih berguna | Tabel anggaran lead time (deck Overview) |

### 10.2 Ambang dan kurva pemicu

Pada batas waktu siap, bertindak lebih murah bila peluang gangguan p memenuhi:

```latex
p > \frac{C + P}{L + P}
```

Sebelum batas waktu, ada pilihan ketiga: menunggu prakiraan yang lebih akurat. Nilai menunggu dihitung dengan pemrograman dinamis mundur dari batas waktu, sehingga ambang efektif membentuk **kurva pemicu**: tinggi saat kejadian masih jauh dan turun ke (C + P) / (L + P) tepat di batas waktu siap.

### 10.3 Aturan keputusan

- p di atas kurva tindakan → status **Putuskan sekarang**.
- p di bawah kurva → status **Tunggu prakiraan berikutnya**.
- Batas waktu terlewati tanpa tindakan → status **Terlambat**, dicatat sebagai kerugian potensial.
- Tindakan yang sudah disetujui tidak dihitung ulang, kecuali operator membatalkannya.

### 10.4 Pola yang diharapkan

Tindakan murah seperti informasi penumpang (T1) punya kurva yang turun paling awal. Tindakan mahal seperti pembatalan (T9) butuh peluang tinggi, di atas sekitar 70% pada preset base. Angka ini masih dummy.

## 11. Elaborasi lapis P · Policy

- **Denda alarm palsu sebagai parameter eksplisit.** Makin besar P, makin tinggi ambang, makin terlambat operator bertindak. Simulasi menunjukkan berapa biaya keterlambatan yang ditimbulkan kebijakan yang menghukum alarm palsu.
- **Berbagi data antarinstansi.** Data muka air BBWS, prakiraan BMKG, dan katalog kejadian KAI bernilai juga bagi BPBD Grobogan untuk peringatan warga. Dibahas kualitatif di laporan.
- **Kewenangan.** Rekomendasi kebijakan tidak mengubah kewenangan KAI atas status jalur.

## 12. Elaborasi lapis A · Aksi dan pengendali operasi KA

### 12.1 Alur kerja operator

1. Konsol menampilkan papan tindakan dengan status SIGAP per tindakan, peluang gangguan, mekanisme, dan sisa waktu sampai batas waktu siap.
2. Operator membaca alasan singkat tiap usulan: bukti utama dan selisih peluang terhadap kurva.
3. Operator memilih **Setujui** atau **Tolak**; penolakan boleh disertai alasan.
4. Keputusan tercatat di log dengan waktu, status SIGAP saat itu, dan identitas operator.
5. Saat bukti baru masuk, papan diperbarui; tindakan berstatus Tunggu bisa berubah menjadi Putuskan sekarang.

### 12.2 Daftar tindakan (dari deck)

| Tindakan | Harus diputuskan sebelum |
| --- | --- |
| Informasi penumpang, refund | Penumpang berangkat ke stasiun |
| Menahan KA di stasiun asal | KA berangkat dari stasiun asal |
| Memutar via Gundih atau Solo | KA melewati titik percabangan |
| Mobilisasi bus pengganti | Bus tiba di stasiun titik putus |
| Siagakan petugas Dapsus dan AMUS | Air mencapai badan jalan rel |
| Pembatalan perjalanan | Sebelum jadwal berangkat |

Tiga tindakan lain dari T1–T9 belum disebut di deck dan perlu dikonfirmasi tim.

### 12.3 Evaluasi keputusan operator

Di akhir episode (T−0), konsol membandingkan biaya keputusan operator dengan biaya bila saran SIGAP diikuti, beserta tindakan mana yang terlalu awal, terlambat, atau sia-sia. Fitur ini juga dipakai untuk demo: penguji mencoba menjadi operator.

### 12.4 Pengecekan maladaptasi

Sebelum usulan memutar via Gundih ditampilkan, sistem memberi peringatan bila rute itu juga berada di wilayah terdampak hujan yang sama. Usulan bus pengganti diberi peringatan bila jalan Semarang–Purwodadi dilaporkan terputus.

## 13. Elaborasi peran KAI

- **Status jalur** (pembatasan atau penutupan) ditetapkan pihak berwenang KAI berdasarkan pemeriksaan lapangan. Sistem tidak menghitung dan tidak menampilkan pernyataan jalur aman.
- **Masukan dari KAI ke sistem:** jadwal KA, laporan petugas lapangan, status jalur resmi, dan pengumuman gangguan.
- **Keluaran sistem untuk KAI:** usulan tindakan dengan alasannya, log keputusan, dan ringkasan biaya per episode sebagai dasar evaluasi rencana kontinjensi.
- **Penerima lain:** unit jalan rel dan jembatan (siaga dan pemeriksaan), humas Daop (informasi penumpang), BPBD Grobogan (informasi banjir Tuntang). Pesan untuk penerima disetujui petugas sebelum dikirim.

## 14. Implementasi: REST API dengan FastAPI

Inti sistem ditulis dalam Python dan diekspos lewat REST API FastAPI. Modul lapis S, I, G, dan A tetap terpisah; API hanya lapisan tipis yang memanggil modul-modul itu, sehingga logika model tidak bergantung pada framework. Frontend dashboard memakai React + Vite + Recharts dan hanya berkomunikasi lewat API.

### 14.1 Susunan kode

```
sigap/
  .env                     # pilihan preset, metode katalog, lokasi data
  config/params.json
  sensing/  inference/  gating/  action/  simulation/
  api/
    main.py                # membuat aplikasi FastAPI, mendaftarkan router
    schemas.py             # model Pydantic untuk request dan response
    deps.py                # memuat konfigurasi dan data sekali saat start
    routers/
      data.py
      prediksi.py
      kurva.py
      tindakan.py
      simulasi.py
  tests/
```

### 14.2 Endpoint

| Metode | Endpoint | Fungsi | Lapis |
| --- | --- | --- | --- |
| GET | `/data/sumber` | Daftar sumber data, status nyata/dummy, waktu ambil terakhir | S |
| GET | `/data/hujan?lokasi=&dari=&sampai=` | Seri hujan lokal atau hulu | S |
| GET | `/data/muka-air` | Seri muka air Glapan dan sintetis | S |
| GET | `/data/kejadian` | Katalog kejadian E1–E6 | S |
| GET | `/episode` | Daftar episode untuk diputar ulang | S |
| GET | `/episode/{id}/prediksi?jam=` | Peluang gangguan, mekanisme, lama tutup pada jam keputusan | I |
| GET | `/tindakan` | Daftar tindakan dan parameter C, L, P, waktu siap | G |
| GET | `/kurva/{tindakan}` | Kurva pemicu satu tindakan | G |
| POST | `/kurva/hitung` | Hitung ulang kurva dengan parameter dari slider | G |
| GET | `/episode/{id}/papan?jam=` | Status tiap tindakan: Putuskan sekarang, Tunggu, Terlambat | A |
| POST | `/episode/{id}/keputusan` | Simpan Setujui atau Tolak dari operator | A |
| GET | `/episode/{id}/ringkasan` | Biaya keputusan operator vs saran SIGAP di T−0 | A |
| POST | `/simulasi` | Jalankan simulasi N episode untuk enam kebijakan | Evaluasi |
| GET | `/simulasi/{id}` | Hasil simulasi: biaya per kebijakan, metrik | Evaluasi |

Tidak ada endpoint yang menetapkan atau mengembalikan status jalur aman.

### 14.3 Konfigurasi lewat file environment

| Variabel | Contoh | Arti |
| --- | --- | --- |
| `PARAMS_FILE` | `config/params.json` | Lokasi file parameter |
| `PARAMS_PRESET` | `base` | Preset low, base, atau high |
| `KEJADIAN_METODE` | `manual` | `manual` atau `ocr_llm` |
| `SUMBER_HUJAN_HULU` | `gpm_imerg` | Sumber hujan hulu aktif |
| `DATA_DIR` | `data/processed` | Data olahan yang dibaca model |
| `SIM_SEED` | `42` | Seed simulasi agar hasil bisa diulang |

### 14.4 Aturan teknis

- Request dan response divalidasi dengan model Pydantic; dokumentasi API otomatis tersedia di `/docs`.
- Data dibaca dari `data/processed`, sehingga API tidak mengunduh ulang saat dijalankan dan demo tidak bergantung pada internet.
- Simulasi panjang dijalankan sebagai tugas latar belakang; hasilnya diambil lewat `/simulasi/{id}`.
- Penyimpanan memakai satu database PostgreSQL dengan TimescaleDB (lihat 14.5).
- Pengujian: pytest untuk modul, `TestClient` FastAPI untuk endpoint.

### 14.5 Database: PostgreSQL + TimescaleDB

Data utama sistem berupa time series yang dikumpulkan dari internet (hujan, prakiraan, muka air). TimescaleDB menyimpan dan meringkasnya dengan cepat, sedangkan PostgreSQL biasa menampung data relasional dalam database yang sama. Dijalankan dengan Docker.

| Tabel | Jenis | Isi |
| --- | --- | --- |
| `obs_hujan` | Hypertable | waktu, lokasi (lokal/hulu), nilai mm, sumber, `is_simulated`, waktu\_ambil |
| `prakiraan_hujan` | Hypertable | waktu\_terbit, waktu\_valid, lokasi, nilai mm, sumber |
| `obs_muka_air` | Hypertable | waktu, titik (Glapan dan lainnya), elevasi, sumber, `is_simulated` |
| `sumber_data` | Relasional | nama, jenis, cara akses, status inti atau tambahan |
| `log_pengambilan` | Relasional | sumber, waktu ambil, rentang data, versi atau tautan, status |
| `kejadian` | Relasional | id E1–E6, tanggal, jam tutup, jam buka, KM, mekanisme, sumber, metode |
| `jadwal_ka` | Relasional | nomor KA, relasi, jam lewat Gubug |
| `tindakan` | Relasional | T1–T9, nama, batas waktu siap |
| `keputusan_operator` | Relasional | episode, tindakan, jam, status SIGAP, setujui/tolak, alasan |
| `hasil_simulasi` | Relasional | id run, preset, seed, kebijakan, biaya per episode |

Parameter C, L, P tetap di `params.json`, bukan di database, agar satu sumber parameter terjaga. Ringkasan seperti akumulasi hujan 3 dan 5 hari dibuat sebagai continuous aggregate TimescaleDB. Prakiraan disimpan dengan waktu terbitnya, supaya model hanya memakai prakiraan yang sudah tersedia pada jam keputusan.

## 15. Login dan manajemen pengguna

Dashboard diawali halaman login. Fitur ini bersifat formalitas untuk prototipe, tetapi tetap mengikuti praktik dasar yang aman.

- **Akun awal:** username `admin`, password `admin`, level admin. Nilainya diambil dari file environment (`ADMIN_USER`, `ADMIN_PASSWORD`) agar mudah diganti di luar demo.
- **Level pengguna:** admin (kelola pengguna, ubah parameter, jalankan simulasi) dan operator (melihat dashboard, menyetujui atau menolak tindakan).
- **Manajemen pengguna:** admin dapat menambah, menonaktifkan, dan mengatur ulang password pengguna dari dalam dashboard.
- **Teknis:** password disimpan sebagai hash (bcrypt) di tabel `pengguna`; login lewat `POST /auth/login` mengembalikan token JWT; endpoint lain mewajibkan token, dan endpoint pengelolaan pengguna (`/pengguna`) khusus admin.
- **Log:** setiap keputusan operator tercatat dengan username pelakunya.

## 16. Mode demo untuk ujian dan presentasi

Mode demo memutar ulang satu episode banjir jam demi jam dengan jam yang dipercepat, sehingga penguji dapat merasakan keputusan operator tanpa menunggu kejadian nyata. Mode ini sepenuhnya offline: semua data dibaca dari database lokal.

- **Pilihan episode:** episode nyata (contoh utama malam 24 Januari 2025) dan episode sintetis dari simulator; label nyata atau sintetis selalu tampil.
- **Kendali waktu:** mulai, jeda, lompat ke jam keputusan berikutnya, dan pilihan kecepatan (misalnya 1 jam episode = beberapa detik). Model hanya memakai informasi yang tersedia sampai jam yang sedang diputar.
- **Peran penguji:** login sebagai operator, lalu menyetujui atau menolak tindakan di papan tindakan.
- **Akhir episode (T−0):** ringkasan biaya keputusan penguji vs saran SIGAP, plus daftar tindakan yang terlalu awal, terlambat, atau sia-sia.
- **Reset:** admin dapat mengulang episode dan menghapus log demo tanpa menyentuh log lain; log demo diberi tanda `mode=demo`.
- **Endpoint:** `POST /demo/mulai`, `POST /demo/{id}/langkah`, `POST /demo/{id}/jeda`, `GET /demo/{id}/status`, `POST /demo/{id}/reset`.
- **Cadangan presentasi:** satu skenario demo tersimpan dengan seed tetap, sehingga hasilnya sama setiap kali diputar.
