// Kelola pengguna (khusus admin, spesifikasi 15): tambah, nonaktifkan/aktifkan, ubah level,
// atur ulang password.
// Lapis: A (antarmuka) -> /pengguna.
import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Pesan } from "../komponen/umum.jsx";

export default function KelolaPengguna() {
  const [daftar, setDaftar] = useState([]);
  const [baru, setBaru] = useState({ username: "", password: "", level: "operator" });
  const [galat, setGalat] = useState(null);
  const [pesan, setPesan] = useState("");

  const muat = () => api.get("/pengguna").then(setDaftar).catch(setGalat);
  useEffect(() => { muat(); }, []);

  async function aksi(fn, ok) {
    try { await fn(); setPesan(ok); setGalat(null); await muat(); } catch (e) { setGalat(e); setPesan(""); }
  }

  return (
    <section className="kartu">
      <div className="kartu-kepala"><h2>Kelola pengguna</h2></div>
      <form className="baris-filter" onSubmit={(e) => { e.preventDefault(); aksi(() => api.post("/pengguna", baru), `Pengguna ${baru.username} ditambahkan.`); setBaru({ username: "", password: "", level: "operator" }); }}>
        <label className="isian">Username <input type="text" value={baru.username} onChange={(e) => setBaru({ ...baru, username: e.target.value })} required /></label>
        <label className="isian">Password <input type="password" value={baru.password} onChange={(e) => setBaru({ ...baru, password: e.target.value })} minLength={4} required /></label>
        <label className="isian">Level
          <select value={baru.level} onChange={(e) => setBaru({ ...baru, level: e.target.value })}>
            <option value="operator">operator</option><option value="admin">admin</option>
          </select>
        </label>
        <button className="tombol utama" type="submit">Tambah</button>
      </form>
      <Pesan galat={galat} />
      {pesan && <p className="sekunder">{pesan}</p>}
      <div className="gulir">
        <table>
          <thead><tr><th>Username</th><th>Level</th><th>Status</th><th>Aksi</th></tr></thead>
          <tbody>
            {daftar.map((p) => (
              <tr key={p.id}>
                <td>{p.username}</td>
                <td>
                  <select value={p.level} onChange={(e) => aksi(() => api.patch(`/pengguna/${p.id}`, { level: e.target.value }), "Level diubah.")}>
                    <option value="operator">operator</option><option value="admin">admin</option>
                  </select>
                </td>
                <td>{p.aktif ? "aktif" : "nonaktif"}</td>
                <td style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button className="tombol kecil" onClick={() => aksi(() => api.patch(`/pengguna/${p.id}`, { aktif: !p.aktif }), p.aktif ? "Dinonaktifkan." : "Diaktifkan.")}>
                    {p.aktif ? "Nonaktifkan" : "Aktifkan"}
                  </button>
                  <button className="tombol kecil" onClick={() => {
                    const pw = window.prompt(`Password baru untuk ${p.username} (minimal 4 karakter)`);
                    if (pw) aksi(() => api.post(`/pengguna/${p.id}/atur-ulang-password`, { password_baru: pw }), "Password diatur ulang.");
                  }}>Atur ulang password</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
