# SIGAP-KA: Data Input Model

Catatan seluruh masukan yang dipakai model SIGAP-KA, per lapis, beserta sumber, satuan, latensi, dan
status nyata/dummy saat ini (posisi 22 Nov 2026). Nilai parameter diambil dari `config/params.json`
preset **base**; preset low/high ada di berkas yang sama.

## Alur singkat

```
Data observasi + prakiraan + laporan  ->  8 fitur (inference/fitur.py)  ->  lapis I: peluang gangguan,
mekanisme, lama tutup  ->  lapis G: kurva pemicu per tindakan (C, L, P, waktu siap)  ->  lapis A: papan
tindakan, peringatan maladaptasi, log keputusan, ringkasan biaya T-0
```

Aturan tetap: pada jam keputusan model hanya memakai data yang **sudah tersedia** saat itu
(akhir periode + latensi sumber; prakiraan menurut waktu terbit).

## 1. Data observasi dan prakiraan (masukan mentah)

| Seri | Sumber aktif → cadangan | Resolusi, satuan | Latensi | Status saat ini | Dipakai untuk |
| --- | --- | --- | --- | --- | --- |
| Hujan lokal Gubug–Karangjati | NASA POWER (episode nyata); generator dummy (episode sintetis) | harian (NASA POWER) atau per jam, mm | 72 jam (NASA POWER), 3 jam (dummy) | nyata 2024-01-01 s.d. 2026-11-20 | fitur hujan lokal 1/3/5 hari, indeks air di badan rel |
| Hujan hulu DAS Tuntang | GPM IMERG → GSMaP → NASA POWER → dummy | harian/per jam, mm | 4 jam (IMERG, GSMaP), 72 jam (NASA POWER) | IMERG/GSMaP belum ada kredensial; NASA POWER nyata tetapi **satu sel grid dengan lokal** | fitur hujan hulu 3 hari, model muka air sintetis |
| Hujan Gundih | NASA POWER / dummy | harian/per jam, mm | sama dengan di atas | nyata (sel grid sama) | hanya peringatan maladaptasi T3 |
| Prakiraan hujan lokal dan hulu | BMKG (adm4 33.15.17.2001, Desa Penadaran); sintetis untuk episode riwayat | per 3 jam, mm, dengan waktu terbit | 0 (dipakai sejak terbit) | BMKG nyata hanya terbitan terkini (tanpa arsip); episode memakai prakiraan sintetis berlabel | fitur prakiraan lokal/hulu |
| Muka air Bendung Glapan | rilis BNPB (manual) → BBWS (bersurat) → model sintetis | per jam (sintetis), elevasi (asumsi cm) | 2 jam (BNPB), 0 (sintetis) | nyata 1 titik (1970, 24 Jan 2025); seri per jam sintetis | fitur Glapan relatif dan tren |
| Laporan petugas: air di badan rel | laporan lapangan (tabel `laporan_lapangan`) | kejadian bertanda waktu | 0 | hanya sintetis di episode generator | pembaruan peluang (rasio kemungkinan) |
| Laporan jalan Semarang–Purwodadi putus | BPBD/BNPB (manual) | kejadian bertanda waktu | 0 | hanya sintetis | peringatan maladaptasi T4 |
| Katalog kejadian E1–E6 | manual atau OCR+LLM | per kejadian: tanggal, jam tutup/buka, KM, mekanisme | – | kerangka saja (jam dan mekanisme kosong) | **label** latih/validasi (belum bisa dipakai) |
| Jadwal KA lewat Gubug | jadwal publik KAI (manual) | jam lewat | – | placeholder KA-A s.d. KA-F (dummy) | tampilan saja; belum masuk perhitungan |

## 2. Fitur lapis I (`inference/fitur.py`)

Setiap fitur dibagi skalanya sebelum masuk model.

| Fitur | Definisi pada jam keputusan | Skala | Sumber |
| --- | --- | --- | --- |
| `hujan_lokal_1h` | akumulasi hujan lokal 24 jam terakhir yang tersedia (mm) | 50 | hujan lokal |
| `hujan_lokal_3h` | akumulasi hujan lokal 3 hari terakhir yang tersedia (mm) | 100 | hujan lokal |
| `hujan_lokal_5h` | akumulasi hujan lokal 5 hari terakhir yang tersedia (mm) | 150 | hujan lokal |
| `hujan_hulu_3h` | akumulasi hujan hulu Tuntang 3 hari terakhir yang tersedia (mm) | 100 | hujan hulu |
| `prakiraan_lokal` | jumlah prakiraan lokal dari jam keputusan sampai T−0, terbitan terakhir (mm) | 100 | prakiraan |
| `prakiraan_hulu` | jumlah prakiraan hulu dari jam keputusan sampai T−0, terbitan terakhir (mm) | 100 | prakiraan |
| `glapan_relatif` | muka air Glapan terakhir − ambang Awas 1905 | 100 | muka air (tanpa data: elevasi dasar 1700) |
| `glapan_tren` | kenaikan muka air Glapan 6 jam terakhir | 50 | muka air |

## 3. Parameter lapis I

| Masukan | Nilai | Status |
| --- | --- | --- |
| Model | logistik multinomial Bayesian, kelas tidak/genangan/gerusan | rancangan (A-026) |
| Prior koefisien | `inferensi.prior_rerata`; preset base: pengali 1,0, sd koefisien 1,0, sd intersep 2,0 (low 0,7/0,5/1,0; high 1,3/2,0/3,0) | dummy (penilaian pengembang) |
| Data latih | 400 episode sintetis, seed 100000 (terpisah dari SIM_SEED), 13 jam keputusan per episode | sintetis |
| Prediktif | Monte Carlo 200 sampel posterior Laplace, seed tetap | – |
| Rasio kemungkinan laporan air di badan rel | 20 | dummy |
| Skenario lama tutup | pendek 2–12 jam (faktor L 0,6), sedang 12–48 jam (1,0), panjang 48–336 jam (1,8) | dummy |
| Peluang skenario bersyarat | genangan 0,6/0,3/0,1; gerusan 0,1/0,3/0,6 (pendek/sedang/panjang) | dummy |

## 4. Masukan lapis G (kurva pemicu)

Kerangka waktu: horizon 72 jam sebelum T−0, keputusan tiap 6 jam (13 jam keputusan), anteseden 5 hari.

| Tindakan | C | L | P | Batas waktu siap | Ambang (C+P)/(L+P) |
| --- | --- | --- | --- | --- | --- |
| T1 Informasi penumpang dan refund | 5 | 150 | 10 | T−36 | 9,4% |
| T2 Menahan KA di stasiun asal | 40 | 300 | 30 | T−6 | 21,2% |
| T3 Memutar via Gundih atau Solo | 120 | 400 | 60 | T−12 | 39,1% |
| T4 Mobilisasi bus pengganti | 80 | 250 | 40 | T−12 | 41,4% |
| T5 Siagakan petugas Dapsus dan AMUS | 15 | 200 | 5 | T−6 | 9,8% |
| T6 (belum dikonfirmasi tim) | 30 | 200 | 20 | T−18 | 22,7% |
| T7 (belum dikonfirmasi tim) | 50 | 250 | 30 | T−12 | 28,6% |
| T8 (belum dikonfirmasi tim) | 60 | 220 | 40 | T−6 | 38,5% |
| T9 Pembatalan perjalanan | 750 | 1100 | 200 | T−24 | 73,1% |

Satuan biaya juta rupiah; **semua nilai dummy**. Jangkar nyata satu-satunya: refund Pekalongan
Rp3,5 miliar untuk 124 perjalanan batal.

| Masukan lain | Nilai | Status |
| --- | --- | --- |
| Peluang gangguan dan faktor L per jam | dari lapis I (L efektif = L × faktor lama tutup) | – |
| Konsentrasi Beta (evolusi peluang antarprakiraan) | 7 (dikalibrasi dari lintasan peluang lapis I) | turunan data sintetis |
| Diskon biaya bertindak lebih awal | 2% per langkah 6 jam | dummy, **penentu utama keunggulan SIGAP** |
| Grid peluang pemrograman dinamis | 201 titik | teknis |
| Keputusan operator yang sudah berlaku | dari log keputusan (tindakan disetujui tidak dihitung ulang) | – |

## 5. Masukan lapis A

| Masukan | Nilai | Status |
| --- | --- | --- |
| Ambang peringatan rute Gundih (hujan 24 jam) | 50 mm (kategori lebat BMKG) | dummy |
| Laporan jalan putus | ada/tidak pada jam keputusan | sintetis |
| Log keputusan operator | Setujui/Tolak/Batalkan, jam, username, mode normal/demo | dari pengguna |
| Hasil episode untuk ringkasan T−0 | kebenaran sintetis; episode nyata belum terkonfirmasi (dua kemungkinan) | – |

## 6. Masukan simulasi dan evaluasi

| Masukan | Nilai |
| --- | --- |
| Jumlah episode | 300 per preset, seed SIM_SEED = 42 |
| Generator episode | `params.json` blok `dummy` (hujan lognormal berkorelasi, galat prakiraan, model "kebenaran" gangguan); laju gangguan base sekitar 29% |
| Kebijakan pembanding | jam tetap T−24, ambang tetap 0,5, cost-loss di batas, reaktif, informasi sempurna |
| Pembanding deteksi (RQ1) | aturan hujan lokal 3 hari + prakiraan ≥ 100 mm; indeks adaptasi H-MHEWS (kategori hujan BMKG 20/50/100/150 mm, Glapan ≥ Awas), alarm bila ≥ 2 |
| Ambang deteksi SIGAP | peluang ≥ 0,5 |

## 7. Yang belum tersedia dan dampaknya

| Data | Dampak | Cara memperoleh |
| --- | --- | --- |
| Hujan hulu terpisah dari lokal | bukti hulu (kasus E3/E6) tidak terlihat pada episode nyata | akun Earthdata (IMERG, arsip sejak 2000) atau JAXA (GSMaP) |
| Arsip prakiraan | episode riwayat memakai prakiraan sintetis | surat permohonan BMKG |
| Seri muka air Glapan | muka air episode nyata sintetis (1734 vs nyata 1970) | surat permohonan BBWS Pemali Juana |
| Jam tutup/buka dan mekanisme E1–E6 | model belum bisa dilatih/divalidasi pada kejadian nyata | berita, pengumuman KAI121/Daop 4, BNPB/BPBD |
| Biaya C, L, P dan biaya keterlambatan | biaya dan keunggulan SIGAP hanya ilustrasi | wawancara praktisi KAI |
| Jadwal KA nyata | jadwal belum masuk perhitungan | jadwal publik KAI |
