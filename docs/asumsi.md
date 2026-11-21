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
| A-014 | Episode nyata 24 Jan 2025: T−0 = **22.25 WIB**, jam tutup sementara menurut detikTravel (26/1/2025) dan Liputan6 (25/1/2025) yang mengutip KAI (kandidat K03). Sebelumnya "malam" ditafsirkan 21.00. Hasil episode tetap belum terkonfirmasi di katalog, sehingga ringkasan T−0 ditampilkan untuk kedua kemungkinan. | Demo episode nyata | terbuka (perlu verifikasi tim) |
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
| A-022 | Titik Glapan 1970 kini berjam 25 Jan 2025 00.00 WIB (rilis BNPB, A-056); titik ini tetap sesudah T−0 22.25 sehingga tidak masuk jam keputusan episode nyata dan hanya dipakai sebagai pembanding model sintetis. | Episode nyata | konvensi |
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

## Tahap 10 · Uji menyeluruh

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-046 | Cadangan presentasi tanpa Docker memakai berkas SQLite (`python -m simulation.cadangan_sqlite`) dengan isi yang sama; hanya untuk demo bila jaringan Docker bermasalah, bukan pengganti TimescaleDB. | Ketahanan demo | konvensi |
| A-047 | Pengujian integrasi yang andal di Windows dijalankan di dalam jaringan Docker (`docker compose --profile uji run --rm uji`), karena jalur localhost:5432 lewat penerus port Docker Desktop di mesin pengembang lambat dan sesekali memutus koneksi. | Prosedur uji | konvensi |

## Pembaruan 22 Nov 2026 · GPM IMERG

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-048 | Hujan IMERG diambil per titik (satu sel 0,1°): lokal (−7,05; 110,65), hulu (−7,25; 110,45), Gundih (−7,25; 110,95), lewat Giovanni Time Series API. Hari IMERG (UTC) dicatat mulai 07.00 WIB. Episode nyata memakai **IMERG Late** (latensi 14 jam, tersedia pada jam keputusan); **IMERG Final** (latensi sekitar 105 hari) hanya untuk analisis riwayat agar tidak mengintip masa depan. Satu sel belum mewakili rerata daerah tangkapan Tuntang. | Bukti hulu episode nyata | terbuka |
| A-017 (pembaruan) | NASA POWER kini menjadi cadangan; masalah satu sel grid untuk lokal/hulu/Gundih tidak lagi memengaruhi episode nyata karena IMERG tersedia. | – | diperbarui |

## Pembaruan 22 Nov 2026 · Modul input/fitur modular (src/sigap_ka)

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-049 | Hari curah hujan BMKG diasumsikan diukur pukul 07.00 WIB untuk 24 jam sebelumnya, sedangkan hari IMERG adalah hari UTC (07.00–07.00 WIB); tanggal BMKG D kira-kira setara hari IMERG D−1. Belum dikoreksi di fitur harian (perlu dicek dengan berkas BMKG asli). | Perbandingan BMKG–IMERG, fitur gabungan | terbuka |
| A-050 | Estimasi TMA Glapan sintetis menganggap hari tanpa data hujan = 0 mm (jumlahnya dilaporkan); hujan harian dibagi rata per jam. | Seri TMA sintetis | terbuka |
| A-051 | Anchoring TMA sintetis ke satu titik nyata (1970, 25 Jan 2025 00.00 WIB menurut rilis BNPB; anchoring memakai maksimum harian) memberi faktor skala sekitar 1,9; akibatnya TMA sintetis melewati ambang Awas sekitar 14% waktu (2024–2026). Titik itu tidak bisa sekaligus dipakai untuk menguji model; perlu seri BBWS. | Fitur Glapan sintetis | terbuka |
| A-052 | Stasiun BMKG yang tersedia di portal hanya di Kota Semarang (Ahmad Yani, Klimatologi Jawa Tengah), sekitar 25–30 km dari koridor dan hulu; dipetakan ke zona `semarang_pembanding` untuk validasi IMERG, bukan masukan zona. Hari BMKG kosong di zona lokal/hulu/Gundih diisi IMERG Late per hari (sumber dicatat per baris). | Fitur hujan | konvensi |
| A-053 | Data BMKG yang tersedia hanya **bulanan** (portal "Data Iklim Bulanan"), sehingga tidak dipakai sebagai fitur harian model; hanya untuk validasi IMERG. Baris bulanan ditandai `resolusi = bulanan` dan dikecualikan dari fitur harian. | Fitur hujan | konvensi |
| A-054 | Validasi di sel IMERG Semarang (−6,95; 110,35; dua stasiun BMKG ~1 km terpisah, sel yang sama): IMERG Late bias +17,4% (24 bulan, r 0,82, MAE 78 mm/bulan); pada 11 bulan yang juga tersedia Final: Late +26,6% (r 0,84), Final +35,6% (r 0,93). Selisih antarstasiun −5,6% (r 0,96) sebagai acuan galat ukur. Sel ini pesisir dan berjarak 25–30 km dari koridor, sehingga belum dipakai untuk mengoreksi IMERG di koridor/hulu; dicatat sebagai ketidakpastian besaran hujan IMERG (cenderung lebih tinggi dari penakar). | Batas klaim lapis S | terbuka |

## Perbaikan lanjutan · katalog kandidat dan uji balik (22 Nov 2026)

| Kode | Asumsi | Dampak | Status |
| --- | --- | --- | --- |
| A-055 | Katalog kejadian **kandidat** (K01–K09, `data/manual/kejadian_kandidat.csv`) dihimpun dari berita publik dan rilis BNPB/KAI yang dikutip media; bukan data resmi dan tidak menggantikan E1–E6. T-0 kandidat = jam tutup/awal gangguan/deteksi yang dinyatakan sumber; tanpa jam → 00.00 hari kejadian (tidak memakai informasi hari itu); "malam" tanpa jam → 18.00. Kandidat dengan gangguan ringan (terlambat, satu jalur) tetap dihitung sebagai kejadian gangguan. | Uji balik model pada hujan nyata | terbuka |
| A-056 | Titik Glapan 1970 dipindah dari "24 Jan 2025 23.00, jam tidak diketahui" ke **25 Jan 2025 00.00 WIB** sesuai rilis BNPB (tautan di `_nyata` dan CSV manual). Titik ini tetap sesudah T-0 episode nyata sehingga tidak masuk keputusan sebelum T-0. | Episode nyata, anchoring TMA sintetis | konvensi |
| A-057 | Ketersediaan IMERG Late harian: hari UTC D (07.00 WIB D s.d. 07.00 D+1) baru tersedia 21.00 WIB D+1 (latensi 14 jam setelah akhir hari). Pada jam keputusan, hujan 14–38 jam terakhir belum terlihat model. | Uji balik, episode nyata | konvensi |
| A-058 | Uji balik memakai **prakiraan persistensi** (laju hujan harian terakhir yang tersedia, diteruskan sampai T−0 + 6 jam) sebagai prakiraan utama karena tidak memuat informasi masa depan. Prakiraan sintetis dibangkitkan dari hujan aktual (memuat informasi masa depan), sehingga hanya dipakai sebagai batas atas. | Uji balik | konvensi |
| A-059 | Pemindaian harian memakai T−0 = 12.00 WIB tiap hari. Hari kejadian = tanggal kandidat; hari dalam ±3 hari dari kejadian dibuang dari pembanding. Hari tanpa berita diperlakukan sebagai "lain" walau mungkin ada gangguan yang tidak diberitakan. | Metrik pemisahan (AUC) | terbuka |
| A-060 | Skala bias uji kepekaan: 1/1,266 ≈ 0,79 dan 1/1,174 ≈ 0,852 dari validasi IMERG Late di sel Semarang (A-054), ditambah 0,8 dan 1,2 sebagai rentang ±20%. Faktor diterapkan seragam ke lokal, hulu, dan Gundih. | Uji kepekaan | konvensi |
| A-061 | Generator dummy (dasar pelatihan lapis I) jauh lebih basah daripada hari nyata IMERG: median hujan hulu 72 jam 81 mm ≈ persentil 98 hari nyata. Kejadian kandidat terjadi pada 40–100 mm, sedangkan model kebenaran generator memberi peluang gangguan rendah pada rentang itu. Parameter generator **tidak diubah** (berstatus dummy, keputusan tim); dampaknya, peluang lapis I pada data nyata rendah secara absolut walau urutannya benar. | Skala peluang lapis I pada data nyata | terbuka |
