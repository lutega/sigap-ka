// Penyiapan vitest: matcher jest-dom dan ResizeObserver tiruan (dibutuhkan Recharts di jsdom).
import "@testing-library/jest-dom/vitest";

class ResizeObserverTiruan {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver || ResizeObserverTiruan;
if (!window.matchMedia) {
  window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
}
