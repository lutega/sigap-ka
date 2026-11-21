// Tema konsol: palet referensi tervalidasi (validate_palette.js lulus untuk slot 1-3 di mode
// terang dan gelap). Recharts menerima warna sebagai nilai, jadi warna dibaca dari tabel ini
// sesuai mode aktif (pilihan pengguna atau pengaturan sistem).
import { createContext, useContext, useEffect, useState } from "react";

export const PALET = {
  terang: {
    seri1: "#2a78d6", seri2: "#eb6834", seri3: "#1baf7a", abu: "#c3c2b7",
    grid: "#e1e0d9", sumbu: "#c3c2b7", teks: "#0b0b0b", teks2: "#52514e", redup: "#898781", permukaan: "#fcfcfb",
  },
  gelap: {
    seri1: "#3987e5", seri2: "#d95926", seri3: "#199e70", abu: "#4a4a46",
    grid: "#2c2c2a", sumbu: "#383835", teks: "#f0efec", teks2: "#c3c2b7", redup: "#898781", permukaan: "#1a1a19",
  },
};

// Warna status: hanya untuk status, selalu bersama ikon dan label (tidak pernah warna saja).
export const STATUS = {
  "Putuskan sekarang": { warna: "#ec835a", ikon: "▲" },
  "Tunggu prakiraan berikutnya": { warna: "#898781", ikon: "◷" },
  "Terlambat": { warna: "#d03b3b", ikon: "✕" },
  "Sudah disetujui": { warna: "#0ca30c", ikon: "✓" },
};

const KUNCI = "sigap_tema";
export const KonteksTema = createContext({ mode: "terang", palet: PALET.terang, ganti: () => {} });

function modeSistem() {
  try { return window.matchMedia("(prefers-color-scheme: dark)").matches ? "gelap" : "terang"; } catch { return "terang"; }
}

export function useTemaPenyedia() {
  const [pilihan, setPilihan] = useState(() => { try { return localStorage.getItem(KUNCI) || "sistem"; } catch { return "sistem"; } });
  const [sistem, setSistem] = useState(modeSistem);
  useEffect(() => {
    let mq;
    try { mq = window.matchMedia("(prefers-color-scheme: dark)"); } catch { return undefined; }
    const ubah = () => setSistem(mq.matches ? "gelap" : "terang");
    mq.addEventListener?.("change", ubah);
    return () => mq.removeEventListener?.("change", ubah);
  }, []);
  const mode = pilihan === "sistem" ? sistem : pilihan;
  useEffect(() => {
    const akar = document.documentElement;
    if (pilihan === "sistem") akar.removeAttribute("data-theme");
    else akar.setAttribute("data-theme", pilihan === "gelap" ? "dark" : "light");
    try { localStorage.setItem(KUNCI, pilihan); } catch { /* storage diblokir */ }
  }, [pilihan]);
  const ganti = () => setPilihan(mode === "gelap" ? "terang" : "gelap");
  return { mode, palet: PALET[mode], ganti };
}

export function useTema() {
  return useContext(KonteksTema);
}

export const persen = (x, d = 0) => (x === null || x === undefined ? "–" : `${(100 * x).toFixed(d)}%`);
export const rupiahJuta = (x) => (x === null || x === undefined ? "–" : `Rp${Math.round(x).toLocaleString("id-ID")} jt`);
