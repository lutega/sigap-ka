// Tab Simulasi: rerata biaya per episode untuk enam kebijakan (300 episode), selisih berpasangan
// SIGAP terhadap pembanding, dan tombol jalankan simulasi (khusus admin).
// Lapis: A (antarmuka) untuk evaluasi. SIGAP ditonjolkan; kebijakan lain abu-abu (penekanan).
import { useCallback, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { KartuGrafik, Pesan, TabelData } from "../komponen/umum.jsx";
import { rupiahJuta, useTema } from "../tema.js";

export default function TabSimulasi({ pengguna, info }) {
  const { palet } = useTema();
  const [runs, setRuns] = useState([]);
  const [runId, setRunId] = useState("");
  const [hasil, setHasil] = useState(null);
  const [form, setForm] = useState({ preset: "base", n: 300, seed: 42 });
  const [galat, setGalat] = useState(null);
  const [menunggu, setMenunggu] = useState(null);

  const muatRuns = useCallback(() => api.get("/simulasi").then((r) => {
    setRuns(r);
    const selesai = r.filter((x) => x.status === "selesai");
    if (!runId && selesai.length) setRunId((selesai.find((x) => x.preset === "base") || selesai[0]).run_id);
  }).catch(setGalat), [runId]);

  useEffect(() => { muatRuns(); }, [muatRuns]);
  useEffect(() => { if (runId) api.get(`/simulasi/${runId}`).then(setHasil).catch(setGalat); }, [runId]);

  useEffect(() => {
    if (!menunggu) return undefined;
    const h = setInterval(async () => {
      try {
        const r = await api.get(`/simulasi/${menunggu}`);
        if (r.status === "selesai" || r.status === "gagal") {
          setMenunggu(null);
          await muatRuns();
          setRunId(r.run_id);
          if (r.status === "gagal") setGalat(new Error(r.pesan));
        }
      } catch (e) { setGalat(e); setMenunggu(null); }
    }, 2000);
    return () => clearInterval(h);
  }, [menunggu, muatRuns]);

  async function jalankan() {
    try {
      const r = await api.post("/simulasi", { preset: form.preset, n: Number(form.n), seed: Number(form.seed) });
      setMenunggu(r.run_id);
      setGalat(null);
    } catch (e) { setGalat(e); }
  }

  const ringkas = hasil && hasil.ringkasan;
  const urutan = ["sigap", "jam_tetap_24", "ambang_tetap_05", "cost_loss_batas", "reaktif", "informasi_sempurna"];
  const data = ringkas ? urutan.filter((k) => k in ringkas.rerata_biaya).map((k) => ({
    kunci: k, kebijakan: ringkas.nama_kebijakan[k], rerata: ringkas.rerata_biaya[k],
    selisih: ringkas.selisih_berpasangan_sigap && ringkas.selisih_berpasangan_sigap[k],
  })) : [];

  return (
    <>
      <section className="kartu baris-filter">
        <label className="isian">Hasil simulasi
          <select value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.filter((r) => r.status === "selesai").map((r) => (
              <option key={r.run_id} value={r.run_id}>{r.preset} · {r.n} episode · seed {r.seed} · {String(r.dibuat).slice(0, 16).replace("T", " ")}</option>
            ))}
          </select>
        </label>
        {pengguna.level === "admin" && (
          <>
            <label className="isian">Preset
              <select value={form.preset} onChange={(e) => setForm({ ...form, preset: e.target.value })}>
                {["low", "base", "high"].map((p) => <option key={p}>{p}</option>)}
              </select>
            </label>
            <label className="isian">Episode <input type="number" min={1} max={2000} value={form.n} onChange={(e) => setForm({ ...form, n: e.target.value })} style={{ width: 90 }} /></label>
            <label className="isian">Seed <input type="number" value={form.seed} onChange={(e) => setForm({ ...form, seed: e.target.value })} style={{ width: 80 }} /></label>
            <button className="tombol utama" onClick={jalankan} disabled={!!menunggu}>{menunggu ? "Berjalan…" : "Jalankan simulasi"}</button>
          </>
        )}
        <Pesan galat={galat} />
      </section>

      <KartuGrafik judul="Rerata biaya per episode menurut kebijakan" label="dummy"
        ket={ringkas ? `${hasil.n} episode sintetis, preset ${hasil.preset}, seed ${hasil.seed}. Laju gangguan ${(100 * ringkas.laju_gangguan).toFixed(0)}%. Pembanding terbaik: ${ringkas.nama_kebijakan[ringkas.pembanding_terbaik]} (SIGAP ${ringkas.sigap_vs_pembanding_terbaik_persen > 0 ? "+" : ""}${ringkas.sigap_vs_pembanding_terbaik_persen}%). ${ringkas.catatan}` : "Belum ada hasil simulasi."}
        kolom={[{ kunci: "kebijakan", judul: "Kebijakan" }, { kunci: "rerata", judul: "Rerata biaya", angka: true, format: rupiahJuta },
          { kunci: "selisih", judul: "Selisih SIGAP − kebijakan (KI 95%)", angka: true,
            format: (v) => (v ? `${rupiahJuta(v.rerata)} [${Math.round(v.ki95[0])}, ${Math.round(v.ki95[1])}]` : "–") }]}
        baris={data}>
        <div className="wadah-grafik" role="img" aria-label="Rerata biaya enam kebijakan">
          <ResponsiveContainer>
            <BarChart data={data} layout="vertical" margin={{ top: 8, right: 72, bottom: 8, left: 24 }}>
              <CartesianGrid horizontal={false} />
              <XAxis type="number" tickFormatter={(v) => Math.round(v)} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="kebijakan" width={200} tickLine={false} axisLine={{ stroke: palet.sumbu }} />
              <Tooltip formatter={(v) => rupiahJuta(v)} contentStyle={{ color: palet.teks }} />
              <Bar dataKey="rerata" name="Rerata biaya" radius={[0, 4, 4, 0]} barSize={20} isAnimationActive={false}
                label={{ position: "right", formatter: (v) => Math.round(v), fill: palet.teks2, fontSize: 12 }}>
                {data.map((d) => <Cell key={d.kunci} fill={d.kunci === "sigap" ? palet.seri1 : palet.abu} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </KartuGrafik>

      {info && (
        <section className="kartu">
          <div className="kartu-kepala"><h2>Batas klaim yang wajib disebut</h2></div>
          <ol style={{ margin: 0, paddingLeft: 20 }}>{info.batas_klaim.map((b, i) => <li key={i} style={{ marginBottom: 4 }}>{b}</li>)}</ol>
        </section>
      )}
      {hasil && hasil.ringkasan && hasil.ringkasan.metrik_deteksi && (
        <section className="kartu">
          <div className="kartu-kepala"><h2>Metrik deteksi gangguan (leave-one-episode-out)</h2></div>
          <TabelData baris={Object.entries(hasil.ringkasan.metrik_deteksi).map(([k, m]) => ({ metode: k, ...m }))}
            kolom={[{ kunci: "metode", judul: "Metode" }, { kunci: "POD", judul: "POD", angka: true, format: (v) => v.toFixed(2) },
              { kunci: "FAR", judul: "FAR", angka: true, format: (v) => v.toFixed(2) }, { kunci: "CSI", judul: "CSI", angka: true, format: (v) => v.toFixed(2) },
              { kunci: "lead_time_jam", judul: "Lead time (jam)", angka: true, format: (v) => v.toFixed(1) }]} />
        </section>
      )}
    </>
  );
}
