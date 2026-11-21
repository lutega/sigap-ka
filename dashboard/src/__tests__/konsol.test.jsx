// Tes konsol SIGAP-KA (vitest + Testing Library): login, tab, menu admin, papan tindakan,
// label nyata/dummy, dan larangan teks pernyataan jalur aman di seluruh sumber antarmuka.
// Lapis: QA, antarmuka.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App.jsx";
import PapanTindakan from "../komponen/PapanTindakan.jsx";
import { LabelData, StatusTindakan } from "../komponen/umum.jsx";
import { simpanToken } from "../api.js";

const PAPAN = {
  episode_id: "UJI", jam_sebelum_t0: 24, ringkas_status: {},
  catatan: ["Status jalur ditetapkan pihak berwenang KAI berdasarkan pemeriksaan lapangan."],
  inferensi: { peluang: 0.4 },
  tindakan: [
    { tindakan: "T1", nama: "Informasi penumpang dan refund", status: "Terlambat", peluang: 0.4, ambang: null, sisa_jam: -12,
      waktu_siap_jam: 36, terkonfirmasi: true, label_parameter: "dummy", alasan: "Batas waktu lewat.", peringatan: [] },
    { tindakan: "T3", nama: "Memutar via Gundih atau Solo", status: "Putuskan sekarang", peluang: 0.8, ambang: 0.6, sisa_jam: 12,
      waktu_siap_jam: 12, terkonfirmasi: true, label_parameter: "dummy", alasan: "Peluang di atas kurva.",
      peringatan: ["Rute alternatif via Gundih juga diguyur hujan 60 mm/24 jam."] },
    { tindakan: "T6", nama: "Tindakan T6 (belum dikonfirmasi tim)", status: "Sudah disetujui", peluang: 0.4, ambang: 0.5, sisa_jam: 6,
      waktu_siap_jam: 18, terkonfirmasi: false, label_parameter: "dummy", alasan: "Disetujui.", peringatan: [] },
  ],
};

function balasan(data, status = 200) {
  return Promise.resolve({ ok: status < 400, status, statusText: "", text: () => Promise.resolve(JSON.stringify(data)) });
}

describe("papan tindakan", () => {
  it("menampilkan status dengan label, peringatan, dan tombol sesuai status", () => {
    const onKeputusan = vi.fn();
    render(<PapanTindakan papan={PAPAN} onKeputusan={onKeputusan} sibuk={false} />);
    expect(screen.getByText("Putuskan sekarang")).toBeInTheDocument();
    expect(screen.getByText(/Gundih juga diguyur/)).toBeInTheDocument();
    expect(screen.getByText("belum dikonfirmasi tim")).toBeInTheDocument();
    const t3 = screen.getByTestId("baris-T3");
    fireEvent.click(t3.querySelector("button.utama"));
    expect(onKeputusan).toHaveBeenCalledWith("T3", "setujui");
    const t1 = screen.getByTestId("baris-T1");
    expect(t1.querySelector("button.utama")).toBeDisabled();
    expect(screen.getByTestId("baris-T6").textContent).toContain("Batalkan");
    expect(screen.getByText(/ditetapkan pihak berwenang KAI/)).toBeInTheDocument();
  });

  it("status dan label data tidak bergantung warna saja", () => {
    render(<><StatusTindakan status="Terlambat" /><LabelData label="dummy" /><LabelData label="nyata" /></>);
    expect(screen.getByText("Terlambat")).toBeInTheDocument();
    expect(screen.getByText("data dummy")).toBeInTheDocument();
    expect(screen.getByText("data nyata")).toBeInTheDocument();
  });
});

describe("aplikasi", () => {
  beforeEach(() => { simpanToken(null); });
  afterEach(() => { vi.restoreAllMocks(); });

  it("tanpa token menampilkan halaman login dan masuk sebagai admin", async () => {
    const fetchTiruan = vi.fn((url) => {
      if (url === "/auth/login") return balasan({ access_token: "t", username: "admin", level: "admin" });
      if (url === "/episode") return balasan([]);
      if (url === "/info") return balasan({ batas_klaim: ["a"], catatan_kewenangan: ["Status jalur ditetapkan KAI."] });
      return balasan([]);
    });
    vi.stubGlobal("fetch", fetchTiruan);
    render(<App />);
    expect(await screen.findByRole("button", { name: "Masuk" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "admin" } });
    fireEvent.click(screen.getByRole("button", { name: "Masuk" }));
    await waitFor(() => expect(screen.getByRole("tab", { name: "Operasi" })).toBeInTheDocument());
    for (const t of ["Data", "Prediksi", "Kurva pemicu", "Simulasi", "Kelola pengguna"]) {
      expect(screen.getByRole("tab", { name: t })).toBeInTheDocument();
    }
  });

  it("operator tidak melihat menu kelola pengguna", async () => {
    simpanToken("t");
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (url === "/auth/saya") return balasan({ id: 2, username: "op1", level: "operator", aktif: true });
      if (url === "/info") return balasan({ batas_klaim: [], catatan_kewenangan: [] });
      return balasan([]);
    }));
    render(<App />);
    await waitFor(() => expect(screen.getByRole("tab", { name: "Operasi" })).toBeInTheDocument());
    expect(screen.queryByRole("tab", { name: "Kelola pengguna" })).toBeNull();
  });

  it("login gagal menampilkan pesan", async () => {
    vi.stubGlobal("fetch", vi.fn(() => balasan({ detail: "username atau password salah" }, 401)));
    render(<App />);
    fireEvent.change(await screen.findByLabelText("Username"), { target: { value: "x" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "y" } });
    fireEvent.click(screen.getByRole("button", { name: "Masuk" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("username atau password salah");
  });
});

describe("teks antarmuka", () => {
  it("tidak ada kata 'aman' atau 'safe' sebagai kata utuh di sumber konsol (FR-A5)", () => {
    const akar = join(__dirname, "..");
    const berkas = [];
    const telusur = (d) => readdirSync(d).forEach((n) => {
      const p = join(d, n);
      if (statSync(p).isDirectory()) { if (n !== "__tests__") telusur(p); } else if (/\.(jsx?|css)$/.test(n)) berkas.push(p);
    });
    telusur(akar);
    expect(berkas.length).toBeGreaterThan(5);
    for (const p of berkas) {
      const isi = readFileSync(p, "utf-8");
      expect(isi, p).not.toMatch(/\b(aman|safe)\b/i);
    }
  });
});
