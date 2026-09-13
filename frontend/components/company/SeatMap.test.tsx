import {act, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import type {FeatureCollection, Polygon} from 'geojson';
import type {StyleSpecification} from '@maplibre/maplibre-gl-style-spec';
import {ThemeProvider, useTheme} from '../../context/ThemeContext';
import {SEAT_SOURCE, SeatMap, zoomFor} from './SeatMap';
import {TILEJSON_URL, TILES_SOURCE} from '../../map/style';
import type {SeatLocation} from '../../types';

/**
 * MapLibre cannot be asserted through the DOM here: jsdom has no WebGL and no
 * layout, so a real map would draw nothing and every assertion would pass for the
 * wrong reason. What *can* be asserted is what we ask MapLibre for -- and that is
 * also where every defect in this component has to live, because a ring that never
 * receives `radiusM` still renders, and still lies.
 *
 * So `maplibre-gl` is replaced by a recorder. The fake captures constructor
 * options, sources, layers, controls and camera moves; the tests read them back.
 * Nothing below asserts MapLibre's own behaviour, and nothing below needs a
 * network.
 *
 * The one piece of real behaviour the fake keeps is the awkward part: `style.load`
 * is asynchronous, and it fires again on every `setStyle`, dropping every source
 * and layer with the old style. That is the state machine the seat layers have to
 * survive, so it is the state machine the fake models.
 */
const g = vi.hoisted(() => {
    type Options = Record<string, unknown>;
    type Handler = (event: unknown) => void;

    const state = {
        maps: [] as FakeMap[],
        /** What `queryRenderedFeatures` answers; the empty case is a test. */
        renderedFeatures: [{}] as unknown[],
        /** Every `setWorkerUrl` argument. The module calls it once, on import. */
        workerUrls: [] as unknown[],
    };

    /** Stands in for MapLibre's `GeoJSONSource`. */
    class FakeGeoJSONSource {
        readonly setDataCalls: unknown[] = [];

        constructor(
            readonly id: string,
            public data: unknown,
        ) {}

        setData(data: unknown): void {
            this.data = data;
            this.setDataCalls.push(data);
        }
    }

    class FakeMap {
        readonly handlers = new Map<string, Handler[]>();
        readonly controls: Array<{control: unknown; position: string}> = [];
        readonly sources = new Map<string, FakeGeoJSONSource>();
        readonly layers: unknown[] = [];
        /** Every `setStyle` argument, in order. The constructor's is not one. */
        readonly styles: unknown[] = [];
        readonly jumps: unknown[] = [];
        removed = false;

        constructor(readonly options: Options) {
            state.maps.push(this);
            // The real one fires this once its style has been fetched and parsed.
            // Nothing about the style is synchronous, so neither is the fake.
            queueMicrotask(() => this.emit('style.load', {}));
        }

        on(event: string, handler: Handler): void {
            const list = this.handlers.get(event) ?? [];
            list.push(handler);
            this.handlers.set(event, list);
        }

        emit(event: string, payload: unknown): void {
            for (const handler of this.handlers.get(event) ?? []) handler(payload);
        }

        addControl(control: unknown, position?: string): void {
            this.controls.push({control, position: position ?? 'top-right'});
        }

        addSource(id: string, definition: {data?: unknown}): void {
            // The real one throws, and the component relies on it not happening.
            if (this.sources.has(id)) throw new Error(`source "${id}" already exists`);
            this.sources.set(id, new FakeGeoJSONSource(id, definition.data));
        }

        getSource(id: string): FakeGeoJSONSource | undefined {
            return this.sources.get(id);
        }

        addLayer(layer: unknown): void {
            this.layers.push(layer);
        }

        setStyle(style: unknown): void {
            this.styles.push(style);
            // A real `setStyle` takes every source and layer with it.
            this.sources.clear();
            this.layers.length = 0;
            queueMicrotask(() => this.emit('style.load', {}));
        }

        jumpTo(options: unknown): void {
            this.jumps.push(options);
        }

        queryRenderedFeatures(): unknown[] {
            return state.renderedFeatures;
        }

        remove(): void {
            this.removed = true;
        }
    }

    class FakeNavigationControl {
        constructor(readonly options: unknown) {}
    }

    class FakeScaleControl {
        constructor(readonly options: unknown) {}
    }

    return {state, FakeMap, FakeNavigationControl, FakeScaleControl};
});

vi.mock('maplibre-gl', () => ({
    Map: g.FakeMap,
    NavigationControl: g.FakeNavigationControl,
    ScaleControl: g.FakeScaleControl,
    setWorkerUrl: (url: unknown) => {
        g.state.workerUrls.push(url);
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

/** A second real row, far enough away that a wrong coordinate cannot pass. */
const other: SeatLocation = {
    lat: 48.7164,
    lon: 21.2611,
    radiusM: 4118,
    psc: '04001',
    precision: 'postal_code',
};

/** How many overlay layers the component puts on the base style. */
const SEAT_LAYER_COUNT = 3;

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

const mapAt = (index = 0) => {
    const instance = g.state.maps[index];
    if (!instance) throw new Error(`no map at index ${index}`);
    return instance;
};

/**
 * Let the fake map's `style.load` microtask run, without `waitFor`.
 *
 * `waitFor` is the right tool everywhere else, but under fake timers it depends
 * on the library recognising them, and a mis-detection there does not fail the
 * test -- it hangs it. The watchdog tests install fake timers, so they settle
 * explicitly instead.
 */
const settle = () =>
    act(async () => {
        await vi.advanceTimersByTimeAsync(0);
    });

/**
 * The map, once its style has landed and the seat layers are on it.
 *
 * Every test that inspects drawing starts here rather than right after `render`,
 * because the constructor returns before the style exists -- the same gap that
 * makes the mount-time seat a ref rather than a closure.
 */
const drawnMap = async () => {
    await waitFor(() => expect(g.state.maps).toHaveLength(1));
    await waitFor(() =>
        expect(mapAt().sources.get(SEAT_SOURCE)).toBeDefined(),
    );
    return mapAt();
};

const styleName = (style: unknown) => (style as StyleSpecification).name;

/**
 * Degrees of latitude to metres, at Slovakia's latitude. Independent of
 * `geometry.ts` on purpose: this is the measurement that catches a ring built
 * with the wrong radius, so it must not reuse the code that built it.
 */
const METRES_PER_DEGREE_LAT = 111132;

/** North-south extent of the drawn ring, in metres. */
const ringHeightM = (data: unknown) => {
    const ring = ((data as FeatureCollection).features[0].geometry as Polygon)
        .coordinates[0];
    const lats = ring.map(([, lat]) => lat);
    return (Math.max(...lats) - Math.min(...lats)) * METRES_PER_DEGREE_LAT;
};

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
        g.state.renderedFeatures = [{}];
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('reads its tiles from the TileJSON document, never from a tile template', () => {
        // The single most important line in this file. OpenFreeMap's *unversioned*
        // template -- `.../planet/{z}/{x}/{y}.pbf`, the one nearly every tutorial
        // shows -- answers HTTP 200 with a zero-byte body and an
        // `x-ofm-debug: empty tile` header, for every tile, so a style built on it
        // draws a blank canvas and logs nothing at all. The working path is a
        // versioned one, and it is the versioned path the TileJSON advertises, so
        // the source has to be the document. A `tiles` array here would be that
        // mistake.
        draw();

        const style = mapAt().options.style as StyleSpecification;
        const source = style.sources[TILES_SOURCE] as {
            type: string;
            url?: string;
            tiles?: unknown;
        };

        expect(source.type).toBe('vector');
        expect(source.url).toBe(TILEJSON_URL);
        expect(source.tiles).toBeUndefined();
    });

    it('draws without a credential of any kind', () => {
        // The reason this component stopped being a Google one: no key, no Map
        // ID, no account, no card. Asserted rather than assumed, because a
        // reintroduced credential is exactly the kind of thing that arrives
        // quietly in a diff.
        draw();

        const options = mapAt().options;
        for (const credential of ['apiKey', 'key', 'mapId', 'authOptions']) {
            expect(options).not.toHaveProperty(credential);
        }
    });

    it('centres on the seat and frames it by the radius it was given', async () => {
        draw();
        await drawnMap();

        // Longitude first: MapLibre takes `[lng, lat]`, and getting that backwards
        // draws perfectly and puts Bratislava in the Indian Ocean.
        expect(mapAt().options.center).toEqual([17.14051, 48.14748]);
        expect(mapAt().options.zoom).toBe(14);
    });

    it('does not let the map capture the page scroll', () => {
        draw();

        expect(mapAt().options.scrollZoom).toBe(false);
    });

    it('turns off the gestures that would spin the map under the reader', () => {
        draw();

        expect(mapAt().options.dragRotate).toBe(false);
        expect(mapAt().options.pitchWithRotate).toBe(false);
        expect(mapAt().options.renderWorldCopies).toBe(false);
    });

    it('draws the ring at the measured radius, not at a guessed one', async () => {
        // The drawn circle *is* the claim about precision, so it has to be the
        // stored radius. Measured north-to-south in metres, from the geometry
        // itself, so a ring built from the wrong number cannot pass.
        draw();
        const instance = await drawnMap();

        const data = instance.sources.get(SEAT_SOURCE)?.data;
        expect(ringHeightM(data)).toBeCloseTo(2 * 737, -2);
    });

    it('puts the credits on the map as links, visible rather than collapsed', async () => {
        // A licence obligation, not decoration: OpenStreetMap's attribution
        // guidelines ask for the credit to be readable by anyone looking at the
        // map, and OpenFreeMap and OpenMapTiles require their own.
        draw();

        expect(
            screen.getByRole('link', {name: 'OpenFreeMap'}),
        ).toHaveAttribute('href', 'https://openfreemap.org');
        expect(
            screen.getByRole('link', {name: '© OpenMapTiles'}),
        ).toHaveAttribute('href', 'https://www.openmaptiles.org/');
        expect(
            screen.getByRole('link', {name: 'Data from OpenStreetMap'}),
        ).toHaveAttribute('href', 'https://www.openstreetmap.org/copyright');
    });

    it('re-dresses the live map on a theme change instead of building another', async () => {
        // The improvement over Google, and worth asserting: `colorScheme` was an
        // initialization-only option there, so following a toggle meant a second
        // map -- and a second billed load. `setStyle` keeps the camera, so the
        // reader stays where they were looking.
        drawWithToggle();
        const instance = await drawnMap();
        expect(styleName(instance.options.style)).toBe('CistaFirma light');

        fireEvent.click(screen.getByRole('button', {name: 'Prepnúť tému'}));

        await waitFor(() => expect(instance.styles).toHaveLength(1));
        expect(styleName(instance.styles[0])).toBe('CistaFirma dark');
        expect(g.state.maps).toHaveLength(1);
    });

    it('puts the seat back after a re-dress, which drops every source with the style', async () => {
        // `setStyle` clears the sources and layers the previous style carried, so
        // a handler that only ran at mount would leave a correctly themed map with
        // no circle on it -- and no error anywhere.
        drawWithToggle();
        const instance = await drawnMap();

        fireEvent.click(screen.getByRole('button', {name: 'Prepnúť tému'}));

        await waitFor(() =>
            expect(instance.sources.get(SEAT_SOURCE)).toBeDefined(),
        );
        expect(instance.layers).toHaveLength(SEAT_LAYER_COUNT);
        expect(ringHeightM(instance.sources.get(SEAT_SOURCE)?.data)).toBeCloseTo(
            2 * 737,
            -2,
        );
    });

    it('lets the map go on unmount instead of leaving it alive', async () => {
        // The card unmounts once per company profile read, so a teardown that
        // skipped this would leave one live map -- listeners and WebGL context
        // included -- behind every profile the reader opens.
        const {unmount} = draw();
        const instance = await drawnMap();

        unmount();

        expect(instance.removed).toBe(true);
    });

    it('moves the drawn map to a new seat instead of rebuilding it', async () => {
        const {rerender} = draw();
        const instance = await drawnMap();

        rerender(
            <ThemeProvider>
                <SeatMap seat={other} />
            </ThemeProvider>,
        );

        await waitFor(() => expect(instance.jumps).toHaveLength(1));
        expect(instance.jumps[0]).toEqual({center: [21.2611, 48.7164], zoom: 11});
        expect(g.state.maps).toHaveLength(1);

        const source = instance.sources.get(SEAT_SOURCE);
        expect(source?.setDataCalls).toHaveLength(1);
        expect(ringHeightM(source?.data)).toBeCloseTo(2 * 4118, -2);
    });

    it('draws the newest seat when it changes before the style has landed', async () => {
        // The map is created a network round-trip before its style exists. Reading
        // the seat from the mount closure would draw the *previous* company and
        // leave no later effect to correct it, since the seat-change effect bails
        // while no seat layers exist yet.
        const {rerender} = draw();
        rerender(
            <ThemeProvider>
                <SeatMap seat={other} />
            </ThemeProvider>,
        );

        const instance = await drawnMap();

        expect(ringHeightM(instance.sources.get(SEAT_SOURCE)?.data)).toBeCloseTo(
            2 * 4118,
            -2,
        );
    });

    it('says so when the tiles never arrive', async () => {
        // Eight seconds of blank canvas is indistinguishable from a slow network,
        // so the watchdog names the outcome instead. The reader is scrolling a
        // long page and would otherwise sit looking at it.
        vi.useFakeTimers();
        draw();
        await settle();
        expect(mapAt().sources.get(SEAT_SOURCE)).toBeDefined();

        await act(async () => {
            await vi.advanceTimersByTimeAsync(9000);
        });

        expect(screen.getByText(/dlaždice sa nepodarilo stiahnuť/)).toBeInTheDocument();
        // The message takes the container away from the map and nothing re-runs
        // the effect when it does, so the map is released here or it outlives its
        // own box.
        expect(mapAt().removed).toBe(true);
    });

    it('says so when the tiles arrive empty, which is the failure that logs nothing', async () => {
        // The measured trap: a 200 response, a zero-byte body, no console error.
        // The source reports itself loaded, so "did anything arrive" is not the
        // question -- the question is whether the viewport holds a single
        // feature, and for a Slovak PSČ at zoom 10 or closer it always does.
        //
        // Which is why this is the *rendered* features that decide it. The call
        // that reads the source instead answers 0 on a map that is visibly
        // drawing, so a guard built on it fires on every healthy map -- the bug
        // this fake now makes unrunnable by answering only the honest question.
        vi.useFakeTimers();
        g.state.renderedFeatures = [];
        draw();
        await settle();

        await act(async () => {
            const instance = mapAt();
            instance.emit('sourcedata', {
                sourceId: TILES_SOURCE,
                isSourceLoaded: true,
            });
            await vi.advanceTimersByTimeAsync(9000);
        });

        expect(screen.getByText(/Dlaždice prišli prázdne/)).toBeInTheDocument();
    });

    it('does not cry wolf when the tiles do arrive', async () => {
        vi.useFakeTimers();
        draw();
        await settle();

        await act(async () => {
            mapAt().emit('sourcedata', {
                sourceId: TILES_SOURCE,
                isSourceLoaded: true,
            });
            await vi.advanceTimersByTimeAsync(9000);
        });

        expect(screen.queryByText(/Mapa sa nenačítala/)).not.toBeInTheDocument();
        expect(screen.queryByText(/prázdne/)).not.toBeInTheDocument();
        expect(mapAt().removed).toBe(false);
        expect(screen.getByRole('region')).toBeInTheDocument();
    });

    it('labels the region with the PSČ it is drawing', async () => {
        draw();

        expect(
            await screen.findByRole('region', {name: /PSČ 82109/}),
        ).toBeInTheDocument();
    });
});

describe('the MapLibre worker', () => {
    it('is pointed at a URL we supply, not left to MapLibre to guess', () => {
        // This one is a post-mortem rather than a speculation. MapLibre locates
        // its tile worker at `new URL('./maplibre-gl-worker.mjs', import.meta.url)`
        // -- a sibling of its own module -- and a bundler moves that module
        // without moving the worker. So the worker 404s, nothing parses a tile,
        // `sourcedata` never reports the source loaded, and the map holds a blank
        // canvas with an empty console: the failure that reaches the reader as
        // "the tiles could not be downloaded", blaming their connection for our
        // packaging. `setWorkerUrl` is the way out, and the module takes it on
        // import, before any `Map` exists.
        //
        // What this can check is that we hand MapLibre a URL of our own. That the
        // URL names a file the build actually emitted is the other half of the
        // fix, and `vite build` is what proves that one -- see the
        // `maplibre-gl-worker-*.js` asset in its output.
        expect(g.state.workerUrls).toHaveLength(1);
        expect(typeof g.state.workerUrls[0]).toBe('string');
        expect(g.state.workerUrls[0]).not.toBe('');
        expect(g.state.workerUrls[0]).not.toContain('.vite/deps');
    });
});
