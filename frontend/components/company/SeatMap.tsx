/**
 * The seat on an OpenStreetMap map: one glyph, shaped by how much we actually know.
 *
 * This drew Google Maps until now. Google cannot be used here without a billing
 * account and a card on file -- since March 2025 the free monthly calls still sit
 * behind a billing account, and the card-free demo key is licensed for evaluation
 * only -- so the renderer changed and the data changed with it. MapLibre GL is a
 * renderer and nothing else: it draws whatever style it is handed. The look that
 * used to come free with Google Maps is therefore ours to state, and it is stated
 * in `map/style.ts`. Neither the library nor the tiles want a key, an account, or
 * a card.
 *
 * What that bought, beyond the bill: Google's `colorScheme` was initialization-only,
 * so following the app's theme meant building a second map -- one more billable
 * load per toggle. MapLibre re-themes a live map with `setStyle()`, so the map is
 * now built once and re-dressed. And `gm_authFailure`, the global Google called
 * when it rejected a key, has no counterpart here because there is no key to
 * reject; the failure surface is now the tile fetch, which is what the watchdog
 * below actually watches.
 *
 * Three decisions survive the change unaltered, because they were about the data
 * rather than about Google:
 *
 * - **The circle is a claim, not a decoration.** It was drawn because the
 *   coordinate used to be a PSČ centroid -- a median 1 980 m from its own address
 *   points -- so the circle was the claim and the dot only marked what it was
 *   centred on. That is still true for a PSČ, and still true for a street. It is
 *   no longer true for the **78,6 %** of companies the MV SR register places on
 *   their own building: those get the point alone, because there is nothing left
 *   to be uncertain about. See `seatData`.
 * - **The zoom is computed from the radius**, not fixed. Our radii run 50 m (a
 *   street's floor, `MIN_STREET_RADIUS_M`) to 8 717 m (the widest PSČ); one zoom
 *   for all of them would either hide the circle or shrink it to a dot, and
 *   either way the reader would misread the precision.
 *   `fitBounds()` answers the same question, but it reads the container's layout,
 *   and this card can render before its box has been laid out -- so the
 *   arithmetic stays in our hands, and `zoomFor` is exported so it can be tested
 *   without a map at all. A building has no radius to fit, and `zoomFor` clamps
 *   it to the closest zoom, which is what a doorstep wants.
 * - **`scrollZoom` off.** The card sits inside a long page, and a map that
 *   captures the wheel traps the reader mid-scroll.
 *
 * One thing did not survive: Google's `Circle` took metres and drew the ring
 * itself. MapLibre has no metre-radius primitive -- a `circle` layer draws in
 * pixels, which would mean something different on every screen and at every zoom
 * -- so the ring is geometry now, built in `map/geometry.ts` and filled like any
 * other polygon. That is the better arrangement of the two: the arithmetic is
 * testable without a map, and one ring is both what the renderer fills and what
 * the tests measure.
 *
 * A note for whoever writes the privacy notice: drawing this map sends the
 * reader's IP address and the viewed coordinates to `tiles.openfreemap.org`, a
 * third party, exactly as Google's tiles went to Google. Nothing else leaves the
 * page -- there is no key, no cookie and no identifier attached -- but the request
 * itself is a disclosure, and it should be named as one.
 */

import React, { useEffect, useRef, useState } from 'react';
import { Map as MapLibreMap, NavigationControl, ScaleControl, setWorkerUrl } from 'maplibre-gl';
import type { GeoJSONSource } from 'maplibre-gl';
import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec';
import type { FeatureCollection } from 'geojson';
import 'maplibre-gl/dist/maplibre-gl.css';

// MapLibre parses every tile in a worker, and finds that worker by resolving
// `new URL('./maplibre-gl-worker.mjs', import.meta.url)` -- a sibling of its own
// module. A bundler breaks that assumption, and it breaks it *silently*: Vite
// pre-bundles the library to `node_modules/.vite/deps/maplibre-gl.js` in dev and
// emits it as `assets/SeatMap-*.js` in a build, and neither directory has ever
// contained the worker, so the request 404s, no tile is parsed, `sourcedata`
// never reports `isSourceLoaded`, and the map sits on a blank canvas with
// nothing in the console. Measured on 6.9.0: 2 frames for ever and
// `areTilesLoaded() === false`, in dev and against `dist/` alike -- while the
// *same* library served from its own `dist/` path renders normally. `?worker&url`
// is the fix: Vite builds the worker as an entry of its own (bundling the
// `maplibre-gl-shared.mjs` it imports) and returns a URL that exists in both
// environments, and `setWorkerUrl` tells MapLibre to use it instead of guessing.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

// At module scope, so it is set before any `Map` is constructed -- the worker
// pool reads this once, on the first map, and nothing later can correct it.
setWorkerUrl(workerUrl);

import type { SeatLocation } from '../../types';
import { useTheme } from '../../context/ThemeContext';
import { circlePolygon } from '../../map/geometry';
import { ATTRIBUTION, TILES_SOURCE, mapStyle } from '../../map/style';

/** Keep the circle inside roughly this many pixels of the map's centre. */
const RADIUS_PIXELS = 90;
/** Metres per pixel at zoom 0 on the equator; halved at every zoom step. */
const EQUATOR_METRES_PER_PIXEL = 156543.03392;
const MIN_ZOOM = 7;
const MAX_ZOOM = 16;

const BRAND = '#2563eb';

/**
 * What the map is, said to a screen reader in the same terms the glyph is drawn in.
 *
 * Naming only the PSČ would describe the *address* rather than the map, and for
 * four fifths of companies it would also be the weaker claim than the one drawn:
 * a reader told "okolia sídla" over a building's own doorstep is being told the
 * map is vaguer than it is, which is the same failure as the circle was.
 */
const SEAT_LABEL: Record<SeatLocation['precision'], string> = {
    building: 'Mapa sídla — presná adresa budovy',
    street: 'Mapa sídla — ulica, číslo budovy známe nie je',
    postal_code: 'Mapa okolia sídla — známe je len PSČ',
};

/** How long the tiles get, once a style is on the map, before we say so. */
const TILE_TIMEOUT_MS = 8000;

/**
 * Our overlay on the base style. Named with a prefix so it cannot collide, and
 * exported so the tests name the same source the component does rather than a
 * copy of the string that can drift.
 */
export const SEAT_SOURCE = 'seat-location';

// Two failures, two sentences, and each names what was actually observed. A map
// that renders as a grey box, or as nothing at all, is the failure mode this
// project keeps paying for -- and the second one below is specific: OpenFreeMap's
// *unversioned* tile template answers HTTP 200 with a zero-byte body and an
// `x-ofm-debug: empty tile` header, so a style pointed at it draws a blank canvas
// and logs nothing at all. That is why `NO_DATA` exists as a separate sentence --
// and why it is judged by what reached the screen rather than by what the source
// holds, since only the first of those is true when the map is drawing.
const LOAD_FAILED =
    'Mapu sa nepodarilo spustiť — knižnica MapLibre sa nenačítala (chýba WebGL?).';
const NO_TILES =
    'Mapa sa nenačítala — dlaždice sa nepodarilo stiahnuť. Skontrolujte pripojenie a obnovte stránku.';
const NO_DATA =
    'Dlaždice prišli prázdne. To je chyba zdroja máp, nie vášho pripojenia — dajte nám o tom vedieť.';

/**
 * The zoom that puts `seat.radiusM` at about `RADIUS_PIXELS` from the centre.
 *
 * Web Mercator's scale is fixed by latitude, so the ground resolution at zoom 0
 * is the equatorial figure times the cosine of the latitude -- which is the whole
 * of the projection's distortion, and the only correction this needs.
 */
export const zoomFor = (seat: SeatLocation) => {
    const metresPerPixelAtZero =
        EQUATOR_METRES_PER_PIXEL * Math.cos((seat.lat * Math.PI) / 180);
    const ideal = Math.log2(
        (metresPerPixelAtZero * RADIUS_PIXELS) / Math.max(seat.radiusM, 1),
    );
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(ideal)));
};

/**
 * What a drawn map depends on: the identity of the seat, not the object.
 *
 * `precision` is in the key because it decides the *shape*. Leaving it out would
 * make a re-match that moved a company from a street to its own building -- same
 * point, 0 m instead of a street's radius -- a no-op on a map already drawn.
 */
const keyOf = (seat: SeatLocation) =>
    `${seat.precision}:${seat.psc}:${seat.lat}:${seat.lon}:${seat.radiusM}`;

/**
 * The one glyph, whose shape is the claim: a bare point, or a point inside a ring.
 *
 * `precision` decides, and it is the backend's answer rather than a threshold on
 * `radiusM` invented here. A `building` really is one point -- the register's own
 * address point for that house number -- so it is drawn as a point and **nothing
 * else**; a ring around it would be the decoration this map was asked to stop
 * drawing. `street` and `postal_code` are areas, so they keep the ring, and the
 * radius is what separates them: a street's 90th-percentile spread is tens to
 * hundreds of metres (floored at 50 m so one known point cannot be drawn as a
 * pin), a PSČ's is 270 m to 8 717 m.
 *
 * Filtering the polygon out here rather than relying on `radiusM: 0` to draw a
 * degenerate ring is deliberate. `circlePolygon(centre, 0)` produces a valid but
 * zero-area polygon, which MapLibre *usually* renders as nothing -- and "usually"
 * is not a property worth depending on for a line layer with round joins.
 *
 * Longitude first: GeoJSON positions are `[x, y]`, and getting that backwards
 * puts Slovak companies in the Indian Ocean -- a mistake that draws perfectly and
 * is therefore worth naming here.
 */
const seatData = (seat: SeatLocation): FeatureCollection => {
    const features: FeatureCollection['features'] = [];

    if (seat.precision !== 'building') {
        features.push(circlePolygon({ lat: seat.lat, lon: seat.lon }, seat.radiusM));
    }

    features.push({
        type: 'Feature',
        properties: {},
        geometry: { type: 'Point', coordinates: [seat.lon, seat.lat] },
    });

    return { type: 'FeatureCollection', features };
};

/**
 * Three layers, no filters: each type draws only the geometry it can draw, so the
 * `fill` and the `line` take the polygon and the `circle` takes the point without
 * being told which is which.
 *
 * Added last, so they land on top of the base style -- the seat is the subject of
 * this map, not a feature of it.
 */
const SEAT_LAYERS: LayerSpecification[] = [
    {
        id: `${SEAT_SOURCE}-fill`,
        type: 'fill',
        source: SEAT_SOURCE,
        paint: { 'fill-color': BRAND, 'fill-opacity': 0.12 },
    },
    {
        id: `${SEAT_SOURCE}-outline`,
        type: 'line',
        source: SEAT_SOURCE,
        layout: { 'line-join': 'round' },
        paint: { 'line-color': BRAND, 'line-width': 2, 'line-opacity': 0.9 },
    },
    {
        // Pixels, and rightly so for a dot: a marker that grew with the zoom
        // would read as something on the ground rather than as a pointer at it.
        id: `${SEAT_SOURCE}-dot`,
        type: 'circle',
        source: SEAT_SOURCE,
        paint: {
            'circle-radius': 5,
            'circle-color': BRAND,
            'circle-stroke-color': '#ffffff',
            'circle-stroke-width': 2,
        },
    },
];

/**
 * The ids of our own layers, so a question about the *tiles* can exclude them.
 *
 * Derived from `SEAT_LAYERS` rather than written out again: the watchdog below
 * asks the map what reached the screen, and the answer has to be about the base
 * style rather than about the dot we drew on top of it.
 */
const SEAT_LAYER_IDS = new Set(SEAT_LAYERS.map((layer) => layer.id));

const message = (text: string) => (
    <div className="flex h-full items-center justify-center bg-gray-50 px-4 text-center text-xs text-gray-500 dark:bg-slate-900 dark:text-gray-400">
        {text}
    </div>
);

interface SeatMapProps {
    seat: SeatLocation;
}

export const SeatMap: React.FC<SeatMapProps> = ({ seat }) => {
    const container = useRef<HTMLDivElement>(null);
    const map = useRef<MapLibreMap | null>(null);
    /** What the drawn map currently shows, so a new seat is a move, not a rebuild. */
    const drawn = useRef<string>('');
    /** False while a style is loading; the seat layers only exist once it has. */
    const ready = useRef(false);
    const [failed, setFailed] = useState<string | null>(null);
    const { isDark } = useTheme();

    /**
     * The newest seat and the reader's current theme, readable from an async
     * continuation.
     *
     * Assigned during render on purpose. The map's style arrives a network
     * round-trip after mount, and by then the mount-time closure may be stale --
     * a parent that kept this card mounted would get a map drawn for the previous
     * firm's seat, with no later effect to fix it. An effect-assigned ref would
     * not close the gap either, since a promise continuation can run before the
     * effect does.
     */
    const latest = useRef(seat);
    latest.current = seat;
    const theme = useRef(isDark);
    theme.current = isDark;
    /** The theme the map's current style was built from. */
    const styled = useRef(isDark);

    useEffect(() => {
        const node = container.current;
        if (!node) return;

        let cancelled = false;
        let instance: MapLibreMap;

        try {
            instance = new MapLibreMap({
                container: node,
                style: mapStyle(theme.current),
                center: [latest.current.lon, latest.current.lat],
                zoom: zoomFor(latest.current),
                // The reader is scrolling a long page and reading a company
                // profile; every one of these either traps the page or competes
                // with the card's own content.
                scrollZoom: false,
                dragRotate: false,
                pitchWithRotate: false,
                touchPitch: false,
                keyboard: false,
                // One world, not an endless ribbon of repeats.
                renderWorldCopies: false,
                // The credit is drawn below as React links instead. MapLibre's
                // own control renders the source's attribution HTML string, and a
                // licence notice is not a place to hand a remote document the
                // page.
                attributionControl: false,
                // No Map ID, no key, no billing account -- which is the point.
            });
        } catch {
            setFailed(LOAD_FAILED);
            return;
        }

        map.current = instance;
        ready.current = false;
        drawn.current = '';

        // Both clustered bottom-right, where Google puts them; the attribution
        // takes the left, so nothing sits on top of anything.
        instance.addControl(
            new ScaleControl({ unit: 'metric', maxWidth: 80 }),
            'bottom-right',
        );
        instance.addControl(
            new NavigationControl({ showCompass: false }),
            'bottom-right',
        );

        let watchdog: ReturnType<typeof setTimeout> | undefined;
        let inspected = false;
        /** Whether the source ever reported itself loaded, tiles or no tiles. */
        let sourceReady = false;

        instance.on('sourcedata', (event) => {
            if (event.sourceId === TILES_SOURCE && event.isSourceLoaded) {
                sourceReady = true;
            }
        });

        /**
         * Let the map go, once, whichever way it ends.
         *
         * The guard is what makes it once: the watchdog can give up while the
         * component is still mounted, and React's cleanup then runs on top of it.
         * Forgetting that is how a WebGL context is leaked per failed map.
         */
        const dispose = () => {
            if (map.current !== instance) return;
            map.current = null;
            ready.current = false;
            drawn.current = '';
            instance.remove();
        };

        const giveUp = (text: string) => {
            dispose();
            setFailed(text);
        };

        instance.on('style.load', () => {
            if (cancelled || map.current !== instance) return;

            // Idempotent: `style.load` fires again on every `setStyle`, and a
            // second `addSource` for a name that already exists throws.
            if (!instance.getSource(SEAT_SOURCE)) {
                instance.addSource(SEAT_SOURCE, {
                    type: 'geojson',
                    data: seatData(latest.current),
                });
                for (const layer of SEAT_LAYERS) instance.addLayer(layer);
            } else {
                (instance.getSource(SEAT_SOURCE) as GeoJSONSource).setData(
                    seatData(latest.current),
                );
            }

            drawn.current = keyOf(latest.current);
            ready.current = true;

            // Re-armed per style, and that is the point: this is a watchdog on
            // the tiles of the style currently on the map, not on the first ever.
            clearTimeout(watchdog);
            inspected = false;
            watchdog = setTimeout(() => {
                if (cancelled || inspected || map.current !== instance) return;
                inspected = true;
                if (!sourceReady) {
                    giveUp(NO_TILES);
                    return;
                }
                // The source loaded but the base style drew nothing. Our seat is
                // always a real Slovak PSČ at zoom 10 or closer, where every tile
                // carries roads, so an empty screen is the empty-tile signature
                // rather than a legitimately blank patch of map.
                //
                // It has to be `queryRenderedFeatures` that answers this, and the
                // distinction is not cosmetic. `querySourceFeatures` reads the
                // source rather than the screen, and on a map that is visibly
                // drawing roads and water it returns **0** -- measured, twice:
                // 0 against 240 rendered features on the same frame. So the guard
                // as first written condemned every healthy map and blamed the tile
                // source for it. The question here is "did anything reach the
                // screen", and only this call asks it.
                //
                // Scoped to the style's own layers, and that part is the fix for a
                // subtler version of the same mistake: with no `layers` option the
                // call queries *every* source in the viewport, including the seat
                // overlay added a few lines above, whose dot sits at the centre.
                // A map drawing our dot and nothing else therefore answered
                // "1 feature" -- so the exact failure this sentence was written
                // for (HTTP 200, zero-byte body, `x-ofm-debug: empty tile`)
                // reached the reader as a blank canvas holding one blue dot and
                // no message. Excluding our own layers leaves the question the
                // right one: did the *tiles* draw?
                let features: unknown[] = [];
                try {
                    const style = instance.getStyle();
                    const baseLayers = (style?.layers ?? [])
                        .map((layer) => layer.id)
                        .filter((id) => !SEAT_LAYER_IDS.has(id));
                    // Silence here, not `NO_DATA`, and the difference is which
                    // claim the message makes. `NO_DATA` says the *tiles* came
                    // back empty; a layer-less style says nothing about the tiles
                    // at all, so using it would blame the source for something it
                    // did not do -- the same mistake the paragraph above records
                    // `querySourceFeatures` making. The realistic way to read an
                    // empty list here is a `setStyle` in flight (the theme
                    // toggle), where the next style re-arms this watchdog anyway
                    // and a message would only flash over a map that is fine.
                    if (!baseLayers.length) return;
                    features = instance.queryRenderedFeatures(undefined, {
                        layers: baseLayers,
                    });
                } catch {
                    // The style went away mid-check; nothing to report.
                    return;
                }
                if (features.length === 0) giveUp(NO_DATA);
            }, TILE_TIMEOUT_MS);
        });

        return () => {
            cancelled = true;
            clearTimeout(watchdog);
            dispose();
        };
        // Mount only. The theme is handled by `setStyle` below, and the seat by
        // `setData` -- rebuilding the map for either would throw away the tiles
        // already loaded and flash the card for no reason.
    }, []);

    // Re-dress rather than rebuild. `setStyle` keeps the camera, so the reader
    // stays looking at the same place across a theme toggle.
    useEffect(() => {
        const instance = map.current;
        if (!instance || styled.current === isDark) return;
        styled.current = isDark;
        ready.current = false;
        instance.setStyle(mapStyle(isDark));
    }, [isDark]);

    // Move in place when the seat changes, for a parent that keeps the card
    // mounted. Bails while a style is loading: there are no seat layers to move
    // yet, and the `style.load` handler above draws from `latest`, which is
    // already this seat.
    useEffect(() => {
        const instance = map.current;
        if (!instance || !ready.current) return;
        if (drawn.current === keyOf(seat)) return;

        instance.jumpTo({ center: [seat.lon, seat.lat], zoom: zoomFor(seat) });
        const source = instance.getSource(SEAT_SOURCE) as GeoJSONSource | undefined;
        source?.setData(seatData(seat));
        drawn.current = keyOf(seat);
    }, [seat]);

    if (failed) return message(failed);

    return (
        <div className="relative h-full w-full">
            <div
                ref={container}
                role="region"
                aria-label={`${SEAT_LABEL[seat.precision]}${seat.psc ? `, PSČ ${seat.psc}` : ''}`}
                className="h-full w-full"
            />
            {/*
                The three credits the licences require, as React links rather than
                as MapLibre's attribution control. Visible rather than collapsed
                behind a toggle: OpenStreetMap's attribution guidelines ask for the
                credit to be readable by anyone looking at the map.
            */}
            <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-wrap items-center gap-x-1 px-1 pb-0.5 text-[10px] leading-tight text-gray-600 dark:text-gray-400">
                <span className="pointer-events-auto rounded-sm bg-white/75 px-1 backdrop-blur-sm dark:bg-slate-900/70">
                    {ATTRIBUTION.map((credit, index) => (
                        <React.Fragment key={credit.href}>
                            {index > 0 && <span aria-hidden="true"> · </span>}
                            <a
                                href={credit.href}
                                target="_blank"
                                rel="noreferrer noopener"
                                className="hover:underline"
                            >
                                {credit.label}
                            </a>
                        </React.Fragment>
                    ))}
                </span>
            </div>
        </div>
    );
};
