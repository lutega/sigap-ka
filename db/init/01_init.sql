-- Dijalankan sekali saat volume database pertama kali dibuat (docker-entrypoint-initdb.d).
-- Mengaktifkan TimescaleDB di database utama dan membuat database uji terpisah.
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE DATABASE sigap_test;
\c sigap_test
CREATE EXTENSION IF NOT EXISTS timescaledb;
