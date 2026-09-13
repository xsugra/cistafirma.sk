/**
 * The seat on a Google map: a centroid, and the circle that stops it lying.
 *
 * Loaded lazily (`SeatLocationCard`) because the Maps JavaScript API is a couple
 * of hundred kilobytes that only this one card needs -- and because Google bills
 * per map load, so the script must not be pulled in by pages that never draw a
 * map. Google's own guidance is to defer creating a map until it is needed; the
 * lazy import *is* that deferral, and no Google script is requested at all until
 * a key has been found.
 *
 * Four decisions live here rather than in the card:
 *
 * - **A circle, centred on a dot.** The coordinate is a PSČ centroid, a median
 *   1 980 m from its own address points, so the circle is the claim and the dot
 *   only marks what it is centred on. That is also why the centre is a plain dot
 *   and *not* the default `AdvancedMarkerElement` pin: Google's pin is a
 *   teardrop, and a teardrop's point names a doorstep. We do not have one.
 * - **The zoom is computed from the radius**, not fixed. Our radii run 270 m to
 *   8 717 m; one zoom for all of them would either hide the circle or shrink it
 *   to a dot, and either way the reader would misread the precision.
 *   `map.fitBounds()` answers the same question, but it reads the container's
 *   layout, and this card can render before its box has been laid out -- so the
 *   arithmetic stays in our hands, and `zoomFor` is exported so it can be tested
 *   without a map at all.
 * - **`scrollwheel` off.** The card sits inside a long page, and a map that
 *   captures the wheel traps the reader mid-scroll.
 * - **The map follows the app's theme, not the operating system's.** `colorScheme`
 *   is the supported way to do that, and it is why a Map ID is not optional. It
 *   is also *initialization-only*: Google documents it as settable when the map
 *   is created and ignored afterwards, so a live map cannot be re-themed, and
 *   following the app's theme means building a second map when the reader
 *   toggles. That is one more billable load per toggle, which is what it costs
 *   not to leave a light rectangle sitting inside a dark page.
 *
 * Two values come from the Google Cloud console rather than from this file, and
 * neither has a default that works in production:
 *
 * - `VITE_GOOGLE_MAPS_API_KEY` -- without it there is no map at all, and this
 *   component says so instead of drawing an empty box.
 * - `VITE_GOOGLE_MAPS_MAP_ID` -- advanced markers *and* the dark colour scheme
 *   are vector-only features. `DEMO_MAP_ID`, Google's own sample value and the
 *   default here, is for development; a production Map ID has to be created in
 *   the console, or dark mode quietly does nothing.
 */

import React, { useEffect, useRef, useState } from 'react';
import { importLibrary, setOptions } from '@googlemaps/js-api-loader';
import type { SeatLocation } from '../../types';
import { useTheme } from '../../context/ThemeContext';

/** Keep the circle inside roughly this many pixels of the map's centre. */
const RADIUS_PIXELS = 90;
/** Metres per pixel at zoom 0 on the equator; halved at every zoom step. */
const EQUATOR_METRES_PER_PIXEL = 156543.03392;
const MIN_ZOOM = 7;
const MAX_ZOOM = 16;

const BRAND = '#2563eb';
const DEMO_MAP_ID = 'DEMO_MAP_ID';

// Three failures, three sentences. A map that renders as a grey box, or as
// nothing at all, is the failure mode this project keeps paying for; each of
// these names what is wrong so that the reader can tell us.
const MISSING_KEY =
    'Mapa sa nezobrazuje: nie je nastavený VITE_GOOGLE_MAPS_API_KEY (Google Maps).';
const LOAD_FAILED = 'Mapu sa nepodarilo načítať — skript Google Maps sa nenačítal.';
const KEY_REJECTED =
    'Google Maps kľúč odmietli: neplatný kľúč, chýbajúca fakturácia alebo nepovolený referrer.';

/**
 * Read when the component renders, not when the module is imported.
 *
 * Vite replaces `import.meta.env.VITE_*` with a literal at build time either
 * way, so this costs nothing in the bundle -- and it lets a test stub the key
 * and render, rather than resetting the module registry (which would hand the
 * component a second copy of React *and* of the theme context, so `useTheme`
 * would throw).
 */
const apiKey = () => (import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? '').trim();
const mapId = () =>
    (import.meta.env.VITE_GOOGLE_MAPS_MAP_ID ?? '').trim() || DEMO_MAP_ID;

export const zoomFor = (seat: SeatLocation) => {
    const metresPerPixelAtZero =
        EQUATOR_METRES_PER_PIXEL * Math.cos((seat.lat * Math.PI) / 180);
    const ideal = Math.log2(
        (metresPerPixelAtZero * RADIUS_PIXELS) / Math.max(seat.radiusM, 1),
    );
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(ideal)));
};

/**
 * The one place the Google script is configured, and it runs once.
 *
 * Version 2 of the loader is a pair of module functions, not a `Loader` object,
 * and it does the singleton work itself: the first `importLibrary` starts the
 * script and every later call returns the library already in hand. `setOptions`
 * is the half that is *not* repeatable -- it has to run before the first library
 * loads and throws if it runs after -- so it is guarded here rather than called
 * on every mount. Under React's development double-mount, that guard is also
 * what stops the second mount from throwing.
 *
 * `language`/`region` are pinned rather than left to the browser: this is a
 * Slovak register read by Slovak users, and a map whose labels arrive in
 * whatever the visitor's browser happens to ask for renders differently for two
 * people looking at the same company.
 */
let configured = false;
const loadLibraries = async () => {
    if (!configured) {
        setOptions({
            key: apiKey(),
            v: 'weekly',
            language: 'sk',
            region: 'SK',
        });
        configured = true;
    }
    return Promise.all([importLibrary('maps'), importLibrary('marker')]);
};

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
    const map = useRef<google.maps.Map | null>(null);
    const circle = useRef<google.maps.Circle | null>(null);
    const marker = useRef<google.maps.marker.AdvancedMarkerElement | null>(null);
    /** What the drawn map currently shows, so a new seat is a move, not a reload. */
    const drawn = useRef<string>('');
    const [failed, setFailed] = useState<string | null>(() =>
        apiKey() ? null : MISSING_KEY,
    );
    const { isDark } = useTheme();

    /**
     * The newest seat, readable from the async continuation below.
     *
     * Assigned during render on purpose. The map is created a network round-trip
     * after mount, and the effect that handles a *change* of seat bails out while
     * `map.current` is still null -- so without this, a parent that kept this card
     * mounted would get a map drawn from the mount-time closure: the previous
     * firm's seat, and no later effect to fix it. An effect-assigned ref would not
     * close that gap either, since a promise continuation can run before the
     * effect does. (The theme needs no such treatment: it is a dependency of the
     * effect below, so its closure is always the current one.)
     */
    const latest = useRef(seat);
    latest.current = seat;

    useEffect(() => {
        if (!apiKey()) return;

        let cancelled = false;

        /**
         * Everything Google offers for undoing a map, and the only teardown there
         * is: the API has no `destroy()`, so detaching the overlays and emptying
         * the container is the whole of it. Skipping it leaves a live map -- its
         * listeners, and the WebGL context that a Map ID always implies -- behind
         * every rebuild, and this card rebuilds on a theme change and unmounts
         * once per company profile.
         */
        const release = () => {
            if (marker.current) marker.current.map = null;
            circle.current?.setMap(null);
            map.current = null;
            circle.current = null;
            marker.current = null;
            drawn.current = '';
            container.current?.replaceChildren();
        };

        // Google reports an unusable key (invalid, unenabled, unbilled, wrong
        // referrer) by calling this global *after* the script has loaded
        // successfully -- so the loader's promise resolves and the map renders as
        // a grey box with a watermark in the corner. That is a silent failure
        // with extra steps, which is the failure mode this project keeps paying
        // for; the hook is Google's documented way to hear about it.
        const onAuthFailure = () => {
            if (cancelled) return;
            // The message below takes the container away from the map, and nothing
            // re-runs this effect when it does -- so what is already drawn has to
            // be let go here, not left to the unmount that may never come.
            release();
            setFailed(KEY_REJECTED);
        };
        (window as { gm_authFailure?: () => void }).gm_authFailure = onAuthFailure;

        void (async () => {
            try {
                const [{ Map, Circle }, { AdvancedMarkerElement }] =
                    await loadLibraries();
                if (cancelled || !container.current) return;

                const current = latest.current;
                const centre = { lat: current.lat, lng: current.lon };
                const instance = new Map(container.current, {
                    center: centre,
                    zoom: zoomFor(current),
                    mapId: mapId(),
                    // The app's theme is the reader's choice; 'FOLLOW_SYSTEM'
                    // would ignore a reader who picked light on a dark desktop.
                    // Read from this effect's own closure, which is why `isDark`
                    // is a dependency below: the option is initialization-only, so
                    // a theme change has to arrive as a new map or not at all.
                    colorScheme: isDark ? 'DARK' : 'LIGHT',
                    // The reader is scrolling a long page and reading a company
                    // profile; every one of these either traps the page or
                    // competes with the card's own content.
                    scrollwheel: false,
                    gestureHandling: 'cooperative',
                    clickableIcons: false,
                    mapTypeControl: false,
                    streetViewControl: false,
                    fullscreenControl: false,
                    zoomControl: true,
                });
                map.current = instance;

                circle.current = new Circle({
                    map: instance,
                    center: centre,
                    radius: current.radiusM,
                    strokeColor: BRAND,
                    strokeWeight: 2,
                    strokeOpacity: 0.9,
                    fillColor: BRAND,
                    fillOpacity: 0.12,
                    clickable: false,
                });

                // A dot, not Google's teardrop pin -- see the note at the top.
                const dot = document.createElement('div');
                dot.setAttribute('aria-hidden', 'true');
                dot.style.cssText = [
                    'width:10px',
                    'height:10px',
                    'border-radius:50%',
                    `background:${BRAND}`,
                    'border:2px solid #ffffff',
                    'box-shadow:0 0 0 1px rgba(0,0,0,.25)',
                ].join(';');

                marker.current = new AdvancedMarkerElement({
                    map: instance,
                    position: centre,
                    content: dot,
                    title: `Stred PSČ ${current.psc}`,
                });

                drawn.current = keyOf(current);
            } catch {
                // The script itself never arrived: offline, blocked, or the key
                // is missing the Maps JavaScript API in its own restrictions.
                if (!cancelled) setFailed(LOAD_FAILED);
            }
        })();

        return () => {
            cancelled = true;
            const global = window as { gm_authFailure?: () => void };
            if (global.gm_authFailure === onAuthFailure) {
                delete global.gm_authFailure;
            }
            release();
        };
        // Mount and theme. Moving to another *company* is handled below, so a
        // parent that keeps the card mounted moves the map instead of building --
        // and paying for -- a second one. Both of today's parents drop the card
        // before the next company's seat can arrive (`pages/Company.tsx` clears
        // the company while the new one loads, `pages/Profile.tsx` shows a
        // spinner), so in the app as it stands the map is built once per profile
        // read either way. The path stays because it is correct under reuse, not
        // because the current routing reaches it.
    }, [isDark]);

    // Redraw in place when the seat changes, for a parent that keeps the card
    // mounted. Bails while the map is being rebuilt, which is why `release()`
    // nulls `map.current`: the rebuild reads the seat from `latest` instead.
    useEffect(() => {
        const instance = map.current;
        if (!instance || drawn.current === keyOf(seat)) return;

        const centre = { lat: seat.lat, lng: seat.lon };
        instance.setCenter(centre);
        instance.setZoom(zoomFor(seat));
        circle.current?.setCenter(centre);
        circle.current?.setRadius(seat.radiusM);
        if (marker.current) {
            marker.current.position = centre;
            marker.current.title = `Stred PSČ ${seat.psc}`;
        }
        drawn.current = keyOf(seat);
    }, [seat]);

    if (failed) return message(failed);

    return (
        <div
            ref={container}
            role="region"
            aria-label={`Mapa okolia sídla, PSČ ${seat.psc}`}
            className="h-full w-full"
        />
    );
};

/** What a drawn map depends on: the identity of the seat, not the object. */
const keyOf = (seat: SeatLocation) => `${seat.psc}:${seat.lat}:${seat.lon}:${seat.radiusM}`;
