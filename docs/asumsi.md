# SIGAP-KA: Daftar Asumsi

Setiap asumsi diberi kode, tahap asal, dan status. Status **terbuka** berarti perlu dikonfirmasi
tim atau diganti data nyata. Angka nyata hanya yang tercantum di blok `_nyata` pada
`config/params.json`.

## Tahap 0 · Kerangka dan parameter

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-001 | Semua nilai C, L, P, dan waktu siap T1–T9 untuk preset low/base/high adalah **dummy** (satuan juta rupiah). Nilai base dipilih agar ambang T9 > 0,7 (spesifikasi 10.4) dan T1 paling murah. | Semua hasil biaya dan simulasi hanya menggambarkan perilaku model | terbuka |
| A-002 | Nama dan batas waktu T6–T8 belum disebut deck; dipakai placeholder "belum dikonfirmasi tim" dengan parameter dummy. | Papan tetap 9 baris; T6–T8 berlabel | terbuka |
| A-003 | Urutan T2–T5 mengikuti urutan tabel spesifikasi 12.2 (menahan KA, memutar, bus, Dapsus/AMUS); T1 = informasi penumpang dan T9 = pembatalan sesuai 10.4. | Penamaan tindakan | terbuka |
| A-004 | Jam keputusan tiap 6 jam, horizon episode 72 jam sebelum T−0, antesedent 5 hari. | Resolusi kurva pemicu | terbuka |
| A-005 | Koordinat lokal (Gubug–Karangjati), hulu Tuntang, Gundih, dan Bendung Glapan adalah perkiraan kasar. NASA POWER bergrid kasar sehingga selisih kecil tidak berpengaruh besar. | Lokasi pengambilan data hujan | terbuka |
| A-006 | Semua waktu disimpan sebagai WIB (UTC+7) tanpa zona waktu. | Konsistensi antar sumber | konvensi |
| A-007 | Satuan elevasi Glapan mengikuti rilis BNPB (diasumsikan cm pada papan duga); hanya ambang Awas 1905 yang diketahui, ambang Waspada/Siaga belum. | Indeks muka air | terbuka |
| A-008 | Kode wilayah BMKG (adm4) awal adalah perkiraan dan ternyata salah (404); diganti A-023. | - | selesai |
| A-009 | Prior koefisien lapis I (blok `inferensi.prior_rerata`) adalah penilaian awal pengembang, bukan ahli; preset low/base/high mengubah pengali rerata dan simpangan prior. | Sensitivitas lapis I | terbuka |
| A-010 | Model "kebenaran" generator dummy (blok `dummy.kebenaran`) sengaja berbeda dari prior inferensi agar evaluasi tidak melingkar sempurna. | Hasil simulasi | konvensi |
| A-011 | Faktor L skenario lama tutup (pendek 0,6; sedang 1,0; panjang 1,8) dan peluang bersyarat mekanisme adalah dummy; arah kualitatifnya mengikuti 9.2 (genangan jam–1 hari, gerusan hari–minggu). | Kerugian L efektif | terbuka |
| A-012 | Kategori hujan harian BMKG (sedang 20, lebat 50, sangat lebat 100, ekstrem 150 mm/hari) dipakai untuk indeks adaptasi H-MHEWS; perlu dicek tim. H-MHEWS hanya pembanding. | Pembanding RQ1 | terbuka |
| A-013 | `sigap_data_proyek_minor.zip` tidak tersedia di repo, sehingga kode, nilai dummy, dan model sintetis dibangun ulang. Angka "SIGAP 14% lebih murah" dan "model sintetis 1768" berasal dari versi lama dan tidak direproduksi. | Perbandingan dengan versi lama | terbuka |
| A-014 | Episode nyata 24 Jan 2025: "malam" ditafsirkan T−0 = pukul 21.00 WIB. Hasil episode (terganggu atau tidak) belum terkonfirmasi di katalog, sehingga ringkasan T−0 ditampilkan untuk kedua kemungkinan. | Demo episode nyata | terbuka |
| A-015 | Latensi data: NASA POWER 72 jam, IMERG Early dan GSMaP NRT 4 jam, Glapan 2 jam, generator dummy 3 jam. | Informasi yang tersedia pada jam keputusan | terbuka |

## Tahap 1 · Database

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-016 | Tabel di luar 14.5 ditambahkan: `pengguna` (bagian 15), `episode`, `laporan_lapangan` (laporan petugas dan jalan putus), `simulasi_run` (status tugas latar belakang), `sesi_demo` (bagian 16). Tabel time series diberi kolom `episode_id` ('' = observasi umum) agar episode sintetis tidak bercampur dengan observasi nyata. | Skema | konvensi |

## Tahap 2 · Sensing

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-017 | Tanggal harian NASA POWER diperlakukan sebagai tanggal WIB. **Temuan:** titik lokal, hulu, dan Gundih jatuh di sel grid NASA POWER yang sama sehingga nilainya identik; NASA POWER tidak dapat membedakan hujan hulu dari hujan lokal. Hujan hulu yang bermakna butuh IMERG/GSMaP (akun gratis) atau data BBWS. | Bukti hulu pada episode nyata lemah | terbuka |
| A-018 | Nilai `tp` prakiraan BMKG diasumsikan akumulasi 3 jam yang berakhir pada `local_datetime`; `analysis_date` dianggap UTC dan ditambah 7 jam sebagai waktu terbit. Periode yang sudah dimulai sebelum waktu terbit dibuang. | Waktu terbit prakiraan | terbuka |
| A-019 | Hujan harian dibagi rata ke 24 jam saat dipakai model muka air sintetis dan fitur per jam. | Puncak hujan harian teredam | terbuka |
| A-020 | Kode periksa K1–K3 metode OCR+LLM ditafsirkan: K1 = benar tanpa koreksi, K2 = benar setelah dikoreksi peneliti, K3 = ditolak. Hanya K1/K2 masuk katalog. | Katalog ocr_llm | terbuka |
| A-021 | Generator dummy: hujan anteseden dan badai lognormal berkorelasi antar lokasi (lokal–hulu 0,5; lokal–Gundih 0,5), puncak badai 6–30 jam sebelum T−0, galat prakiraan lognormal yang mengecil linear dari σ 0,8 (lead 72 jam) ke 0,15 (lead 0) dengan korelasi antarterbitan 0,6. Prakiraan tiap terbitan mencakup periode sampai T−0 + 6 jam. Model kebenaran disetel agar laju gangguan base sekitar 29% (low 13%, high 46%) dan sekitar 25% gangguan berupa gerusan. | Seluruh hasil simulasi | terbuka |
| A-022 | Titik Glapan 1970 (24 Jan 2025) tidak diketahui jamnya; diletakkan pukul 23.00 agar tidak dipakai sebelum waktunya. Akibatnya titik ini tidak masuk jam keputusan episode nyata (T−0 21.00) dan hanya dipakai sebagai pembanding model sintetis. | Episode nyata | terbuka |
| A-023 | Kode wilayah BMKG lokal: 33.15.17.2001 (Desa Penadaran, Kec. Gubug), terverifikasi dari respons API BMKG. Menggantikan A-008. | Prakiraan BMKG | terverifikasi |
| A-024 | Model bawaan metode ocr_llm: `claude-opus-5-5` dengan structured outputs dan fallback sisi server (`fallbacks: "default"`) bila model menolak; dapat diganti lewat LLM_MODEL di .env. | Biaya dan perilaku ekstraksi | konvensi |

## Tahap 3 · Inferensi

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-025 | Fitur lapis I: hujan lokal 1/3/5 hari dan hulu 3 hari dihitung sebagai akumulasi yang berakhir pada data terakhir yang tersedia (memperhitungkan latensi sumber); prakiraan = jumlah prakiraan terbitan terakhir dari jam keputusan sampai T−0; muka air = pembacaan Glapan terakhir yang tersedia dikurangi ambang Awas, dan kenaikannya 6 jam. Bila tidak ada data muka air, dipakai elevasi dasar model sintetis. | Masukan model | konvensi |
| A-026 | Model peluang: regresi logistik multinomial Bayesian (tidak/genangan/gerusan) dengan prior Gaussian, MAP dengan Newton, kovarians Laplace, prediktif Monte Carlo 200 sampel berseed tetap. Model bawaan dilatih pada 400 episode sintetis (seed latih terpisah dari SIM_SEED). Pada 200 episode uji sintetis: AUC sekitar 0,68 (T−72), 0,84 (T−24), 0,95 (T−0); kalibrasi mendekati diagonal. Angka ini sifat data sintetis, bukan kinerja nyata. | Kinerja lapis I | terbuka |
| A-027 | Laporan petugas "air di badan rel" mengalikan odds gangguan dengan rasio kemungkinan 20 (dummy); porsi genangan:gerusan dipertahankan. | Pembaruan bukti | terbuka |

## Tahap 4 · Gating

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-028 | Kurva pemicu: peluang antarprakiraan (tiap 6 jam) dimodelkan martingale Beta(k·p, k·(1−p)) dengan k = 12 (dummy). Bertindak satu langkah lebih awal 2% lebih murah, sehingga di batas waktu biaya = C (pola Regnier & Harr 2006; tanpa diskon ini menunggu hampir selalu menang). L efektif = L × faktor lama tutup saat ini dan dianggap tetap untuk sisa horizon. Tindakan diasumsikan mencegah seluruh L bila dijalankan sebelum batas waktunya. | Bentuk kurva dan status | terbuka |
| A-029 | Status "Terlambat" berlaku bila jam keputusan sudah melewati batas waktu siap tanpa persetujuan; tepat pada batas waktu tindakan masih dapat diputuskan. | Papan tindakan | konvensi |

## Tahap 5 · Aksi

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-030 | Penjaga klaim sengaja ketat: kata utuh "aman" atau "safe" dalam keluaran apa pun ditolak, termasuk dalam negasi ("tidak aman"), karena status jalur hanya ditetapkan KAI. Teks sistem ditulis tanpa kata tersebut; kata turunan seperti "keamanan" diperbolehkan. | Seluruh keluaran | konvensi |
| A-031 | Keputusan operator diikat ke jam episode (jam sebelum T−0). Persetujuan membekukan status tindakan; "batalkan" menghapus efek persetujuan (dianggap tidak dijalankan). Persetujuan pada jam yang batas waktunya lewat ditolak. | Log dan ringkasan | konvensi |
| A-032 | Label ringkasan T−0: sia-sia = dijalankan tanpa gangguan; terlambat = gangguan terjadi tanpa tindakan sampai batas waktu; terlalu awal = dijalankan (dan gangguan terjadi) lebih awal daripada saran SIGAP; tepat = selainnya. | Ringkasan dan demo | terbuka |
| A-033 | Peringatan maladaptasi: memutar via Gundih diberi peringatan bila hujan 24 jam Gundih ≥ 50 mm (kategori lebat BMKG); bus pengganti bila ada laporan jalan Semarang–Purwodadi putus. Pada NASA POWER, Gundih satu sel grid dengan koridor sehingga peringatan Gundih cenderung ikut hujan lokal. | Papan tindakan | terbuka |

## Tahap 6 · Simulasi

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-034 | Episode nyata 24 Jan 2025 memakai hujan NASA POWER nyata (harian, dibagi rata per jam), titik Glapan nyata, serta prakiraan dan muka air per jam sintetis berlabel (arsip prakiraan dan seri muka air belum ada). Hasil episode belum terkonfirmasi. | Demo episode nyata | terbuka |
| A-035 | Definisi operasional kebijakan: jam tetap = diputuskan sekali pada T−24 (atau di batas waktu bila lebih awal) dengan ambang statis; reaktif = bertindak setelah laporan air di badan rel; informasi sempurna = bertindak paling awal hanya bila gangguan terjadi. Semua kebijakan memakai peluang lapis I yang sama pada jam yang sama. | Perbandingan kebijakan | terbuka |
| A-036 | Konsentrasi Beta kurva pemicu dikalibrasi ulang dari 12 menjadi 7 berdasarkan lintasan peluang lapis I (k = rerata p(1−p) / rerata Δp² − 1 = 7,06 pada 300 episode sintetis base). Menggantikan nilai k di A-028. | Kurva pemicu | konvensi |
| A-037 | Pembanding RQ1: aturan hujan lokal = hujan lokal 3 hari teramati + prakiraan lokal sampai T−0 ≥ 100 mm; indeks adaptasi H-MHEWS = maks(kategori hujan BMKG dari hujan 24 jam/prakiraan, level 3 bila Glapan ≥ Awas), alarm bila ≥ 2. Alarm pada T−0 tidak dihitung (lead time nol). | Metrik deteksi | terbuka |

## Tahap 7 · API dan auth

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-038 | Parameter `jam` di API dinyatakan sebagai jam sebelum T−0 (mis. 24 = T−24) dan harus kelipatan interval keputusan. Endpoint detail dan lintasan episode memotong data pada jam yang diminta. | Kontrak API | konvensi |
| A-039 | Operator dan admin sama-sama boleh mencatat keputusan; log normal dibagi per episode (bukan per pengguna), log demo per sesi. Simulasi, kelola pengguna, dan reset demo khusus admin. Hitung ulang kurva dengan slider boleh untuk semua pengguna karena tidak mengubah params.json. | Otorisasi | terbuka |
| A-040 | Token JWT HS256 berlaku 480 menit; status aktif pengguna diperiksa ulang tiap permintaan sehingga pengguna yang dinonaktifkan langsung tertolak. | Keamanan prototipe | konvensi |

## Tahap 8 · Konsol

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-041 | Warna grafik memakai palet referensi tervalidasi (slot biru/oranye/aqua; diuji `validate_palette.js` di mode terang dan gelap); warna status hanya untuk status dan selalu disertai ikon dan label. Setiap grafik punya tampilan tabel. | Aksesibilitas konsol | konvensi |
| A-042 | Kurva pada grafik Operasi dihitung dengan faktor L efektif jam berjalan (dari sebaran lama tutup) sehingga dapat bergeser antarjam; kurva adalah aturan keputusan, bukan data masa depan. | Tampilan kurva | konvensi |

## Tahap 9 · Mode demo

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-043 | Laju putar otomatis demo diatur klien (pewaktu memanggil `/demo/{id}/langkah` tiap kecepatan × 6 detik selama status server "berjalan"); server menyimpan jam berjalan sehingga hasil tidak bergantung jam dinding. Keputusan demo hanya diterima pada jam yang sedang diputar. | Mode demo | konvensi |
| A-044 | Skenario cadangan presentasi = episode terganggu pertama dari 20 episode seed 2025 (bukan dipilih agar SIGAP tampak baik); cuplikan dibulatkan 6 desimal sebelum dihitung sidik SHA-256. | Keterulangan demo | konvensi |
| A-045 | Sesi demo hanya dapat dikendalikan pembuatnya atau admin; reset khusus admin. | Hak akses demo | terbuka |
