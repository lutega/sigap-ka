// Tab Operasi: putar ulang episode jam demi jam, grafik peluang vs kurva pemicu tindakan terpilih,
// papan 9 tindakan dengan Setujui/Tolak, dan ringkasan biaya di T-0 (spesifikasi 4.6, 12).
// Lapis: A (antarmuka). Data hanya sampai jam yang sedang diputar (tanpa intip masa depan).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";
import GrafikPeluangKurva, { labelJam } from "../komponen/GrafikPeluangKurva.jsx";
import PapanTindakan from "../komponen/PapanTindakan.jsx";
import { KartuGrafik, LabelData, Pesan, Stat, TabelData } from "../komponen/umum.jsx";
import { persen, rupiahJuta } from "../tema.js";
import PanelDemo from "./PanelDemo.jsx";

export function RingkasanT0({ ringkasan }) {
  if (!ringkasan) return null;
  return (
    <section className="kartu" data-testid="ringkasan-t0">
      <div className="kartu-kepala"><h2>Ringkasan T-0: keputusan operator vs saran SIGAP</h2>
        <span className="lencana dummy">biaya parameter dummy</span></div>
      {ringkasan.status_hasil === "belum terkonfirmasi" && (
        <p className="sekunder">Hasil episode belum terkonfirmasi di katalog kejadian, jadi biaya ditampilkan untuk dua kemungkinan.</p>
      )}
      {ringkasan.skenario.map((s, i) => (
        <div key={i} style={{ marginBottom: 16 }}>
          <h3 style={{ marginBottom: 8 }}>{s.terganggu ? "Bila jalur terganggu" : "Bila jalur tidak terganggu"}
            {ringkasan.status_hasil === "diketahui" && " (hasil episode)"}</h3>
          <div className="grid-3" style={{ marginBottom: 8 }}>
            <Stat label="Total biaya operator" nilai={rupiahJuta(s.total_operator)} />
            <Stat label="Total biaya bila saran SIGAP diikuti" nilai={rupiahJuta(s.total_sigap)} />
            <Stat label="Selisih (operator - SIGAP)" nilai={rupiahJuta(s.selisih_operator_minus_sigap)} />
          </div>
          <TabelData baris={s.tindakan.map((t) => ({ ...t, op_jam: t.operator.jam_sebelum_t0, op_biaya: t.operator.biaya,
            op_label: t.operator.label, sg_jam: t.sigap.jam_sebelum_t0, sg_biaya: t.sigap.biaya, sg_label: t.sigap.label }))}
            kolom={[
              { kunci: "tindakan", judul: "Tindakan" }, { kunci: "nama", judul: "Nama" },
              { kunci: "op_jam", judul: "Operator bertindak", format: (v) => (v === null ? "tidak" : labelJam(v)) },
              { kunci: "op_biaya", judul: "Biaya operator", angka: true, format: rupiahJuta },
              { kunci: "op_label", judul: "Penilaian operator" },
              { kunci: "sg_jam", judul: "SIGAP bertindak", format: (v) => (v === null ? "tidak" : labelJam(v)) },
              { kunci: "sg_biaya", judul: "Biaya SIGAP", angka: true, format: rupiahJuta },
            ]} />
        </div>
      ))}
      {ringkasan.catatan.map((c, i) => <p key={i} className="muted" style={{ fontSize: 12 }}>{c}</p>)}
    </section>
  );
}

export default function TabOperasi({ episode, pengguna }) {
  const [epId, setEpId] = useState("");
  const [jam, setJam] = useState(72);
  const [papan, setPapan] = useState(null);
  const [lintasan, setLintasan] = useState([]);
  const [kurva, setKurva] = useState(null);
  const [dipilih, setDipilih] = useState("T1");
  const [ringkasan, setRingkasan] = useState(null);
  const [galat, setGalat] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [putar, setPutar] = useState(false);
  const [detikPerLangkah, setDetikPerLangkah] = useState(4);
  const [demo, setDemo] = useState(null); // sesi demo aktif (tahap 9)
  const pewaktu = useRef(null);

  useEffect(() => { if (!epId && episode.length) setEpId(episode[0].id); }, [episode, epId]);
  const ep = episode.find((e) => e.id === epId);
  const daftarJam = ep ? ep.jam_keputusan : [];
  const sesiQ = demo ? `&sesi_demo_id=${demo.id}` : "";

  const muat = useCallback(async () => {
    if (!epId) return;
    setGalat(null);
    try {
      const [p, l] = await Promise.all([
        api.get(`/episode/${epId}/papan?jam=${jam}${sesiQ}`),
        api.get(`/episode/${epId}/lintasan?sampai_jam=${jam}`),
      ]);
      setPapan(p);
      setLintasan(l);
      setRingkasan(jam === 0 ? await api.get(`/episode/${epId}/ringkasan?${sesiQ.slice(1)}`) : null);
    } catch (e) { setGalat(e); }
  }, [epId, jam, sesiQ]);

  useEffect(() => { muat(); }, [muat]);

  useEffect(() => {
    if (!papan) return;
    const f = papan.inferensi.lama_tutup.faktor_L;
    api.get(`/kurva/${dipilih}?faktor_L=${f.toFixed(4)}`).then(setKurva).catch(setGalat);
  }, [dipilih, papan]);

  // putar ulang otomatis (mode normal); mode demo mengatur langkahnya sendiri lewat PanelDemo
  useEffect(() => {
    if (!putar || demo) return undefined;
    pewaktu.current = setTimeout(() => {
      const i = daftarJam.indexOf(jam);
      if (i >= 0 && i < daftarJam.length - 1) setJam(daftarJam[i + 1]); else setPutar(false);
    }, detikPerLangkah * 1000);
    return () => clearTimeout(pewaktu.current);
  }, [putar, jam, daftarJam, detikPerLangkah, demo]);

  async function keputusan(tindakan, jenis, alasan) {
    setSibuk(true);
    try {
      await api.post(`/episode/${epId}/keputusan`, { tindakan, jam_sebelum_t0: jam, keputusan: jenis, alasan: alasan || null,
        sesi_demo_id: demo ? demo.id : null });
      await muat();
    } catch (e) { setGalat(e); } finally { setSibuk(false); }
  }

  const dataGrafik = useMemo(() => daftarJam.map((j) => {
    const l = lintasan.find((x) => x.jam_sebelum_t0 === j);
    const k = kurva ? kurva.ambang[kurva.jam_sebelum_t0.indexOf(j)] : undefined;
    return { label: labelJam(j), jam: j, peluang: l ? l.peluang : null, kurva: k === undefined ? null : k };
  }), [daftarJam, lintasan, kurva]);

  const inf = papan && papan.inferensi;
  const langkah = (arah) => {
    const i = daftarJam.indexOf(jam) + arah;
    if (i >= 0 && i < daftarJam.length) setJam(daftarJam[i]);
  };

  return (
    <>
      <section className="kartu">
        <div className="baris-filter">
          <label className="isian">Episode
            <select value={epId} onChange={(e) => { setEpId(e.target.value); setJam(72); setPutar(false); setDemo(null); }}>
              {episode.map((e) => <option key={e.id} value={e.id}>{e.nama} ({e.jenis})</option>)}
            </select>
          </label>
          {ep && <LabelData label={ep.jenis === "nyata" ? "campuran" : "dummy"} />}
          {!demo && (
            <>
              <button className="tombol" onClick={() => langkah(-1)} disabled={jam === daftarJam[0]} aria-label="jam keputusan sebelumnya">◀</button>
              <strong className="angka" style={{ minWidth: 60, textAlign: "center" }}>{labelJam(jam)}</strong>
              <button className="tombol" onClick={() => langkah(1)} disabled={jam === 0} aria-label="jam keputusan berikutnya">▶</button>
              <button className="tombol" onClick={() => setPutar(!putar)} disabled={jam === 0}>{putar ? "Jeda" : "Putar"}</button>
              <label className="isian">Kecepatan
                <select value={detikPerLangkah} onChange={(e) => setDetikPerLangkah(Number(e.target.value))}>
                  {[2, 4, 8].map((d) => <option key={d} value={d}>{d} detik / 6 jam episode</option>)}
                </select>
              </label>
              <button className="tombol" onClick={() => { setJam(72); setPutar(false); }}>Ulang ke T-72</button>
            </>
          )}
          <span style={{ flex: 1 }} />
          <PanelDemo episodeId={epId} pengguna={pengguna} demo={demo} setDemo={setDemo} setJam={setJam} onGalat={setGalat} />
        </div>
        {ep && <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>{ep.keterangan}</p>}
        <Pesan galat={galat} />
      </section>

      {inf && (
        <section className="kartu grid-3">
          <Stat label={`Peluang gangguan pada ${labelJam(jam)}`} nilai={persen(inf.peluang)} ket={`genangan ${persen(inf.peluang_genangan)} · gerusan ${persen(inf.peluang_gerusan)}`} />
          <Stat label="Mekanisme dominan" nilai={inf.mekanisme_dominan} ket={`porsi genangan ${persen(inf.porsi_genangan)}`} />
          <Stat label="Perkiraan lama tutup bila terganggu" nilai={`${Math.round(inf.lama_tutup.harapan_jam)} jam`}
            ket={`pendek ${persen(inf.lama_tutup.sebaran.pendek)} · sedang ${persen(inf.lama_tutup.sebaran.sedang)} · panjang ${persen(inf.lama_tutup.sebaran.panjang)}`} />
        </section>
      )}

      <div className="grid-2">
        <KartuGrafik judul={`Peluang gangguan vs kurva pemicu ${dipilih}`} label="dummy"
          ket={kurva ? `${kurva.nama}: ambang di batas waktu (C+P)/(L+P) = ${persen(kurva.ambang_statis, 1)}. Pilih tindakan lain dari papan.` : ""}
          kolom={[{ kunci: "label", judul: "Jam" }, { kunci: "peluang", judul: "Peluang", angka: true, format: (v) => persen(v, 1) },
            { kunci: "kurva", judul: "Kurva pemicu", angka: true, format: (v) => persen(v, 1) }]}
          baris={dataGrafik}>
          <GrafikPeluangKurva data={dataGrafik} waktuSiap={kurva ? kurva.waktu_siap_jam : undefined} jamSekarang={jam}
            namaKurva={`Kurva pemicu ${dipilih}`} />
        </KartuGrafik>
        <section className="kartu">
          <div className="kartu-kepala"><h2>Bukti utama</h2></div>
          {inf ? <TabelData baris={inf.bukti} kolom={[
            { kunci: "keterangan", judul: "Bukti" }, { kunci: "nilai", judul: "Nilai", angka: true },
            { kunci: "satuan", judul: "Satuan" }, { kunci: "arah", judul: "Pengaruh" }]} /> : <p className="muted">Memuat…</p>}
          {inf && inf.catatan.map((c, i) => <p key={i} className="catatan-kewenangan">{c}</p>)}
        </section>
      </div>

      <section className="kartu">
        <div className="kartu-kepala"><h2>Papan tindakan {labelJam(jam)}</h2>
          {papan && Object.entries(papan.ringkas_status).map(([s, n]) => <span key={s} className="lencana">{s}: {n}</span>)}
        </div>
        <PapanTindakan papan={papan} onKeputusan={keputusan} sibuk={sibuk} dipilih={dipilih} onPilih={setDipilih} />
      </section>

      <RingkasanT0 ringkasan={ringkasan} />
    </>
  );
}
