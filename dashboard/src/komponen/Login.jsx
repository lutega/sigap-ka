// Halaman login konsol (spesifikasi 15). Akun awal admin/admin hanya untuk prototipe dan demo.
// Lapis: A (antarmuka) -> POST /auth/login.
import { useState } from "react";
import { api } from "../api.js";
import { Pesan } from "./umum.jsx";

export default function Login({ onMasuk }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [galat, setGalat] = useState(null);
  const [sibuk, setSibuk] = useState(false);

  async function kirim(e) {
    e.preventDefault();
    setSibuk(true);
    setGalat(null);
    try {
      const d = await api.login(username, password);
      onMasuk({ username: d.username, level: d.level });
    } catch (err) {
      setGalat(err);
    } finally {
      setSibuk(false);
    }
  }

  return (
    <div className="login">
      <form className="kartu" onSubmit={kirim}>
        <div>
          <h1 style={{ fontSize: 20 }}>SIGAP-KA</h1>
          <p className="sekunder" style={{ margin: "4px 0 0" }}>Konsol pendukung keputusan kontinjensi banjir koridor Brumbung–Karangjati</p>
        </div>
        <label className="isian">Username
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </label>
        <label className="isian">Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </label>
        <button className="tombol utama" type="submit" disabled={sibuk}>{sibuk ? "Memproses…" : "Masuk"}</button>
        <Pesan galat={galat} />
        <p className="muted" style={{ fontSize: 12, margin: 0 }}>Prototipe Proyek Minor KS5203. Usulan sistem bersifat saran; status jalur ditetapkan KAI.</p>
      </form>
    </div>
  );
}
