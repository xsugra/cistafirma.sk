import {act, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {ThemeProvider, useTheme} from '../../context/ThemeContext';
import {SeatMap, zoomFor} from './SeatMap';
import type {SeatLocation} from '../../types';

/**
 * Google's renderer cannot be asserted through the DOM here: jsdom has no
 * layout, so it would draw nothing and every assertion would pass for the wrong
 * reason. What *can* be asserted is what we ask Google for -- and that is also
 * where every defect in this component has to live, because a circle that never
 * receives `radiusM` still renders, and still lies.
 *
 * So `@googlemaps/js-api-loader` is replaced by a recorder. The fake classes
 * capture their options; the tests read them back. Nothing below asserts
 * Google's own behaviour, and nothing below needs a network.
 */
const g = vi.hoisted(() => {
    type Options = Record<string, unknown>;
    const state = {
        maps: [] as Options[],
        circles: [] as Options[],
        markers: [] as Options[],
        mapUpdates: [] as Options[],
        libraryNames: [] as string[],
        /** A single slot, not a list: `setOptions` is called once per page. */
        configured: null as unknown,
    };

    class FakeMap {
        constructor(_container: unknown, options: Options) {
            state.maps.push(options);
        }
        setCenter(): void {}
        setZoom(): void {}
        setOptions(options: Options): void {
            state.mapUpdates.push(options);
        }
    }

    class FakeCircle {
        constructor(private readonly options: Options) {
            state.circles.push(options);
        }
        setCenter(centre: unknown): void {
            this.options.center = centre;
        }
        setRadius(radius: unknown): void {
            this.options.radius = radius;
        }
        /** The only way Google lets a circle be detached from its map. */
        setMap(map: unknown): void {
            this.options.map = map;
        }
    }

    /**
     * The real element exposes `position`, `title` and `map` as accessors, and
     * detaches through `map = null` rather than a `setMap` method.
     */
    class FakeMarker {
        constructor(private readonly options: Options) {
            state.markers.push(options);
        }
        set position(value: unknown) {
            this.options.position = value;
        }
        get position(): unknown {
            return this.options.position;
        }
        set title(value: unknown) {
            this.options.title = value;
        }
        get title(): unknown {
            return this.options.title;
        }
        set map(value: unknown) {
            this.options.map = value;
        }
        get map(): unknown {
            return this.options.map;
        }
    }

    return {state, FakeMap, FakeCircle, FakeMarker};
});

vi.mock('@googlemaps/js-api-loader', () => ({
    setOptions: (options: unknown) => {
        g.state.configured = options;
    },
    importLibrary: (name: string) => {
        g.state.libraryNames.push(name);
        return Promise.resolve(
            name === 'maps'
                ? {Map: g.FakeMap, Circle: g.FakeCircle}
                : {AdvancedMarkerElement: g.FakeMarker},
        );
    },
}));

/** A real row: PSČ 82109 Bratislava, the median-sized area in the table. */
const seat: SeatLocation = {
    lat: 48.14748,
    lon: 17.14051,
    radiusM: 737,
    psc: '82109',
    precision: 'postal_code',
};

const draw = (value: SeatLocation = seat) =>
    render(
        <ThemeProvider>
            <SeatMap seat={value} />
        </ThemeProvider>,
    );

/** The header's theme toggle, reduced to the one thing it does to the context. */
const ThemeToggle = () => {
    const {isDark, setTheme} = useTheme();
    return (
        <button type="button" onClick={() => setTheme(isDark ? 'light' : 'dark')}>
            Prepnúť tému
        </button>
    );
};

const drawWithToggle = (value: SeatLocation = seat) =>
    render(
        <ThemeProvider>
            <ThemeToggle />
            <SeatMap seat={value} />
        </ThemeProvider>,
    );

describe('zoomFor', () => {
    // The stored radii run 270 m to 8 717 m, so these are ordinary rows rather
    // than edge cases. The exact integers are the point: the contract is "the
    // drawn circle spans roughly RADIUS_PIXELS", and the rounding step is where
    // that contract is kept or lost.
    it('zooms in for a tight PSČ and out for a sprawling one', () => {
        expect(zoomFor({...seat, radiusM: 270})).toBe(15);
        expect(zoomFor({...seat, radiusM: 737})).toBe(14);
        expect(zoomFor({...seat, radiusM: 4118})).toBe(11);
        expect(zoomFor({...seat, radiusM: 8717})).toBe(10);
    });

    it('never draws a bigger circle smaller than a tighter one', () => {
        const zooms = [270, 737, 1200, 4118, 8717].map((radiusM) =>
            zoomFor({...seat, radiusM}),
        );
        for (let i = 1; i < zooms.length; i++) {
            expect(zooms[i]).toBeLessThanOrEqual(zooms[i - 1]);
        }
    });

    it('clamps instead of following a radius no PSČ has', () => {
        expect(zoomFor({...seat, radiusM: 50})).toBe(16);
        expect(zoomFor({...seat, radiusM: 500_000})).toBe(7);
    });

    it('survives a radius of zero rather than producing Infinity', () => {
        expect(Number.isFinite(zoomFor({...seat, radiusM: 0}))).toBe(true);
    });
});

describe('SeatMap', () => {
    beforeEach(() => {
        g.state.maps.length = 0;
        g.state.circles.length = 0;
        g.state.markers.length = 0;
        g.state.mapUpdates.length = 0;
        g.state.libraryNames.length = 0;
        // `g.state.configured` is deliberately *not* cleared: the loader is
        // configured once for the life of the module, so the slot keeps whatever
        // the first successful load put there for the rest of this file.
        vi.unstubAllEnvs();
        // Nobody stubs this in most of the cases below, and `mapId()` reads it at
        // render time. `vi.unstubAllEnvs` restores rather than clears, so without
        // this line the moment an operator does what `.env.default` and the plan
        // tell them to -- put a real Map ID in the root `.env` -- the theme test
        // fails with a message about a variable it never mentions.
        vi.stubEnv('VITE_GOOGLE_MAPS_MAP_ID', '');
    });

    afterEach(() => {
        vi.unstubAllEnvs();
    });

    describe('without a key', () => {
        beforeEach(() => vi.stubEnv('VITE_GOOGLE_MAPS_API_KEY', ''));

        it('names the missing variable instead of drawing an empty box', () => {
            draw();

            expect(screen.getByText(/VITE_GOOGLE_MAPS_API_KEY/)).toBeInTheDocument();
            // The one outcome that must not happen: a blank grey rectangle that
            // looks like a slow network rather than a misconfiguration.
            expect(screen.queryByRole('region')).not.toBeInTheDocument();
            expect(g.state.maps).toHaveLength(0);
        });

        it('does not ask Google for the script at all', async () => {
            // Billing is per map load, and a key-less deployment should not even
            // reach Google's servers.
            draw();
            // The load-bearing observable is `libraryNames`, because the mocked
            // loader records it *synchronously*, before its promise resolves.
            // Asserting on the map or the circle here would hold whatever the
            // component did: both are created a microtask after `render()`
            // returns, so an empty list proves only that the test had not waited.
            await act(async () => {});

            expect(g.state.libraryNames).toEqual([]);
        });
    });

    describe('with a key', () => {
        beforeEach(() => vi.stubEnv('VITE_GOOGLE_MAPS_API_KEY', 'test-key'));

        it('configures the script from the environment, once, with both libraries', async () => {
            // The option names are the loader's, not ours: v2 renamed `apiKey` to
            // `key` and `version` to `v`, and a stale name is accepted silently
            // by the bootstrap and then fails as an unbilled or unauthorised
            // request. `setOptions` throws if it runs twice, so the fact that
            // this file mounts eight maps and the slot still holds one call is
            // the assertion that the guard works.
            draw();

            await waitFor(() => expect(g.state.maps).toHaveLength(1));
            expect(g.state.configured).toEqual({
                key: 'test-key',
                v: 'weekly',
                language: 'sk',
                region: 'SK',
            });
            expect([...g.state.libraryNames].sort()).toEqual(['maps', 'marker']);
        });

        it('gives the circle the measured radius, not a default', async () => {
            draw();

            await waitFor(() => expect(g.state.circles).toHaveLength(1));
            expect(g.state.circles[0].radius).toBe(737);
            expect(g.state.circles[0].center).toEqual({lat: 48.14748, lng: 17.14051});
        });

        it('centres the dot on the centroid, the same place as the circle', async () => {
            draw();

            await waitFor(() => expect(g.state.markers).toHaveLength(1));
            expect(g.state.markers[0].position).toEqual({lat: 48.14748, lng: 17.14051});
            expect(g.state.markers[0].title).toBe('Stred PSČ 82109');
        });

        it('does not let the map capture the page scroll', async () => {
            draw();

            await waitFor(() => expect(g.state.maps).toHaveLength(1));
            expect(g.state.maps[0].scrollwheel).toBe(false);
            expect(g.state.maps[0].gestureHandling).toBe('cooperative');
        });

        it('draws in the app theme, which needs a Map ID', async () => {
            // Light is what this project's ThemeProvider resolves to under
            // jsdom's `prefers-color-scheme: dark -> false` stub.
            draw();

            await waitFor(() => expect(g.state.maps).toHaveLength(1));
            expect(g.state.maps[0].colorScheme).toBe('LIGHT');
            expect(g.state.maps[0].mapId).toBe('DEMO_MAP_ID');
        });

        it('takes the Map ID from the environment when one is configured', async () => {
            // The whole reason vite-env.d.ts and `envDir` exist: a production Map
            // ID that never reaches the bundle would leave dark mode silently
            // doing nothing.
            vi.stubEnv('VITE_GOOGLE_MAPS_MAP_ID', 'cistafirma-prod');

            draw();

            await waitFor(() => expect(g.state.maps).toHaveLength(1));
            expect(g.state.maps[0].mapId).toBe('cistafirma-prod');
        });

        it('rebuilds the map when the theme changes, because it cannot re-theme it', async () => {
            // `colorScheme` is an initialization-only option: Google documents it
            // as settable when the map is created and ignored afterwards, so the
            // effect that used to call `map.setOptions({colorScheme})` did
            // nothing at all. Following a theme toggle therefore costs a second
            // map and a second billable load -- which is why it is asserted here
            // rather than assumed, and why `mapUpdates` is asserted empty: the
            // no-op must not come back.
            drawWithToggle();
            await waitFor(() => expect(g.state.maps).toHaveLength(1));
            expect(g.state.maps[0].colorScheme).toBe('LIGHT');

            fireEvent.click(screen.getByRole('button', {name: 'Prepnúť tému'}));

            await waitFor(() => expect(g.state.maps).toHaveLength(2));
            expect(g.state.maps[1].colorScheme).toBe('DARK');
            expect(g.state.maps[1].center).toEqual({lat: 48.14748, lng: 17.14051});
            // The map the reader can no longer see is let go of, not forgotten:
            // Google has no destroy(), so the overlays are detached by hand.
            expect(g.state.circles[0].map).toBeNull();
            expect(g.state.markers[0].map).toBeNull();
            expect(g.state.circles[1].radius).toBe(737);
            expect(g.state.mapUpdates).toEqual([]);
        });

        it('lets the map go on unmount instead of leaving it alive', async () => {
            // The card unmounts once per company profile read, so a teardown that
            // skipped this would leave one live map -- listeners and WebGL context
            // included -- behind every profile the reader opens.
            const {unmount} = draw();
            await waitFor(() => expect(g.state.maps).toHaveLength(1));

            unmount();

            expect(g.state.circles[0].map).toBeNull();
            expect(g.state.markers[0].map).toBeNull();
        });

        it('moves the drawn map to a new seat instead of billing for a second', async () => {
            const next: SeatLocation = {
                lat: 48.7164,
                lon: 21.2611,
                radiusM: 4118,
                psc: '04001',
                precision: 'postal_code',
            };
            const {rerender} = draw();
            await waitFor(() => expect(g.state.maps).toHaveLength(1));

            rerender(
                <ThemeProvider>
                    <SeatMap seat={next} />
                </ThemeProvider>,
            );

            await waitFor(() => expect(g.state.circles[0].radius).toBe(4118));
            expect(g.state.circles[0].center).toEqual({lat: 48.7164, lng: 21.2611});
            expect(g.state.markers[0].title).toBe('Stred PSČ 04001');
            // One map and one circle for the whole session: a second of either
            // would be a second load, and a second load is a second charge.
            expect(g.state.maps).toHaveLength(1);
            expect(g.state.circles).toHaveLength(1);
        });

        it('redraws when the seat changes before the script has landed', async () => {
            // The map is created a network round-trip after mount. Reading the
            // seat from the mount closure would draw the *previous* company and
            // leave no later effect to correct it.
            const next: SeatLocation = {
                lat: 48.7164,
                lon: 21.2611,
                radiusM: 4118,
                psc: '04001',
                precision: 'postal_code',
            };
            const {rerender} = draw();
            rerender(
                <ThemeProvider>
                    <SeatMap seat={next} />
                </ThemeProvider>,
            );

            await waitFor(() => expect(g.state.circles).toHaveLength(1));
            expect(g.state.circles[0].radius).toBe(4118);
            expect(g.state.circles[0].center).toEqual({lat: 48.7164, lng: 21.2611});
        });

        it('reports a rejected key instead of showing a watermark', async () => {
            // Google calls this global when the key is invalid, unbilled or
            // restricted to the wrong referrer -- after the script has loaded
            // successfully. Without the hook the map renders as a grey box.
            draw();
            await waitFor(() => expect(g.state.maps).toHaveLength(1));

            act(() => {
                (window as {gm_authFailure?: () => void}).gm_authFailure?.();
            });

            expect(screen.getByText(/kľúč odmietli/)).toBeInTheDocument();
            expect(screen.queryByRole('region')).not.toBeInTheDocument();
            // The message takes the container away from the map and nothing
            // re-runs the effect when it does, so the map is released here or it
            // outlives its own box.
            expect(g.state.circles[0].map).toBeNull();
            expect(g.state.markers[0].map).toBeNull();
        });

        it('labels the region with the PSČ it is drawing', async () => {
            draw();

            expect(
                await screen.findByRole('region', {name: /PSČ 82109/}),
            ).toBeInTheDocument();
        });
    });
});
