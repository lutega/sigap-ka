// Klien REST SIGAP-KA.
// Lapis: A (antarmuka) -> API. Dashboard hanya berkomunikasi lewat API ini.
// Token JWT disimpan di sessionStorage (dibungkus try/catch; tetap jalan bila storage diblokir).

const KUNCI_TOKEN = "sigap_token";
let tokenMemori = null;

export function simpanToken(token) {
  tokenMemori = token;
  try { if (token) sessionStorage.setItem(KUNCI_TOKEN, token); else sessionStorage.removeItem(KUNCI_TOKEN); } catch { /* storage diblokir */ }
}

export function ambilToken() {
  if (tokenMemori) return tokenMemori;
  try { tokenMemori = sessionStorage.getItem(KUNCI_TOKEN); } catch { tokenMemori = null; }
  return tokenMemori;
}

export class GalatApi extends Error {
  constructor(status, pesan) { super(pesan); this.status = status; }
}

async function minta(metode, jalur, badan) {
  const kepala = { "Content-Type": "application/json" };
  const token = ambilToken();
  if (token) kepala.Authorization = `Bearer ${token}`;
  const r = await fetch(jalur, { method: metode, headers: kepala, body: badan ? JSON.stringify(badan) : undefined });
  if (r.status === 401 && jalur !== "/auth/login") {
    simpanToken(null);
    window.dispatchEvent(new Event("sigap-keluar"));
  }
  const teks = await r.text();
  const data = teks ? JSON.parse(teks) : null;
  if (!r.ok) {
    const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : r.statusText;
    throw new GalatApi(r.status, detail);
  }
  return data;
}

export const api = {
  get: (jalur) => minta("GET", jalur),
  post: (jalur, badan) => minta("POST", jalur, badan || {}),
  patch: (jalur, badan) => minta("PATCH", jalur, badan || {}),
  login: async (username, password) => {
    const d = await minta("POST", "/auth/login", { username, password });
    simpanToken(d.access_token);
    return d;
  },
};
