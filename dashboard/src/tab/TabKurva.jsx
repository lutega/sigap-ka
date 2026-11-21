// Tab Kurva pemicu: ambang per tindakan sepanjang horizon dan slider parameter C, L, P, waktu siap
// untuk melihat pergeseran kurva (FR-G4). Slider tidak mengubah params.json.
// Lapis: A (antarmuka) untuk lapis G.
import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { labelJam } from "../komponen/GrafikPeluangKurva.jsx";
import { KartuGrafik, Pesan, TabelData } from "../komponen/umum.jsx";
import { persen, rupiahJuta, useTema } from "../tema.js";

function Slider({ label, nilai, min, max, langkah, onUbah, format }) {
  return (
    <label className="isian" style={{ minWidth: 200 }}>
      <span>{label}: <strong className="angka">{format ? format(nilai) : nilai}</strong></span>
      <input type="range" min={min} max={max} step={langkah} value={nilai} onChange={(e) => onUbah(Number(e.target.value))} aria-label={label} />
    </label>
  );
}

export default function TabKurva() {
  const { palet } = useTema();
  const [preset, setPreset] = useState("base");
  const [daftar, setDaftar] = useState(null);
  const [tid, setTid] = useState("T1");
  const [nilai, setNilai] = useState(null);
  const [hasil, setHasil] = useState(null);
  const [galat, setGalat] = useState(null);

  useEffect(() => { api.get(`/tindakan?preset=${preset}`).then(setDaftar).catch(setGalat); }, [preset]);
  const t = daftar ? daftar.tindakan.find((x) => x.id === tid) : null;
  useEffect(() => { if (t) setNilai({ C: t.C, L: t.L, P: t.P, waktu_siap_jam: t.waktu_siap_jam }); }, [t && t.id, preset]); // eslint-disable-line

  useEffect(() => {
    if (!nilai || !t) return undefined;
    const h = setTimeout(() => {
      api.post("/kurva/hitung", { tindakan: tid, preset, ...nilai }).then((r) => { setHasil(r); setGalat(null); }).catch(setGalat);
    }, 250);
    return () => clearTimeout(h);
  }, [nilai, tid, preset]); // eslint-disable-line

  const data = useMemo(() => {
    if (!hasil) return [];
    const jam = Array.from(new Set([...hasil.kurva_bawaan.jam_sebelum_t0, ...hasil.kurva.jam_sebelum_t0])).sort((a, b) => b - a);
    return jam.map((j) => {
      const ib = hasil.kurva_bawaan.jam_sebelum_t0.indexOf(j);
      const is = hasil.kurva.jam_sebelum_t0.indexOf(j);
      return { label: labelJam(j), bawaan: ib >= 0 ? hasil.kurva_bawaan.ambang[ib] : null, slider: is >= 0 ? hasil.kurva.ambang[is] : null };
    });
  }, [hasil]);

  return (
    <>
      <section className="kartu baris-filter">
        <label className="isian">Preset
          <select value={preset} onChange={(e) => setPreset(e.target.value)}>
            {["low", "base", "high"].map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label className="isian">Tindakan
          <select value={tid} onChange={(e) => setTid(e.target.value)}>
            {daftar && daftar.tindakan.map((x) => <option key={x.id} value={x.id}>{x.id} · {x.nama}</option>)}
          </select>
        </label>
        {t && nilai && (
          <>
            <Slider label="C biaya tindakan" nilai={nilai.C} min={1} max={Math.max(t.C * 3, 10)} langkah={1} format={rupiahJuta}
              onUbah={(v) => setNilai({ ...nilai, C: v })} />
            <Slider label="L kerugian tanpa persiapan" nilai={nilai.L} min={Math.ceil(nilai.C) + 1} max={t.L * 3} langkah={5} format={rupiahJuta}
              onUbah={(v) => setNilai({ ...nilai, L: v })} />
            <Slider label="P denda alarm palsu" nilai={nilai.P} min={0} max={Math.max(t.P * 4, 50)} langkah={1} format={rupiahJuta}
              onUbah={(v) => setNilai({ ...nilai, P: v })} />
            <Slider label="Batas waktu siap" nilai={nilai.waktu_siap_jam} min={0} max={72} langkah={6} format={(v) => labelJam(v)}
              onUbah={(v) => setNilai({ ...nilai, waktu_siap_jam: v })} />
            <button className="tombol" onClick={() => setNilai({ C: t.C, L: t.L, P: t.P, waktu_siap_jam: t.waktu_siap_jam })}>Kembalikan</button>
          </>
        )}
        <Pesan galat={galat} />
      </section>

      <KartuGrafik judul={`Kurva pemicu ${tid}${t ? ` · ${t.nama}` : ""}`} label="dummy"
        ket={hasil ? `Ambang di batas waktu (C+P)/(L+P): bawaan ${persen(hasil.kurva_bawaan.ambang_statis, 1)}, slider ${persen(hasil.kurva.ambang_statis, 1)}. Peluang di atas kurva berarti "Putuskan sekarang". ${hasil.catatan}` : ""}
        kolom={[{ kunci: "label", judul: "Jam" }, { kunci: "bawaan", judul: "Kurva bawaan", angka: true, format: (v) => persen(v, 1) },
          { kunci: "slider", judul: "Kurva slider", angka: true, format: (v) => persen(v, 1) }]}
        baris={data}>
        <div className="wadah-grafik" role="img" aria-label="Kurva pemicu bawaan dan hasil slider">
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 16, right: 32, bottom: 8, left: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: palet.sumbu }} />
              <YAxis domain={[0, 1]} tickFormatter={(v) => persen(v)} tickLine={false} axisLine={false} width={44} />
              <Tooltip formatter={(v, n) => [persen(v, 1), n]} contentStyle={{ color: palet.teks }} />
              <Legend verticalAlign="top" height={28} iconType="plainline" />
              {hasil && <ReferenceLine y={hasil.kurva.ambang_statis} stroke={palet.redup}
                label={{ value: "ambang statis (slider)", position: "insideBottomLeft", fill: palet.teks2, fontSize: 11 }} />}
              <Line type="stepAfter" dataKey="bawaan" name="Kurva bawaan params.json" stroke={palet.seri1} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="stepAfter" dataKey="slider" name="Kurva dengan slider" stroke={palet.seri2} strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </KartuGrafik>

      {daftar && (
        <section className="kartu">
          <div className="kartu-kepala"><h2>Parameter tindakan preset {daftar.preset}</h2><span className="lencana dummy">dummy</span>
            <span className="muted" style={{ fontSize: 12 }}>satuan {daftar.satuan_biaya}</span></div>
          <TabelData baris={daftar.tindakan} kolom={[{ kunci: "id", judul: "Id" }, { kunci: "nama", judul: "Tindakan" },
            { kunci: "keputusan_sebelum", judul: "Diputuskan sebelum" }, { kunci: "C", judul: "C", angka: true },
            { kunci: "L", judul: "L", angka: true }, { kunci: "P", judul: "P", angka: true },
            { kunci: "waktu_siap_jam", judul: "Batas", format: (v) => labelJam(v) },
            { kunci: "ambang_statis", judul: "(C+P)/(L+P)", angka: true, format: (v) => persen(v, 1) }]} />
        </section>
      )}
    </>
  );
}
