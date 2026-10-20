import '@testing-library/jest-dom/vitest';

// jsdom has no canvas; the sky backdrop treats a missing 2D context as "draw nothing".
HTMLCanvasElement.prototype.getContext = (() => null) as typeof HTMLCanvasElement.prototype.getContext;

// Node 26 defines its own global localStorage, which is undefined unless Node runs with
// --localstorage-file. That stops vitest from installing jsdom's Storage, so the prefs tests
// saw no localStorage. Use jsdom's real Storage when that happens (Node 22 is unaffected).
const dom = (globalThis as { jsdom?: { window: Window } }).jsdom;
if (typeof globalThis.localStorage === 'undefined' && dom) {
  Object.defineProperty(globalThis, 'localStorage', { value: dom.window.localStorage, configurable: true, writable: true });
}
