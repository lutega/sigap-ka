// Evaluasi pada data nyata (kandidat): validasi IMERG vs BMKG, kejadian kandidat dari berita dengan
// hasil uji balik, kemampuan membedakan hari (AUC + selang 95%), kepekaan bias, realisme generator.
// Lapis: A (antarmuka) untuk evaluasi lapis S-I-G. Data dari GET /data/evaluasi-nyata.
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ErrorBar, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { KartuGrafik, Pesan, Stat, TabelData } from "./umum.jsx";
import { useTema } from "../tema.js";

const angka = (x, d = 2) => (x === null || x === undefined ? "–"
  : Number(x).toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d }));
const bias = (x) => (x === null || x === undefined ? "–" : `${x > 0 ? "+" : ""}${angka(x, 1)}%`);
const tglJam = (w) => (w ? String(w).slice(0, 16).replace("T", " ") : "–");

const LABEL_SKOR = {
  "p_T-0": "Peluang T-0", "p_T-24": "Peluang T-24", hujan_hulu_3h_tersedia: "Hujan hulu tersedia",
  hujan_aktual_hulu_72j: "Hujan hulu aktual*", hujan_aktual_lokal_72j: "Hujan lokal aktual*",
};
const LABEL_BESARAN = {
  hulu_72j: "Hujan hulu 72 jam (mm)", lokal_72j: "Hujan lokal 72 jam (mm)",
  hulu_3h_tersedia: "Hujan hulu 3 hari tersedia (mm)", lokal_3h_tersedia: "Hujan lokal 3 hari tersedia (mm)",
  glapan_relatif_T0: "Glapan relatif Awas pada T-0 (cm)",
};

function TooltipAuc({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const s = payload[0].payload;
  return (
    <div className="tooltip-sigap">
      <strong>{s.nama}</strong>
      <div>AUC {angka(s.auc)} (selang 95% {angka(s.bawah)}–{angka(s.atas)})</div>
    </div>
  );
}

export default function EvaluasiNyata() {
  const { palet } = useTema();
  const [d, setD] = useState(null);
  const [galat, setGalat] = useState(null);
  const [sumber, setSumber] = useState("harian");

  useEffect(() => {
    api.get("/data/evaluasi-nyata").then((r) => {
      if (r && !Array.isArray(r)) { setD(r); if (r.sumber_utama) setSumber(r.sumber_utama); }
    }).catch(setGalat);
  }, []);

  const pem = d?.pemisahan?.[sumber];
  const dataAuc = useMemo(() => (pem?.skor || []).filter((s) => s.auc !== null).map((s) => ({
    ...s, label: LABEL_SKOR[s.skor] || s.skor,
    galat: [Math.max(0, s.auc - (s.bawah ?? s.auc)), Math.max(0, (s.atas ?? s.auc) - s.auc)],
  })), [pem]);
  const kandidat = useMemo(() => (d?.kandidat || []).map((k) => ({ ...k, ...(k[sumber] || {}) })), [d, sumber]);

  if (galat) return <Pesan galat={galat} />;
  if (!d) return null;
  const v = d.validasi_imerg || {};
  const late = v.gpm_imerg_late || {};
  const pembanding = pem?.pembanding?.waktu_nyata?.find((s) => s.skor === "p_T-0");
  const pT0 = pem?.skor?.find((s) => s.skor === "p_T-0");

  return (
    <>
      <section className="kartu">
        <div className="kartu-kepala">
          <h2>Evaluasi pada data nyata</h2>
          <span className="lencana dummy" title="Kejadian dari berita publik, belum diverifikasi tim">kandidat</span>
          <span className="spasi" />
          <label className="isian">Sumber hujan
            <select value={sumber} onChange={(e) => setSumber(e.target.value)}>
              {Object.entries(d.sumber || {}).map(([k, s]) => <option key={k} value={k}>{s.nama}</option>)}
            </select>
          </label>
        </div>
        <ul className="sekunder" style={{ fontSize: 12, marginTop: 0 }}>
          {d.batas_klaim.map((b) => <li key={b}>{b}</li>)}
        </ul>
        <div className="baris-stat">
          <Stat label="Kejadian kandidat" nilai={d.kandidat.length} ket={pem ? `${pem.n_kejadian} hari kejadian vs ${pem.n_lain} hari lain` : ""} />
          <Stat label="AUC peluang T-0" nilai={pT0 ? angka(pT0.auc) : "–"}
            ket={pT0 ? `selang 95% ${angka(pT0.bawah)}–${angka(pT0.atas)}; acak = 0,50` : ""} />
          <Stat label="IMERG Late vs BMKG Semarang" nilai={bias(late.bias_persen)}
            ket={late.n_bulan ? `korelasi bulanan ${angka(late.korelasi)}, ${late.n_bulan} bulan` : "validasi belum dijalankan"} />
          <Stat label="Selisih antarstasiun BMKG" nilai={bias(v.antarstasiun?.bias_persen)}
            ket={v.antarstasiun ? `korelasi ${angka(v.antarstasiun.korelasi)} (acuan galat ukur)` : ""} />
        </div>
      </section>

      <div className="grid-2">
        <KartuGrafik judul="Membedakan hari kejadian dari hari lain (AUC)" label="campuran"
          ket={`Pemindaian harian T-0 pukul 12.00, prakiraan ${d.prakiraan_utama || "persistensi"}, muka air sintetis tertunda sesuai latensi hujan. *Hujan aktual belum tersedia pada jam keputusan (pembanding batas atas).${pembanding ? ` Bila muka air sintetis dianggap waktu nyata: AUC T-0 ${angka(pembanding.auc)}.` : ""}`}
          kolom={[{ kunci: "nama", judul: "Skor" }, { kunci: "auc", judul: "AUC", angka: true, format: (x) => angka(x) },
            { kunci: "bawah", judul: "Bawah 95%", angka: true, format: (x) => angka(x) },
            { kunci: "atas", judul: "Atas 95%", angka: true, format: (x) => angka(x) }]}
          baris={dataAuc}>
          <div className="wadah-grafik" role="img" aria-label="AUC tiap skor dengan selang kepercayaan 95 persen">
            <ResponsiveContainer>
              <BarChart data={dataAuc} layout="vertical" margin={{ top: 8, right: 24, bottom: 8, left: 8 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tickFormatter={(x) => angka(x)}
                  tickLine={false} axisLine={{ stroke: palet.sumbu }} />
                <YAxis type="category" dataKey="label" width={136} tickLine={false} axisLine={false} />
                <Tooltip content={<TooltipAuc />} cursor={{ fill: palet.grid }} />
                <ReferenceLine x={0.5} stroke={palet.redup} strokeDasharray="4 4"
                  label={{ value: "acak 0,50", position: "insideTopRight", fill: palet.teks2, fontSize: 11 }} />
                <Bar dataKey="auc" name="AUC" fill={palet.seri1} radius={[0, 4, 4, 0]} barSize={16} isAnimationActive={false}>
                  <ErrorBar dataKey="galat" width={6} strokeWidth={1.5} stroke={palet.teks2} direction="x" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </KartuGrafik>

        <section className="kartu">
          <div className="kartu-kepala"><h2>Realisme generator dummy</h2><span className="lencana dummy">dummy vs nyata</span></div>
          <p className="sekunder" style={{ fontSize: 12 }}>Median episode latih lapis I (sintetis) dibanding semua hari IMERG Late dan hari kejadian kandidat. Episode latih jauh lebih basah, sehingga skala peluang model rendah pada data nyata (A-061).</p>
          <TabelData baris={d.realisme?.median || []} kolom={[
            { kunci: "besaran", judul: "Median", format: (x) => LABEL_BESARAN[x] || x },
            { kunci: "sintetis_latih", judul: "Latih sintetis", angka: true, format: (x) => angka(x, 0) },
            { kunci: "nyata_semua_hari", judul: "Semua hari", angka: true, format: (x) => angka(x, 0) },
            { kunci: "nyata_hari_kejadian", judul: "Hari kejadian", angka: true, format: (x) => angka(x, 0) }]} />
          <TabelData baris={d.realisme?.kelas_hujan || []} kolom={[
            { kunci: "hujan_hulu_72j", judul: "Hujan hulu 72 jam" },
            { kunci: "porsi_terganggu_sintetis", judul: "Terganggu (sintetis)", angka: true, format: (x) => (x === null || x === undefined ? "–" : `${angka(100 * x, 0)}%`) },
            { kunci: "n_hari_nyata", judul: "Hari nyata", angka: true },
            { kunci: "hari_kejadian", judul: "Hari kejadian", angka: true }]} />
        </section>
      </div>

      <section className="kartu">
        <div className="kartu-kepala"><h2>Kejadian kandidat dan hasil uji balik</h2><span className="lencana dummy">kandidat</span></div>
        <p className="sekunder" style={{ fontSize: 12 }}>T-0 = jam tutup/awal gangguan menurut berita; tanpa jam = 00.00 (A-055). Hujan tersedia = yang sudah bisa dilihat model pada T-0 (IMERG Late, latensi 14 jam). Tautan berita lengkap ada di data/manual/kejadian_kandidat.csv.</p>
        <TabelData baris={kandidat} kolom={[
          { kunci: "id_kandidat", judul: "Id" }, { kunci: "t0", judul: "T-0", format: tglJam },
          { kunci: "lokasi_km", judul: "KM" }, { kunci: "jenis_gangguan", judul: "Gangguan", format: (x) => String(x || "").replaceAll("_", " ") },
          { kunci: "mekanisme", judul: "Mekanisme" },
          { kunci: "hujan_aktual_hulu_72j", judul: "Hulu 72 j aktual", angka: true, format: (x) => angka(x, 0) },
          { kunci: "hujan_hulu_3h_tersedia", judul: "Hulu tersedia", angka: true, format: (x) => angka(x, 0) },
          { kunci: "p_T-24", judul: "p T‑24", angka: true, format: (x) => angka(x) },
          { kunci: "p_T-0", judul: "p T‑0", angka: true, format: (x) => angka(x) },
          { kunci: "tindakan_sigap", judul: "Rencana SIGAP", format: (x) => x || "–" },
          { kunci: "sumber", judul: "Sumber", format: (x) => (x || []).join(", ") }]} />
      </section>
    </>
  );
}
