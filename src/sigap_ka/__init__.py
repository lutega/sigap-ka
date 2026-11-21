"""
Tujuan      : Paket modular data input (inputs/) dan fitur (features/) SIGAP-KA untuk prototipe:
              satu modul per sumber data, keluaran berskema seragam (tanggal, zona, nilai, sumber,
              status_data).
Lapis       : S (Sensing) dan penyiapan fitur lapis I.
Sumber      : data/raw/bmkg (BMKG), data/processed (IMERG, Glapan nyata), config/params.json.
Masukan     : -
Keluaran    : data/interim/*.csv dan data/processed/*_features.csv.
Keterbatasan: Melengkapi paket lapis S yang ada (sensing/); adapter ke tabel standar lama ada di
              inputs/base.py. Jalankan modul dengan PYTHONPATH=src (pytest sudah diatur).
"""
