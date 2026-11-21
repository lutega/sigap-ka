// Tab Prediksi: peluang gangguan per mekanisme sepanjang episode (sampai jam terpilih), sebaran
// lama tutup, dan bukti utama (lapis I, spesifikasi 9).
// Lapis: A (antarmuka) untuk lapis I.
import { useEffect, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { labelJam } from "../komponen/GrafikPeluangKurva.jsx";
import { KartuGrafik, Pesan, Stat, TabelData } from "../komponen/umum.jsx";
import { persen, useTema } from "../tema.js";

export default function TabPrediksi({ episode }) {
  const { palet } = useTema();
  const [epId, setEpId] = useState("");
  const [jam, setJam] = useState(24);
  const [pred, setPred] = useState(null);
  const [lintasan, setLintasan] = useState([]);
  const [galat, setGalat] = useState(null);

  useEffect(() => { if (!epId && episode.length) setEpId(episode[0].id); }, [episode, epId]);
  useEffect(() => {
    if (!epId) return;
    Promise.all([api.get(`/episode/${epId}/prediksi?jam=${jam}`), api.get(`/episode/${epId}/lintasan?sampai_jam=${jam}`)])
      .then(([p, l]) => { setPred(p); setLintasan(l); setGalat(null); }).catch(setGalat);
  }, [epId, jam]);

  const ep = episode.find((e) => e.id === epId);
  const dataLintasan = lintasan.map((l) => ({ label: labelJam(l.jam_sebelum_t0), genangan: l.peluang_genangan, gerusan: l.peluang_gerusan }));
  const dataLama = pred ? ["pendek", "sedang", "panjang"].map((s) => ({ skenario: s, peluang: pred.lama_tutup.sebaran[s] })) : [];

  return (
    <>
      <section className="kartu baris-filter">
        <label className="isian">Episode
          <select value={epId} onChange={(e) => setEpId(e.target.value)}>
            {episode.map((e) => <option key={e.id} value={e.id}>{e.nama} ({e.jenis})</option>)}
          </select>
        </label>
        <label className="isian">Jam keputusan
          <select value={jam} onChange={(e) => setJam(Number(e.target.value))}>
            {(ep ? ep.jam_keputusan : []).map((j) => <option key={j} value={j}>{labelJam(j)}</option>)}
          </select>
        </label>
        <span className="muted" style={{ fontSize: 12 }}>Model hanya memakai informasi yang tersedia sampai jam keputusan.</span>
        <Pesan galat={galat} />
      </section>

      {pred && (
        <section className="kartu grid-3">
          <Stat label="Peluang gangguan" nilai={persen(pred.peluang)} ket={pred.waktu.replace("T", " ")} />
          <Stat label="Mekanisme dominan" nilai={pred.mekanisme_dominan} ket={`genangan ${persen(pred.peluang_genangan)} · gerusan ${persen(pred.peluang_gerusan)}`} />
          <Stat label="Harapan lama tutup bila terganggu" nilai={`${Math.round(pred.lama_tutup.harapan_jam)} jam`} ket={`faktor kerugian L × ${pred.lama_tutup.faktor_L.toFixed(2)}`} />
        </section>
      )}

      <div className="grid-2">
        <KartuGrafik judul="Peluang gangguan per mekanisme" label="dummy"
          ket="Dua mekanisme saling lepas; tinggi tumpukan = peluang gangguan total."
          kolom={[{ kunci: "label", judul: "Jam" }, { kunci: "genangan", judul: "Genangan", angka: true, format: (v) => persen(v, 1) },
            { kunci: "gerusan", judul: "Gerusan", angka: true, format: (v) => persen(v, 1) }]}
          baris={dataLintasan}>
          <div className="wadah-grafik" role="img" aria-label="Peluang genangan dan gerusan menurut jam keputusan">
            <ResponsiveContainer>
              <AreaChart data={dataLintasan} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: palet.sumbu }} />
                <YAxis domain={[0, 1]} tickFormatter={(v) => persen(v)} tickLine={false} axisLine={false} width={44} />
                <Tooltip formatter={(v, n) => [persen(v, 1), n]} contentStyle={{ color: palet.teks }} />
                <Legend verticalAlign="top" height={28} />
                <Area type="linear" dataKey="genangan" name="Genangan" stackId="1" stroke={palet.seri1} fill={palet.seri1} fillOpacity={0.35} strokeWidth={2} isAnimationActive={false} />
                <Area type="linear" dataKey="gerusan" name="Gerusan" stackId="1" stroke={palet.seri2} fill={palet.seri2} fillOpacity={0.35} strokeWidth={2} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </KartuGrafik>

        <KartuGrafik judul="Sebaran lama tutup bila terganggu" label="dummy"
          ket="Rentang jam tiap skenario dan peluang bersyaratnya diatur di params.json (nilai dummy)."
          kolom={[{ kunci: "skenario", judul: "Skenario" }, { kunci: "peluang", judul: "Peluang", angka: true, format: (v) => persen(v, 1) }]}
          baris={dataLama}>
          <div className="wadah-grafik" role="img" aria-label="Sebaran skenario lama tutup">
            <ResponsiveContainer>
              <BarChart data={dataLama} layout="vertical" margin={{ top: 8, right: 40, bottom: 8, left: 16 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => persen(v)} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="skenario" tickLine={false} axisLine={{ stroke: palet.sumbu }} width={64} />
                <Tooltip formatter={(v) => persen(v, 1)} contentStyle={{ color: palet.teks }} />
                <Bar dataKey="peluang" name="Peluang" fill={palet.seri1} radius={[0, 4, 4, 0]} barSize={22} isAnimationActive={false}
                  label={{ position: "right", formatter: (v) => persen(v), fill: palet.teks2, fontSize: 12 }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </KartuGrafik>
      </div>

      {pred && (
        <section className="kartu">
          <div className="kartu-kepala"><h2>Bukti yang paling memengaruhi hasil</h2></div>
          <TabelData baris={pred.bukti} kolom={[{ kunci: "keterangan", judul: "Bukti" }, { kunci: "nilai", judul: "Nilai", angka: true },
            { kunci: "satuan", judul: "Satuan" }, { kunci: "kontribusi", judul: "Kontribusi logit", angka: true }, { kunci: "arah", judul: "Pengaruh" }]} />
          <h3 style={{ margin: "12px 0 6px" }}>Semua fitur pada jam ini</h3>
          <TabelData baris={Object.entries(pred.fitur).map(([k, v]) => ({ fitur: k, nilai: v }))}
            kolom={[{ kunci: "fitur", judul: "Fitur" }, { kunci: "nilai", judul: "Nilai", angka: true }]} />
          {pred.catatan.map((c, i) => <p key={i} className="catatan-kewenangan">{c}</p>)}
        </section>
      )}
    </>
  );
}
