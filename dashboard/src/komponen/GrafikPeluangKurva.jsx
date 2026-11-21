// Grafik peluang gangguan vs kurva pemicu satu tindakan (tab Operasi dan Kurva).
// Lapis: A (antarmuka) untuk keluaran lapis I dan G. Satu sumbu (peluang 0-100%), dua seri
// (slot 1 = peluang, slot 2 = kurva), legenda + label langsung di ujung, garis batas waktu siap.
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { persen, useTema } from "../tema.js";

export function labelJam(j) {
  return `T-${j}`;
}

export default function GrafikPeluangKurva({ data, waktuSiap, jamSekarang, namaKurva = "Kurva pemicu", namaPeluang = "Peluang gangguan", seriKedua }) {
  const { palet } = useTema();
  return (
    <div className="wadah-grafik" role="img" aria-label={`${namaPeluang} dibanding ${namaKurva}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 16, right: 32, bottom: 8, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: palet.sumbu }} interval={1} />
          <YAxis domain={[0, 1]} tickFormatter={(v) => persen(v)} tickLine={false} axisLine={false} width={44} />
          <Tooltip formatter={(v, n) => [persen(v, 1), n]} contentStyle={{ color: palet.teks }} />
          <Legend verticalAlign="top" height={28} iconType="plainline" />
          {waktuSiap !== undefined && (
            <ReferenceLine x={labelJam(waktuSiap)} stroke={palet.redup} label={{ value: "batas waktu siap", position: "insideTopRight", fill: palet.teks2, fontSize: 11 }} />
          )}
          {jamSekarang !== undefined && (
            <ReferenceLine x={labelJam(jamSekarang)} stroke={palet.teks2} strokeWidth={1} label={{ value: "sekarang", position: "insideTopLeft", fill: palet.teks2, fontSize: 11 }} />
          )}
          <Line type="stepAfter" dataKey="kurva" name={namaKurva} stroke={palet.seri2} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
          {seriKedua && (
            <Line type="stepAfter" dataKey="kurva2" name={seriKedua} stroke={palet.seri3} strokeWidth={2} dot={false} isAnimationActive={false} />
          )}
          <Line type="linear" dataKey="peluang" name={namaPeluang} stroke={palet.seri1} strokeWidth={2}
            dot={{ r: 4, strokeWidth: 2, stroke: palet.permukaan, fill: palet.seri1 }} activeDot={{ r: 6 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
