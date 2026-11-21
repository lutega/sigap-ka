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
| A-008 | Kode wilayah BMKG (adm4) untuk desa di Kec. Gubug di params.json adalah perkiraan. | Prakiraan BMKG bisa gagal diambil | terbuka |
| A-009 | Prior koefisien lapis I (blok `inferensi.prior_rerata`) adalah penilaian awal pengembang, bukan ahli; preset low/base/high mengubah pengali rerata dan simpangan prior. | Sensitivitas lapis I | terbuka |
| A-010 | Model "kebenaran" generator dummy (blok `dummy.kebenaran`) sengaja berbeda dari prior inferensi agar evaluasi tidak melingkar sempurna. | Hasil simulasi | konvensi |
| A-011 | Faktor L skenario lama tutup (pendek 0,6; sedang 1,0; panjang 1,8) dan peluang bersyarat mekanisme adalah dummy; arah kualitatifnya mengikuti 9.2 (genangan jam–1 hari, gerusan hari–minggu). | Kerugian L efektif | terbuka |
| A-012 | Kategori hujan harian BMKG (sedang 20, lebat 50, sangat lebat 100, ekstrem 150 mm/hari) dipakai untuk indeks adaptasi H-MHEWS; perlu dicek tim. H-MHEWS hanya pembanding. | Pembanding RQ1 | terbuka |
| A-013 | `sigap_data_proyek_minor.zip` tidak tersedia di repo, sehingga kode, nilai dummy, dan model sintetis dibangun ulang. Angka "SIGAP 14% lebih murah" dan "model sintetis 1768" berasal dari versi lama dan tidak direproduksi. | Perbandingan dengan versi lama | terbuka |
| A-014 | Episode nyata 24 Jan 2025: "malam" ditafsirkan T−0 = pukul 21.00 WIB. Hasil episode (terganggu atau tidak) belum terkonfirmasi di katalog, sehingga ringkasan T−0 ditampilkan untuk kedua kemungkinan. | Demo episode nyata | terbuka |
| A-015 | Latensi data: NASA POWER 72 jam, IMERG Early dan GSMaP NRT 4 jam, Glapan 2 jam, generator dummy 3 jam. | Informasi yang tersedia pada jam keputusan | terbuka |
