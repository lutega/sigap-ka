// Papan 9 tindakan: status SIGAP, peluang vs kurva, sisa waktu, alasan singkat, peringatan
// maladaptasi, dan tombol Setujui / Tolak / Batalkan (human in the loop, spesifikasi 12.1).
// Lapis: A (antarmuka).
import { useState } from "react";
import { persen } from "../tema.js";
import { StatusTindakan } from "./umum.jsx";

export default function PapanTindakan({ papan, onKeputusan, sibuk, dipilih, onPilih }) {
  const [alasanTolak, setAlasanTolak] = useState({});
  if (!papan) return <p className="muted">Memuat papan tindakan…</p>;
  return (
    <div>
      {papan.tindakan.map((b) => {
        const bisaSetujui = b.status === "Putuskan sekarang" || b.status === "Tunggu prakiraan berikutnya";
        return (
          <div className="papan-baris" key={b.tindakan} data-testid={`baris-${b.tindakan}`}
            style={dipilih === b.tindakan ? { background: "var(--surface-2)" } : undefined}>
            <button className="tombol kecil id" onClick={() => onPilih && onPilih(b.tindakan)} title="Tampilkan kurva tindakan ini">
              {b.tindakan}
            </button>
            <div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                <strong>{b.nama}</strong>
                {!b.terkonfirmasi && <span className="lencana dummy">belum dikonfirmasi tim</span>}
                <span className="lencana dummy" title="Parameter C, L, P masih dummy">parameter {b.label_parameter}</span>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 4, alignItems: "center" }}>
                <StatusTindakan status={b.status} />
                <span className="sekunder angka">peluang {persen(b.peluang)} · kurva {b.ambang === null ? "–" : persen(b.ambang)}</span>
                <span className="muted angka">{b.sisa_jam >= 0 ? `sisa ${b.sisa_jam} jam ke batas (T-${b.waktu_siap_jam})` : `batas T-${b.waktu_siap_jam} lewat`}</span>
              </div>
              <div className="alasan">{b.alasan}</div>
              {b.peringatan.map((p, i) => <div className="peringatan" key={i}><span aria-hidden="true">⚠ </span>{p}</div>)}
            </div>
            <div className="aksi">
              {b.status === "Sudah disetujui" ? (
                <button className="tombol kecil" disabled={sibuk} onClick={() => onKeputusan(b.tindakan, "batalkan")}>Batalkan</button>
              ) : (
                <>
                  <button className="tombol kecil utama" disabled={sibuk || !bisaSetujui} onClick={() => onKeputusan(b.tindakan, "setujui")}>Setujui</button>
                  <input type="text" placeholder="alasan tolak" aria-label={`alasan tolak ${b.tindakan}`} style={{ width: 120, padding: "3px 6px", fontSize: 12 }}
                    value={alasanTolak[b.tindakan] || ""} onChange={(e) => setAlasanTolak({ ...alasanTolak, [b.tindakan]: e.target.value })} />
                  <button className="tombol kecil" disabled={sibuk || b.status === "Terlambat"}
                    onClick={() => onKeputusan(b.tindakan, "tolak", alasanTolak[b.tindakan])}>Tolak</button>
                </>
              )}
            </div>
          </div>
        );
      })}
      {papan.catatan.map((c, i) => <p className="catatan-kewenangan" key={i}>{c}</p>)}
    </div>
  );
}
