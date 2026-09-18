import '@testing-library/jest-dom/vitest';
import {afterEach, beforeEach, vi} from 'vitest';
import {cleanup, configure} from '@testing-library/react';

// RTL waits 1s by default for `waitFor`/`findBy*`. That is ample for one spec
// and not reliably ample for the whole suite: several specs drive a debounced
// autocomplete on real timers (SearchBar debounces 300ms, then two endpoints
// resolve), and under the CPU contention of a 200-test run the chain can cross
// the second and fail a test that has nothing wrong with it. It showed up
// exactly that way -- `SearchBar.test.tsx` green alone, red in the full run.
//
// This raises patience, not tolerance: every assertion stays exactly as strict,
// and a test that is genuinely wrong still fails, one or two seconds later.
configure({asyncUtilTimeout: 3000});

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
//
// jsdom has no layout engine, so every element here measures 0x0 and the stub
// never fires. Recharts reads that as a zero-size container and says so --
// "The width(0) and height(0) of chart should be greater than 0" -- in the
// output of any spec that mounts one. That message is the test environment
// talking, not the app: in a browser the container has the size its class list
// gives it, and each chart is handed that size through `initialDimension` so it
// never sees a negative or zero measurement at all. Do not "fix" a component to
// silence this line.
class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
    (globalThis as {ResizeObserver?: unknown}).ResizeObserver = ResizeObserverStub;
}

// jsdom has no 2D context either: `getContext('2d')` returns null *and* prints
// "Not implemented: HTMLCanvasElement.prototype.getContext" on the virtual
// console, once per call. `GraphCanvas` probes for one to measure label text and
// falls back to an average glyph width -- it is built for exactly this, so the
// fallback is what runs either way and the printout adds nothing but noise at
// the top of the run. Same reasoning as the stub above: the environment is
// answering a question the code already knows to ask twice.
//
// Returning null rather than throwing keeps it behaviour-identical to jsdom's
// own answer; only the console line goes away.
HTMLCanvasElement.prototype.getContext = (() => null) as unknown as typeof HTMLCanvasElement.prototype.getContext;

beforeEach(() => {
    vi.clearAllMocks(); // reset call history; implementations survive
    localStorage.clear();
    // Also the session storage: an unticked "Zapamätať prihlásenie" puts the
    // tokens there, and jsdom keeps one `sessionStorage` for the whole file --
    // so without this a signed-in test signs in the next one.
    sessionStorage.clear();
    document.documentElement.className = '';
});

// RTL's auto-cleanup only registers itself against a *global* afterEach (which
// needs globals:true). With globals:false we register it manually.
afterEach(() => {
    cleanup();
});
