// Aplikasi konsol SIGAP-KA: halaman login, lalu lima tab (Operasi, Data, Prediksi, Kurva pemicu,
// Simulasi) dan menu Kelola pengguna khusus admin (spesifikasi 4.6 dan 15).
// Lapis: A (antarmuka). Hanya berkomunikasi lewat REST API.
import { useEffect, useState } from "react";
import { ambilToken, api, simpanToken } from "./api.js";
import Login from "./komponen/Login.jsx";
import { KonteksTema, useTemaPenyedia } from "./tema.js";
import KelolaPengguna from "./tab/KelolaPengguna.jsx";
import TabData from "./tab/TabData.jsx";
import TabKurva from "./tab/TabKurva.jsx";
import TabOperasi from "./tab/TabOperasi.jsx";
import TabPrediksi from "./tab/TabPrediksi.jsx";
import TabSimulasi from "./tab/TabSimulasi.jsx";

export const TAB = [
  { kunci: "operasi", judul: "Operasi" },
  { kunci: "data", judul: "Data" },
  { kunci: "prediksi", judul: "Prediksi" },
  { kunci: "kurva", judul: "Kurva pemicu" },
  { kunci: "simulasi", judul: "Simulasi" },
];

export default function App() {
  const tema = useTemaPenyedia();
  const [pengguna, setPengguna] = useState(null);
  const [siap, setSiap] = useState(false);
  const [tab, setTab] = useState("operasi");
  const [episode, setEpisode] = useState([]);
  const [info, setInfo] = useState(null);

  useEffect(() => {
    if (!ambilToken()) { setSiap(true); return; }
    api.get("/auth/saya").then((p) => setPengguna(p)).catch(() => simpanToken(null)).finally(() => setSiap(true));
  }, []);

  useEffect(() => {
    const keluar = () => setPengguna(null);
    window.addEventListener("sigap-keluar", keluar);
    return () => window.removeEventListener("sigap-keluar", keluar);
  }, []);

  useEffect(() => {
    if (!pengguna) return;
    api.get("/episode").then(setEpisode).catch(() => {});
    api.get("/info").then(setInfo).catch(() => {});
  }, [pengguna]);

  if (!siap) return null;
  return (
    <KonteksTema.Provider value={tema}>
      {!pengguna ? <Login onMasuk={setPengguna} /> : (
        <>
          <header className="kepala">
            <span className="judul">SIGAP-KA</span>
            <span className="sekunder">Koridor Brumbung–Karangjati</span>
            <span className="lencana dummy" title="Parameter C, L, P dan generator masih dummy">parameter dummy</span>
            <span className="spasi" />
            <span className="sekunder">{pengguna.username} ({pengguna.level})</span>
            <button className="tombol kecil" onClick={tema.ganti} aria-label="ganti tema terang/gelap">{tema.mode === "gelap" ? "Tema terang" : "Tema gelap"}</button>
            <button className="tombol kecil" onClick={() => { simpanToken(null); setPengguna(null); }}>Keluar</button>
          </header>
          <nav className="tab-bar" role="tablist">
            {TAB.map((t) => (
              <button key={t.kunci} role="tab" aria-selected={tab === t.kunci} onClick={() => setTab(t.kunci)}>{t.judul}</button>
            ))}
            {pengguna.level === "admin" && (
              <button role="tab" aria-selected={tab === "pengguna"} onClick={() => setTab("pengguna")}>Kelola pengguna</button>
            )}
          </nav>
          <main className="isi">
            {tab === "operasi" && <TabOperasi episode={episode} pengguna={pengguna} />}
            {tab === "data" && <TabData />}
            {tab === "prediksi" && <TabPrediksi episode={episode} />}
            {tab === "kurva" && <TabKurva />}
            {tab === "simulasi" && <TabSimulasi pengguna={pengguna} info={info} />}
            {tab === "pengguna" && pengguna.level === "admin" && <KelolaPengguna />}
            {info && (
              <footer className="kartu" style={{ fontSize: 12 }}>
                {info.catatan_kewenangan.map((c, i) => <p key={i} className="catatan-kewenangan">{c}</p>)}
                <details>
                  <summary className="sekunder">Batas klaim prototipe</summary>
                  <ol>{info.batas_klaim.map((b, i) => <li key={i}>{b}</li>)}</ol>
                </details>
              </footer>
            )}
          </main>
        </>
      )}
    </KonteksTema.Provider>
  );
}
