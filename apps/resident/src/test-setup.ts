import '@testing-library/jest-dom/vitest';

// jsdom has no canvas; the sky backdrop treats a missing 2D context as "draw nothing".
HTMLCanvasElement.prototype.getContext = (() => null) as typeof HTMLCanvasElement.prototype.getContext;
