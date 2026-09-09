import '@testing-library/jest-dom/vitest';
import {afterEach, beforeEach, vi} from 'vitest';
import {cleanup} from '@testing-library/react';

// jsdom has no matchMedia. ThemeContext reads it during render (isDark state
// initializer) and subscribes to 'change' events in an effect; ThemeToggle and
// ThemeProvider rely on the same API.
Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(), // legacy
        removeListener: vi.fn(), // legacy
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    })),
});

// Cheap insurance: recharts (reached via Profile -> CompanyDetail ->
// FinancialChart) touches ResizeObserver whenever a responsive chart measures.
// These specs never mount a chart, but a no-op stub keeps the whole import
// graph safe if that ever changes.
class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
    (globalThis as {ResizeObserver?: unknown}).ResizeObserver = ResizeObserverStub;
}

beforeEach(() => {
    vi.clearAllMocks(); // reset call history; implementations survive
    localStorage.clear();
    document.documentElement.className = '';
});

// RTL's auto-cleanup only registers itself against a *global* afterEach (which
// needs globals:true). With globals:false we register it manually.
afterEach(() => {
    cleanup();
});
