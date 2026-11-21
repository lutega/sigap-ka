// Panel kendali mode demo (spesifikasi 16) di tab Operasi: mulai sesi demo untuk episode terpilih,
// langkah ke jam keputusan berikutnya, putar/jeda otomatis dengan kecepatan pilihan, reset (admin),
// dan keluar. Keputusan selama demo dicatat dengan tanda mode=demo.
// Lapis: A (antarmuka) -> /demo.
import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

export default function PanelDemo({ episodeId, pengguna, demo, setDemo, setJam, onGalat }) {
  const [sibuk, setSibuk] = useState(false);
  const [kecepatan, setKecepatan] = useState(2);
  const pewaktu = useRef(null);

  function terapkan(r) {
    setDemo(r.sesi);
    setJam(r.sesi.jam_sebelum_t0);
  }

  async function panggil(fn) {
    setSibuk(true);
    try { terapkan(await fn()); } catch (e) { onGalat(e); } finally { setSibuk(false); }
  }

  // putar otomatis: satu langkah (6 jam episode) tiap kecepatan x interval detik selama status
  // server "berjalan"; status "jeda" dari server menghentikan pewaktu
  useEffect(() => {
    if (!demo || demo.status !== "berjalan") return undefined;
    pewaktu.current = setTimeout(() => {
      api.post(`/demo/${demo.id}/langkah`).then(terapkan).catch(onGalat);
    }, demo.detik_per_langkah * 1000);
    return () => clearTimeout(pewaktu.current);
  }, [demo]); // eslint-disable-line

  if (!demo) {
    return (
      <div className="baris-filter">
        <label className="isian">Kecepatan demo
          <select value={kecepatan} onChange={(e) => setKecepatan(Number(e.target.value))}>
            {[0.5, 1, 2].map((k) => <option key={k} value={k}>1 jam episode = {k} detik</option>)}
          </select>
        </label>
        <button className="tombol utama" disabled={!episodeId || sibuk}
          onClick={() => panggil(() => api.post("/demo/mulai", { episode_id: episodeId, kecepatan_detik_per_jam: kecepatan }))}>
          Mulai mode demo
        </button>
      </div>
    );
  }

  const selesai = demo.status === "selesai";
  return (
    <div className="baris-filter" data-testid="panel-demo">
      <span className="lencana" title="Log keputusan ditandai mode=demo">mode demo · {demo.status}</span>
      <strong className="angka">T-{demo.jam_sebelum_t0}</strong>
      <button className="tombol" disabled={sibuk || selesai} onClick={() => panggil(() => api.post(`/demo/${demo.id}/langkah`))}>
        Lompat ke jam berikutnya
      </button>
      <button className="tombol" disabled={sibuk || selesai}
        onClick={() => panggil(() => api.post(`/demo/${demo.id}/jeda`))}>
        {demo.status === "berjalan" ? "Jeda" : "Lanjutkan"}
      </button>
      <span className="muted angka" style={{ fontSize: 12 }}>{demo.detik_per_langkah} detik / 6 jam</span>
      {pengguna.level === "admin" && (
        <button className="tombol hapus" disabled={sibuk} onClick={() => panggil(() => api.post(`/demo/${demo.id}/reset`))}>
          Reset demo
        </button>
      )}
      <button className="tombol" onClick={() => { setDemo(null); setJam(72); }}>Keluar demo</button>
    </div>
  );
}
