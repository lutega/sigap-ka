# SIGAP-KA: Arsitektur Sistem (Executive Summary)

Ringkasan tingkat tinggi dari deck Overview dan Update Tim SIGAP-KA (posisi 5 November 2026).

## Untuk apa

SIGAP-KA membantu pengendali operasi KA di koridor Brumbung–Karangjati, Grobogan, memutuskan **kapan** tiap tindakan kontinjensi diaktifkan saat banjir mengancam, sebelum air terlihat di rel. Sistem ini tidak membuat peringatan dini baru. Tugasnya mengubah peringatan yang sudah ada menjadi tindakan tepat waktu.

## Alur besar: lima lapis SIGAP

**Masukan → S (Sensing) → I (Inferensi) → G (Gating) → A (Aksi) → Operator dan KAI**, dengan **P (Policy)** sebagai aturan yang membingkai semuanya.

&#91;embedded content: Arsitektur SIGAP-KA · input, lima lapis, keputusan\]

Empat jenis data masuk ke lapis S, diolah sampai lapis A menjadi usulan, lalu operator memutuskan dan KAI menetapkan status jalur. Bila usulannya tunggu, sistem menghitung ulang saat prakiraan berikutnya masuk.

| Lapis | Fungsi | Keluaran |
| --- | --- | --- |
| S · Sensing | Mengumpulkan hujan, prakiraan, muka air, kejadian | Data terstruktur, ditandai nyata atau dummy |
| I · Inferensi | Menaksir kondisi jalur | Peluang gangguan, mekanisme (genangan atau gerusan), perkiraan lama tutup |
| G · Gating (inti) | Membandingkan peluang dengan kurva pemicu tiap tindakan | Status per tindakan: putuskan sekarang atau tunggu prakiraan berikutnya |
| A · Aksi | Menyajikan usulan di konsol | Papan 9 tindakan dengan tombol Setujui atau Tolak, beserta log keputusan |
| P · Policy | Biaya alarm palsu, berbagi data | Dibahas kualitatif di laporan |

## Masukan (input)

- **Hujan lokal dan hulu**: NASA POWER (nyata), GPM IMERG (rencana)
- **Prakiraan hujan**: arsip GEFS (ditunda, bukan jalur kritis)
- **Muka air Bendung Glapan**: rilis BNPB (sebagian nyata), seri waktu diminta ke BBWS
- **Katalog kejadian gangguan**: pengumuman KAI121/Daop 4 dan berita (sebagian nyata)
- **Banjir, tanggul, jalan putus**: BNPB dan BPBD Grobogan
- **Parameter keputusan**: biaya tindakan (C), kerugian bila tidak bersiap (L), denda alarm palsu (P), waktu siap tiap tindakan, jadwal KA. Sebagian besar masih dummy di params.json.

## Strategi data: inti dan tambahan

Model inti berjalan dengan data yang bisa diunduh bebas. Data yang perlu surat permohonan resmi menjadi data tambahan untuk kalibrasi dan peningkatan akurasi, bukan jalur kritis.

| Kelompok | Sumber | Isi | Cara akses |
| --- | --- | --- | --- |
| Inti | NASA POWER | Hujan harian, grid kasar | Unduh/API, tanpa akun |
| Inti | GPM IMERG (NASA/JAXA) | Hujan satelit per 30 menit, grid sekitar 10 km, untuk hujan hulu | NASA GES DISC, akun Earthdata gratis |
| Inti | GSMaP (JAXA) | Hujan satelit hampir real-time | Portal JAXA, akun gratis |
| Inti | BMKG (publik) | Prakiraan dan peringatan dini cuaca terkini | Situs dan data terbuka BMKG |
| Inti | KAI121, Daop 4, berita, BNPB, BPBD | Katalog kejadian gangguan | Publik |
| Tambahan | BBWS Pemali Juana | Pos hujan hulu, muka air Tuntang dan Bendung Glapan | Surat permohonan |
| Tambahan | BMKG (detail) | Data stasiun, AWS, radar sekitar Semarang | Surat permohonan |
| Tambahan | Arsip prakiraan | Prakiraan lama untuk uji pada jam keputusan | Surat permohonan |
| Tambahan | Praktisi KAI | Biaya memutar dan pembatalan | Wawancara |

## Keluaran (output)

- Peluang jalur terganggu dan perkiraan lama penutupan
- Rekomendasi per tindakan (T1–T9): **putuskan sekarang** atau **tunggu**
- Log keputusan operator dan perbandingan biaya keputusan operator dengan saran SIGAP di akhir episode
- Hasil simulasi kebijakan: SIGAP sekitar 14% lebih murah daripada pembanding terbaik (parameter dummy)

## Untuk siapa

- **Pengguna utama: pengendali operasi KA.** Memilih tindakan berdasarkan usulan sistem.
- **KAI (pihak berwenang)** tetap menetapkan status jalur dari pemeriksaan lapangan. Sistem tidak pernah menyatakan jalur aman.
- **Penerima informasi lain**: unit jalan rel dan jembatan, humas Daop, BPBD Grobogan, dan penumpang lewat informasi lebih awal.

## Contoh tindakan yang diatur

Informasi penumpang dan refund, menahan KA di stasiun asal, memutar via Gundih atau Solo, mobilisasi bus pengganti, menyiagakan petugas Dapsus dan AMUS, hingga pembatalan. Tindakan murah dipicu lebih awal, sedangkan tindakan mahal seperti pembatalan butuh peluang tinggi.

## Batas penting

Masih prototipe dengan data campuran. Keunggulan 14% adalah batas atas menurut asumsi model sendiri, dan uji penentunya butuh prakiraan nyata.

## Mockup konsol

&#91;embedded content: Mockup konsol · tab Operasi, ilustrasi\]

Ilustrasi tab Operasi: grafik kiri menunjukkan kapan peluang memotong kurva pemicu, papan kanan berisi usulan tiap tindakan dengan tombol Setujui atau Tolak. Status yang tampil hanya contoh; deck menyebut 9 tindakan, enam di antaranya ditampilkan.

## Implementasi yang dipilih

Program dibangun dari awal dengan Python. Modul S, I, G, A diekspos lewat REST API FastAPI, data disimpan di PostgreSQL + TimescaleDB, dashboard React + Vite + Recharts diawali halaman login (akun awal admin/admin, admin dapat menambah pengguna). Pengaturan seperti preset parameter dan metode katalog kejadian dipilih lewat file `.env`. Untuk ujian dan presentasi tersedia mode demo yang memutar ulang episode secara offline. Rincian ada di Spesifikasi Fungsional bagian 8–16 dan dokumen Konteks Peran Agen.
