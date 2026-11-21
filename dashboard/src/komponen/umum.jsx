// Komponen umum konsol: label nyata/dummy, kartu grafik dengan tampilan tabel (setiap grafik
// punya kembaran tabel), angka utama, dan status tindakan (warna + ikon + label, tidak warna saja).
// Lapis: A (antarmuka).
import { useState } from "react";
import { STATUS } from "../tema.js";

export function LabelData({ label }) {
  const nyata = label === "nyata";
  const teks = { nyata: "data nyata", dummy: "data dummy", campuran: "campuran nyata + dummy", kosong: "kosong" }[label] || label;
  return <span className={`lencana ${nyata ? "nyata" : "dummy"}`} title="Label asal data (NFR-2)">{teks}</span>;
}

export function StatusTindakan({ status }) {
  const s = STATUS[status] || { warna: "#898781", ikon: "•" };
  return (
    <span className="status" style={{ color: "var(--text-primary)" }}>
      <span className="titik" style={{ background: s.warna }} aria-hidden="true" />
      <span aria-hidden="true">{s.ikon}</span>
      {status}
    </span>
  );
}

export function Stat({ label, nilai, ket }) {
  return (
    <div className="stat">
      <span className="label">{label}</span>
      <span className="nilai">{nilai}</span>
      {ket && <span className="muted" style={{ fontSize: 12 }}>{ket}</span>}
    </div>
  );
}

export function TabelData({ kolom, baris }) {
  return (
    <div className="gulir">
      <table>
        <thead><tr>{kolom.map((k) => <th key={k.kunci} className={k.angka ? "angka" : ""}>{k.judul}</th>)}</tr></thead>
        <tbody>
          {baris.map((b, i) => (
            <tr key={i}>{kolom.map((k) => (
              <td key={k.kunci} className={k.angka ? "angka" : ""}>{k.format ? k.format(b[k.kunci], b) : b[k.kunci] ?? "–"}</td>
            ))}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function KartuGrafik({ judul, ket, label, kolom, baris, aksi, children }) {
  const [tabel, setTabel] = useState(false);
  return (
    <section className="kartu">
      <div className="kartu-kepala">
        <h2>{judul}</h2>
        {label && <LabelData label={label} />}
        <span className="spasi" />
        {aksi}
        {kolom && (
          <button className="tombol kecil" onClick={() => setTabel(!tabel)} aria-pressed={tabel}>
            {tabel ? "Lihat grafik" : "Lihat tabel"}
          </button>
        )}
      </div>
      {ket && <p className="sekunder" style={{ marginTop: -6, fontSize: 12 }}>{ket}</p>}
      {tabel && kolom ? <TabelData kolom={kolom} baris={baris || []} /> : children}
    </section>
  );
}

export function Pesan({ galat }) {
  if (!galat) return null;
  return <p className="pesan-galat" role="alert">{String(galat.message || galat)}</p>;
}
