// Tab Data: status sumber (nyata/dummy, waktu ambil terakhir), hujan harian NASA POWER lokal dan
// hulu, muka air Glapan (sintetis + titik nyata, garis Awas), katalog kejadian, jadwal KA.
// Lapis: A (antarmuka) untuk lapis S.
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { KartuGrafik, LabelData, Pesan, TabelData } from "../komponen/umum.jsx";
import { useTema } from "../tema.js";

const tgl = (w) => (w ? String(w).slice(0, 10) : "–");
const tglJam = (w) => (w ? String(w).slice(0, 16).replace("T", " ") : "–");

export default function TabData() {
  const { palet } = useTema();
  const [sumber, setSumber] = useState([]);
  const [dari, setDari] = useState("2025-01-10");
  const [sampai, setSampai] = useState("2025-01-31");
  const [sumberHujan, setSumberHujan] = useState("gpm_imerg_late");
  const [hujan, setHujan] = useState([]);
  const [mukaAir, setMukaAir] = useState(null);
  const [kejadian, setKejadian] = useState([]);
  const [jadwal, setJadwal] = useState([]);
  const [galat, setGalat] = useState(null);

  useEffect(() => {
    Promise.all([api.get("/data/sumber"), api.get("/data/kejadian"), api.get("/data/jadwal"),
      api.get("/data/muka-air?titik=glapan&episode_id=NYATA-20250124")])
      .then(([s, k, j, m]) => { setSumber(s); setKejadian(k); setJadwal(j); setMukaAir(m); })
      .catch(setGalat);
  }, []);

  useEffect(() => {
    api.get(`/data/hujan?dari=${dari}&sampai=${sampai}T23:59:59&sumber=${sumberHujan}`).then(setHujan).catch(setGalat);
  }, [dari, sampai, sumberHujan]);

  const dataHujan = useMemo(() => {
    const per = {};
    hujan.forEach((h) => {
      const k = tgl(h.waktu);
      per[k] = per[k] || { tanggal: k };
      per[k][h.lokasi] = h.nilai;
    });
    return Object.values(per).sort((a, b) => a.tanggal.localeCompare(b.tanggal));
  }, [hujan]);

  const dataAir = useMemo(() => {
    if (!mukaAir) return [];
    return mukaAir.seri.filter((s) => s.lokasi === "glapan").map((s) => ({
      waktu: tglJam(s.waktu), sintetis: s.is_simulated ? s.nilai : null, nyata: s.is_simulated ? null : s.nilai,
    })).sort((a, b) => a.waktu.localeCompare(b.waktu)).filter((_, i, arr) => i % 3 === 0 || arr[i].nyata !== null);
  }, [mukaAir]);

  return (
    <>
      <Pesan galat={galat} />
      <section className="kartu">
        <div className="kartu-kepala"><h2>Sumber data</h2><span className="spasi" />
          <span className="muted" style={{ fontSize: 12 }}>Data inti dari sumber terbuka; data bersurat bersifat opsional.</span></div>
        <TabelData baris={sumber} kolom={[
          { kunci: "nama", judul: "Sumber" }, { kunci: "jenis", judul: "Jenis" }, { kunci: "kelompok", judul: "Kelompok" },
          { kunci: "label", judul: "Label", format: (v) => <LabelData label={v} /> },
          { kunci: "siap", judul: "Siap", format: (v) => (v ? "siap" : "belum") }, { kunci: "alasan", judul: "Keterangan" },
          { kunci: "status_terakhir", judul: "Status terakhir" },
          { kunci: "waktu_ambil_terakhir", judul: "Ambil terakhir", format: tglJam },
        ]} />
      </section>

      <section className="kartu baris-filter">
        <label className="isian">Dari <input type="text" value={dari} onChange={(e) => setDari(e.target.value)} placeholder="YYYY-MM-DD" /></label>
        <label className="isian">Sampai <input type="text" value={sampai} onChange={(e) => setSampai(e.target.value)} placeholder="YYYY-MM-DD" /></label>
        <label className="isian">Sumber hujan
          <select value={sumberHujan} onChange={(e) => setSumberHujan(e.target.value)}>
            <option value="gpm_imerg_late">GPM IMERG Late (0,1°, tersedia saat keputusan)</option>
            <option value="gpm_imerg_final">GPM IMERG Final (0,1°, analisis riwayat)</option>
            <option value="nasa_power">NASA POWER (grid kasar)</option>
          </select>
        </label>
        <span className="muted" style={{ fontSize: 12 }}>Rentang dan sumber berlaku untuk grafik hujan.</span>
      </section>

      <div className="grid-2">
        <KartuGrafik judul="Hujan harian (mm)" label="nyata"
          ket={sumberHujan === "nasa_power"
            ? "NASA POWER: titik lokal dan hulu jatuh di sel grid yang sama sehingga nilainya identik (A-017)."
            : "GPM IMERG 0,1°: hujan hulu Tuntang terpisah dari hujan lokal. Hari IMERG dihitung dalam UTC (mulai 07.00 WIB)."}
          kolom={[{ kunci: "tanggal", judul: "Tanggal" }, { kunci: "lokal", judul: "Lokal (mm)", angka: true },
            { kunci: "hulu", judul: "Hulu (mm)", angka: true }, { kunci: "gundih", judul: "Gundih (mm)", angka: true }]}
          baris={dataHujan}>
          <div className="wadah-grafik" role="img" aria-label="Hujan harian lokal dan hulu">
            <ResponsiveContainer>
              <BarChart data={dataHujan} margin={{ top: 8, right: 16, bottom: 8, left: 0 }} barGap={2}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="tanggal" tickFormatter={(v) => v.slice(5)} tickLine={false} axisLine={{ stroke: palet.sumbu }} minTickGap={16} />
                <YAxis tickLine={false} axisLine={false} width={40} />
                <Tooltip formatter={(v, n) => [`${Number(v).toFixed(1)} mm`, n]} contentStyle={{ color: palet.teks }} />
                <Legend verticalAlign="top" height={28} />
                <Bar dataKey="lokal" name="Lokal Gubug–Karangjati" fill={palet.seri1} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                <Bar dataKey="hulu" name="Hulu Tuntang" fill={palet.seri2} radius={[4, 4, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </KartuGrafik>

        <KartuGrafik judul="Muka air Bendung Glapan, Januari 2025" label="campuran"
          ket={mukaAir ? mukaAir.catatan : ""}
          kolom={[{ kunci: "waktu", judul: "Waktu" }, { kunci: "sintetis", judul: "Sintetis", angka: true },
            { kunci: "nyata", judul: "Nyata (BNPB)", angka: true }]}
          baris={dataAir}>
          <div className="wadah-grafik" role="img" aria-label="Muka air Glapan sintetis dan titik nyata">
            <ResponsiveContainer>
              <ComposedChart data={dataAir} margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="waktu" tickFormatter={(v) => v.slice(5, 10)} tickLine={false} axisLine={{ stroke: palet.sumbu }} minTickGap={24} />
                <YAxis domain={["dataMin - 30", "dataMax + 30"]} tickLine={false} axisLine={false} width={48} />
                <Tooltip contentStyle={{ color: palet.teks }} />
                <Legend verticalAlign="top" height={28} />
                {mukaAir && <ReferenceLine y={mukaAir.ambang_awas} stroke={palet.redup}
                  label={{ value: `Awas ${mukaAir.ambang_awas}`, position: "insideTopLeft", fill: palet.teks2, fontSize: 11 }} />}
                <Line dataKey="sintetis" name="Model sintetis (dummy)" stroke={palet.seri1} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
                <Scatter dataKey="nyata" name="Titik nyata rilis BNPB" fill={palet.seri2} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </KartuGrafik>
      </div>

      <div className="grid-2">
        <section className="kartu">
          <div className="kartu-kepala"><h2>Katalog kejadian gangguan</h2></div>
          <p className="sekunder" style={{ fontSize: 12 }}>Kolom yang belum diketahui dibiarkan kosong (tidak ditebak). Prioritas pengisian: jam tutup, jam buka, mekanisme E1, E4, E5, E6.</p>
          <TabelData baris={kejadian} kolom={[{ kunci: "id", judul: "Id" }, { kunci: "tanggal", judul: "Tanggal", format: tgl },
            { kunci: "jam_tutup", judul: "Tutup", format: tglJam }, { kunci: "jam_buka", judul: "Buka", format: tglJam },
            { kunci: "mekanisme", judul: "Mekanisme" }, { kunci: "status_konfirmasi", judul: "Status" }, { kunci: "catatan", judul: "Catatan" }]} />
        </section>
        <section className="kartu">
          <div className="kartu-kepala"><h2>Jadwal KA lewat Gubug</h2>{jadwal.some((j) => j.is_simulated) && <LabelData label="dummy" />}</div>
          <TabelData baris={jadwal} kolom={[{ kunci: "nomor", judul: "Nomor" }, { kunci: "relasi", judul: "Relasi" },
            { kunci: "jam_lewat_gubug", judul: "Jam lewat" }, { kunci: "sumber", judul: "Sumber" }]} />
        </section>
      </div>
    </>
  );
}
