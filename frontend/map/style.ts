/**
 * Our own MapLibre style: OpenStreetMap data, drawn to read like Google Maps.
 *
 * Google's renderer came with its own cartography and no way to keep it without
 * a billing account. MapLibre is the renderer only -- it draws whatever style it
 * is handed -- so the look is now ours to state, and this file states it. The
 * palette below is deliberately Google's: its warm light grey ground, its
 * `#aadaff` water, its amber motorways, its `#242f3e` dark ground. Anyone who has
 * seen Google Maps should recognise the picture without being told.
 *
 * Three things about the data shape this file, and all three were measured by
 * decoding real tiles rather than recalled:
 *
 * - **`boundary` has no `class`.** It carries `admin_level` (2, 4, 6, 8). A
 *   filter on `class` -- the obvious guess -- would have matched nothing and
 *   drawn no borders at all, silently.
 * - **`building` has no `class` either.** It carries `render_height`,
 *   `render_min_height`, `colour`, `hide_3d`. Same trap.
 * - **`park`'s `class` is free text.** Real values include `Natura 2000`,
 *   `Prírodná rezervácia` and `Národná prírodná rezervácia`, so a `match` on a
 *   remembered vocabulary would have dropped Slovakia's protected areas while
 *   keeping the generic ones. All `park` features are drawn alike instead.
 *
 * A fourth fact is not a trap but a constraint: **vector tiles omit a field that
 * is empty for every feature in that tile**, so `ref` can be present in one tile
 * and absent in the next. Every filter below therefore treats a missing field as
 * "not this", which is what `['has', ...]` and a `null` comparison already do.
 *
 * No sprite is declared, because nothing here draws an icon: the seat marker is a
 * DOM element and every point of interest is a label. Glyphs are not optional --
 * a style with text and no `glyphs` draws no text at all -- and the fontstacks
 * named here are the three OpenFreeMap actually serves.
 */

import type {
    ExpressionSpecification,
    FilterSpecification,
    LayerSpecification,
    StyleSpecification,
} from '@maplibre/maplibre-gl-style-spec';

/** The one source. Its TileJSON is fetched at runtime; see `TILEJSON_URL`. */
export const TILES_SOURCE = 'openmaptiles';

/**
 * The TileJSON *document*, not a tile template.
 *
 * This matters more than it looks. The obvious template --
 * `.../planet/{z}/{x}/{y}.pbf` -- answers **HTTP 200 with an empty body** and a
 * `x-ofm-debug: empty tile` header, for every tile, so a map built on it renders
 * a blank canvas with nothing in the console to explain it. The working path is
 * a versioned one (`.../planet/20260906_080001_pt/{z}/{x}/{y}.pbf`, 558 kB for a
 * Bratislava z14 tile), and it is the versioned path that the TileJSON at this
 * URL advertises in its `tiles` array. Letting MapLibre read it from there means
 * we track OpenFreeMap's current build instead of pinning a build id that will
 * one day be pruned.
 */
export const TILEJSON_URL = 'https://tiles.openfreemap.org/planet';

/**
 * The TileJSON declares neither `glyphs` nor `sprite`, so the style must.
 * `{fontstack}` and `{range}` are MapLibre's placeholders, not ours.
 */
export const GLYPHS_URL =
    'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf';

/**
 * The credit three licences require, as data rather than as markup.
 *
 * OpenFreeMap's own TileJSON carries an equivalent string, but it arrives over
 * the network and nothing here would notice if it changed. Stating it ourselves
 * keeps a licence obligation in version control, and returning links rather than
 * an HTML string means the card renders them as React elements -- no
 * `dangerouslySetInnerHTML`, and no way for a remote document to inject markup
 * into the page.
 *
 * All three must be visible, not hidden behind a toggle: OpenStreetMap's
 * attribution guidelines ask for the credit to be readable by anyone looking at
 * the map.
 */
export const ATTRIBUTION: ReadonlyArray<{label: string; href: string}> = [
    {label: 'OpenFreeMap', href: 'https://openfreemap.org'},
    {label: '© OpenMapTiles', href: 'https://www.openmaptiles.org/'},
    {
        label: 'Data from OpenStreetMap',
        href: 'https://www.openstreetmap.org/copyright',
    },
];

const REGULAR = ['Noto Sans Regular'];
const BOLD = ['Noto Sans Bold'];
const ITALIC = ['Noto Sans Italic'];

/**
 * Slovak first, then whatever the tile happens to carry.
 *
 * OpenMapTiles ships `name:sk` on every layer that has names, so a Slovak
 * register read by Slovak users gets Slovak labels; `name` is the fallback for
 * the features nobody has translated, which would otherwise be drawn nameless.
 */
const NAME: ExpressionSpecification = [
    'coalesce',
    ['get', 'name:sk'],
    ['get', 'name'],
];

/**
 * `['interpolate', ['linear'], ['zoom'], z0, v0, z1, v1, ...]`.
 *
 * The one place in this file that needs a cast. The spec's expression type is a
 * union of tuples wide enough that a *built* array cannot be inferred into it,
 * though a literal can. One cast inside one helper beats a cast at every call
 * site -- and the real check on the output is `style.test.ts`, which runs the
 * style spec's own validator over whatever this module returns. That validator
 * checks expression arity, property names and value ranges far more strictly
 * than `tsc` would.
 */
const ramp = (
    stops: ReadonlyArray<readonly [number, number]>,
): ExpressionSpecification =>
    [
        'interpolate',
        ['linear'],
        ['zoom'],
        ...stops.flat(),
    ] as unknown as ExpressionSpecification;

/** `['match', ['get', 'class'], [...values], true, false]`. */
const classIn = (values: string[]): FilterSpecification =>
    ['match', ['get', 'class'], values, true, false] as unknown as FilterSpecification;

/** A field equals one of these values, or the feature is dropped. */
const fieldIn = (field: string, values: string[]): FilterSpecification =>
    ['match', ['get', field], values, true, false] as unknown as FilterSpecification;

interface Palette {
    background: string;
    water: string;
    waterway: string;
    waterText: string;
    wood: string;
    grass: string;
    farmland: string;
    sand: string;
    wetland: string;
    ice: string;
    rock: string;
    residential: string;
    commercial: string;
    institutional: string;
    green: string;
    building: string;
    buildingOutline: string;
    aeroway: string;
    rail: string;
    boundaryMajor: string;
    boundaryMinor: string;
    /** Motorways and trunks: Google's amber. */
    motorway: string;
    motorwayCasing: string;
    /** Primary roads: white, with a warm casing. */
    roadPrimary: string;
    roadPrimaryCasing: string;
    /** Everything below primary: white, with a neutral casing. */
    road: string;
    roadCasing: string;
    text: string;
    textMinor: string;
    textHalo: string;
}

const LIGHT: Palette = {
    background: '#f4f3ef',
    water: '#aadaff',
    waterway: '#a5d6fb',
    waterText: '#5d8ba8',
    wood: '#b8dfae',
    grass: '#c9e8c0',
    farmland: '#eef0d9',
    sand: '#f1e9d2',
    wetland: '#c3e2d4',
    ice: '#eaf4fb',
    rock: '#e9e7e2',
    residential: '#eceae4',
    commercial: '#e9e5df',
    institutional: '#e7e6e0',
    green: '#c5e5bd',
    building: '#e6e3dd',
    buildingOutline: '#dbd8d1',
    aeroway: '#e4e2dd',
    rail: '#cfcdc7',
    boundaryMajor: '#9e9e9e',
    boundaryMinor: '#b8b8b8',
    motorway: '#fcd68a',
    motorwayCasing: '#f0b357',
    roadPrimary: '#ffffff',
    roadPrimaryCasing: '#e8d9a8',
    road: '#ffffff',
    roadCasing: '#e3e1da',
    text: '#545454',
    textMinor: '#6f6f6f',
    textHalo: '#ffffff',
};

const DARK: Palette = {
    background: '#242f3e',
    water: '#17263c',
    waterway: '#1b2d45',
    waterText: '#7fa3bd',
    wood: '#22383b',
    grass: '#243a34',
    farmland: '#2b3a34',
    sand: '#3a3730',
    wetland: '#22383b',
    ice: '#33414f',
    rock: '#2b3544',
    residential: '#28323f',
    commercial: '#2b3544',
    institutional: '#2a3441',
    green: '#263c3f',
    building: '#2b3544',
    buildingOutline: '#333e4d',
    aeroway: '#2b3544',
    rail: '#3b4553',
    boundaryMajor: '#6b7686',
    boundaryMinor: '#4d5866',
    motorway: '#746855',
    motorwayCasing: '#8a7a5c',
    roadPrimary: '#38414e',
    roadPrimaryCasing: '#4c5665',
    road: '#38414e',
    roadCasing: '#2c3643',
    text: '#c8ccd0',
    textMinor: '#a3a9b0',
    textHalo: '#242f3e',
};

/** Wide at low zoom, narrow at high; the road groups below share these stops. */
const ROAD_ZOOMS = [6, 10, 13, 16] as const;

const scaled = (values: readonly [number, number, number, number]) =>
    ROAD_ZOOMS.map((z, i) => [z, values[i]] as const);

interface RoadGroup {
    id: string;
    classes: string[];
    fill: keyof Palette;
    casing: keyof Palette;
    fillWidth: ReadonlyArray<readonly [number, number]>;
    casingWidth: ReadonlyArray<readonly [number, number]>;
    minzoom: number;
}

/**
 * Google's road hierarchy, in its order: motorways at the top and visibly the
 * widest, then a long tail of ordinary white streets.
 *
 * Each class is its own pair of layers rather than one layer with a data-driven
 * width, because the casing has to be drawn *under* the fill and a single layer
 * cannot be both. The width ramps are the cartography: get them wrong and every
 * road reads as the same size, which is the difference between a map and a
 * diagram.
 */
const ROADS: RoadGroup[] = [
    {
        id: 'road-motorway',
        classes: ['motorway', 'motorway_construction'],
        fill: 'motorway',
        casing: 'motorwayCasing',
        fillWidth: scaled([0.9, 2.2, 4.5, 13]),
        casingWidth: scaled([2.0, 4.0, 8.0, 19]),
        minzoom: 5,
    },
    {
        id: 'road-trunk',
        classes: ['trunk', 'trunk_construction'],
        fill: 'motorway',
        casing: 'motorwayCasing',
        fillWidth: scaled([0.8, 2.0, 4.0, 11]),
        casingWidth: scaled([1.8, 3.6, 7.0, 16]),
        minzoom: 6,
    },
    {
        id: 'road-primary',
        classes: ['primary', 'primary_construction'],
        fill: 'roadPrimary',
        casing: 'roadPrimaryCasing',
        fillWidth: scaled([0.7, 1.6, 3.2, 9]),
        casingWidth: scaled([1.6, 3.0, 6.0, 14]),
        minzoom: 7,
    },
    {
        id: 'road-secondary',
        classes: ['secondary', 'secondary_construction'],
        fill: 'road',
        casing: 'roadCasing',
        fillWidth: scaled([0.5, 1.2, 2.4, 7]),
        casingWidth: scaled([1.2, 2.4, 4.6, 11]),
        minzoom: 9,
    },
    {
        id: 'road-tertiary',
        classes: ['tertiary', 'tertiary_construction'],
        fill: 'road',
        casing: 'roadCasing',
        fillWidth: scaled([0.4, 0.9, 1.8, 5.4]),
        casingWidth: scaled([1.0, 2.0, 3.6, 9]),
        minzoom: 10,
    },
    {
        id: 'road-minor',
        classes: ['minor', 'raceway'],
        fill: 'road',
        casing: 'roadCasing',
        fillWidth: scaled([0.3, 0.7, 1.3, 4.0]),
        casingWidth: scaled([0.8, 1.6, 2.8, 7]),
        minzoom: 12,
    },
];

/** Tunnels are drawn below the water, so a road does not cross a river. */
const TUNNEL_CLASSES = [
    'motorway',
    'motorway_construction',
    'trunk',
    'trunk_construction',
    'primary',
    'primary_construction',
    'secondary',
    'tertiary',
];

const notTunnel: FilterSpecification = [
    '!=',
    ['get', 'brunnel'],
    'tunnel',
] as unknown as FilterSpecification;

const onlyTunnel: FilterSpecification = [
    '==',
    ['get', 'brunnel'],
    'tunnel',
] as unknown as FilterSpecification;

const lineLayout = {
    'line-cap': 'round',
    'line-join': 'round',
} as const;

const roadLayers = (palette: Palette): LayerSpecification[] =>
    ROADS.flatMap((road): LayerSpecification[] => {
        const filter: FilterSpecification = [
            'all',
            classIn(road.classes),
            notTunnel,
        ] as unknown as FilterSpecification;
        return [
            {
                id: `${road.id}-casing`,
                type: 'line',
                source: TILES_SOURCE,
                'source-layer': 'transportation',
                minzoom: road.minzoom,
                filter,
                layout: lineLayout,
                paint: {
                    'line-color': palette[road.casing],
                    'line-width': ramp(road.casingWidth),
                },
            },
            {
                id: road.id,
                type: 'line',
                source: TILES_SOURCE,
                'source-layer': 'transportation',
                minzoom: road.minzoom,
                filter,
                layout: lineLayout,
                paint: {
                    'line-color': palette[road.fill],
                    'line-width': ramp(road.fillWidth),
                },
            },
        ];
    });

/**
 * Buildings, roads and labels, in draw order. Earlier is further down.
 *
 * The one ordering decision worth naming: the tunnel pair sits *before* the
 * water fill, so a tunnel that runs under a river is hidden by it while a
 * bridge -- which is `brunnel: bridge` and stays in the ordinary road layers --
 * is drawn on top. Without that, the D2 through Lamač would cut across the
 * Danube on the map.
 */
const layers = (p: Palette): LayerSpecification[] => [
    {
        id: 'background',
        type: 'background',
        paint: {'background-color': p.background},
    },
    {
        id: 'landcover',
        type: 'fill',
        source: TILES_SOURCE,
        'source-layer': 'landcover',
        paint: {
            // A transparent fallback: a class this build does not know draws
            // nothing rather than being painted as though it were grass.
            'fill-color': [
                'match',
                ['get', 'class'],
                'wood',
                p.wood,
                'grass',
                p.grass,
                'farmland',
                p.farmland,
                'sand',
                p.sand,
                'wetland',
                p.wetland,
                'ice',
                p.ice,
                'rock',
                p.rock,
                'rgba(0,0,0,0)',
            ] as unknown as ExpressionSpecification,
            'fill-opacity': 0.85,
        },
    },
    {
        id: 'landuse-residential',
        type: 'fill',
        source: TILES_SOURCE,
        'source-layer': 'landuse',
        minzoom: 9,
        filter: classIn(['residential', 'neighbourhood', 'quarter', 'suburb']),
        paint: {'fill-color': p.residential, 'fill-opacity': 0.6},
    },
    {
        id: 'landuse-commercial',
        type: 'fill',
        source: TILES_SOURCE,
        'source-layer': 'landuse',
        minzoom: 11,
        filter: classIn([
            'commercial',
            'retail',
            'industrial',
            'garages',
            'railway',
            'bus_station',
        ]),
        paint: {'fill-color': p.commercial, 'fill-opacity': 0.75},
    },
    {
        id: 'landuse-institutional',
        type: 'fill',
        source: TILES_SOURCE,
        'source-layer': 'landuse',
        minzoom: 11,
        filter: classIn([
            'school',
            'university',
            'college',
            'kindergarten',
            'hospital',
            'library',
            'civic',
            'town_hall',
            'place_of_worship',
            'museum',
        ]),
        paint: {'fill-color': p.institutional, 'fill-opacity': 0.9},
    },
    {
        id: 'landuse-green',
        type: 'fill',
        source: TILES_SOURCE,
        'source-layer': 'landuse',
        minzoom: 10,
        filter: classIn([
            'pitch',
            'playground',
            'park',
            'cemetery',
            'recreation_ground',
            'garden',
            'zoo',
            'stadium',
            'track',
            'grassland',
            'village_green',
            'allotments',
            'meadow',
            'sports_centre',
            'golf_course',
            'nature_reserve',
        ]),
        paint: {'fill-color': p.green, 'fill-opacity': 0.9},
    },
    {
        // No class filter, on purpose: `park.class` is free text in this data.
        id: 'park',
        type: 'fill',
        source: TILES_SOURCE,
        'source-layer': 'park',
        minzoom: 7,
        paint: {'fill-color': p.green, 'fill-opacity': 0.75},
    },
    {
        id: 'tunnel-casing',
        type: 'line',
        source: TILES_SOURCE,
        'source-layer': 'transportation',
        minzoom: 10,
        filter: ['all', classIn(TUNNEL_CLASSES), onlyTunnel] as unknown as FilterSpecification,
        layout: lineLayout,
        paint: {
            'line-color': p.roadCasing,
            'line-width': ramp(scaled([0, 1.6, 3.0, 8.0])),
            'line-opacity': 0.5,
            'line-dasharray': [3, 2],
        },
    },
    {
        id: 'tunnel',
        type: 'line',
        source: TILES_SOURCE,
        'source-layer': 'transportation',
        minzoom: 10,
        filter: ['all', classIn(TUNNEL_CLASSES), onlyTunnel] as unknown as FilterSpecification,
        layout: lineLayout,
        paint: {
            'line-color': p.road,
            'line-width': ramp(scaled([0, 0.8, 1.5, 5.0])),
            'line-opacity': 0.5,
        },
    },
    {
        id: 'water',
        type: 'fill',
        source: TILES_SOURCE,
        'source-layer': 'water',
        paint: {'fill-color': p.water},
    },
    {
        id: 'waterway',
        type: 'line',
        source: TILES_SOURCE,
        'source-layer': 'waterway',
        minzoom: 9,
        layout: lineLayout,
        paint: {
            'line-color': p.waterway,
            // A river is worth seeing at every zoom; a drainage ditch is not.
            'line-width': [
                'interpolate',
                ['linear'],
                ['zoom'],
                9,
                ['match', ['get', 'class'], ['river', 'canal'], 1.2, 0.3],
                16,
                ['match', ['get', 'class'], ['river', 'canal'], 7, 1.5],
            ] as unknown as ExpressionSpecification,
        },
    },
    {
        id: 'aeroway',
        type: 'fill',
        source: TILES_SOURCE,
        'source-layer': 'aeroway',
        minzoom: 10,
        paint: {'fill-color': p.aeroway},
    },
    {
        id: 'building',
        type: 'fill',
        source: TILES_SOURCE,
        'source-layer': 'building',
        minzoom: 14,
        paint: {
            'fill-color': p.building,
            'fill-opacity': ramp([
                [14, 0],
                [15, 0.7],
                [16, 0.9],
            ]),
        },
    },
    {
        id: 'building-outline',
        type: 'line',
        source: TILES_SOURCE,
        'source-layer': 'building',
        minzoom: 16,
        paint: {'line-color': p.buildingOutline, 'line-width': 0.5},
    },
    {
        id: 'rail',
        type: 'line',
        source: TILES_SOURCE,
        'source-layer': 'transportation',
        minzoom: 11,
        filter: classIn(['rail', 'transit']),
        layout: lineLayout,
        paint: {
            'line-color': p.rail,
            'line-width': ramp([
                [11, 0.5],
                [14, 1.2],
                [16, 2.2],
            ]),
            'line-dasharray': [3, 2],
        },
    },
    ...roadLayers(p),
    {
        id: 'road-service',
        type: 'line',
        source: TILES_SOURCE,
        'source-layer': 'transportation',
        minzoom: 14,
        filter: ['all', classIn(['service']), notTunnel] as unknown as FilterSpecification,
        layout: lineLayout,
        paint: {
            'line-color': p.road,
            'line-width': ramp([
                [14, 1.0],
                [16, 3.0],
            ]),
        },
    },
    {
        // A pedestrian zone is a street, not a footpath: Google draws it as one.
        id: 'road-pedestrian',
        type: 'line',
        source: TILES_SOURCE,
        'source-layer': 'transportation',
        minzoom: 14,
        filter: fieldIn('subclass', ['pedestrian']),
        layout: lineLayout,
        paint: {
            'line-color': p.road,
            'line-width': ramp([
                [14, 1.2],
                [16, 4.5],
            ]),
        },
    },
    {
        // Footpaths and tracks last and thinnest, and only once the reader has
        // zoomed in far enough to want them: Google shows none at z14.
        id: 'road-path',
        type: 'line',
        source: TILES_SOURCE,
        'source-layer': 'transportation',
        minzoom: 15,
        filter: classIn(['path', 'track']),
        layout: {'line-cap': 'butt', 'line-join': 'round'},
        paint: {
            'line-color': p.road,
            'line-width': ramp([
                [15, 0.6],
                [16, 1.6],
            ]),
            'line-dasharray': [2, 1.5],
        },
    },
    {
        id: 'boundary-minor',
        type: 'line',
        source: TILES_SOURCE,
        'source-layer': 'boundary',
        minzoom: 9,
        filter: ['>=', ['get', 'admin_level'], 6] as unknown as FilterSpecification,
        layout: lineLayout,
        paint: {
            'line-color': p.boundaryMinor,
            'line-width': ramp([
                [9, 0.5],
                [16, 1.2],
            ]),
            'line-dasharray': [2, 2],
        },
    },
    {
        id: 'boundary-major',
        type: 'line',
        source: TILES_SOURCE,
        'source-layer': 'boundary',
        minzoom: 4,
        filter: [
            'all',
            ['<=', ['get', 'admin_level'], 4],
            // A maritime border has no business being drawn on a land map.
            ['!=', ['get', 'maritime'], 1],
        ] as unknown as FilterSpecification,
        layout: lineLayout,
        paint: {
            'line-color': p.boundaryMajor,
            'line-width': ramp([
                [4, 0.6],
                [10, 1.1],
                [16, 1.8],
            ]),
        },
    },

    // ---- Labels -----------------------------------------------------------------
    // Placed first to last, which is also collision priority: a city name beats
    // a shop name for the same pixels.

    {
        id: 'place-city',
        type: 'symbol',
        source: TILES_SOURCE,
        'source-layer': 'place',
        minzoom: 4,
        filter: classIn(['city']),
        layout: {
            'text-field': NAME,
            'text-font': BOLD,
            'text-size': ramp([
                [4, 11],
                [8, 15],
                [12, 20],
                [16, 25],
            ]),
            'text-letter-spacing': 0.02,
            'text-max-width': 8,
        },
        paint: {
            'text-color': p.text,
            'text-halo-color': p.textHalo,
            'text-halo-width': 1.3,
            'text-halo-blur': 0.5,
        },
    },
    {
        id: 'place-town',
        type: 'symbol',
        source: TILES_SOURCE,
        'source-layer': 'place',
        minzoom: 7,
        filter: classIn(['town']),
        layout: {
            'text-field': NAME,
            'text-font': BOLD,
            'text-size': ramp([
                [7, 10.5],
                [11, 14],
                [14, 18],
            ]),
            'text-max-width': 8,
        },
        paint: {
            'text-color': p.text,
            'text-halo-color': p.textHalo,
            'text-halo-width': 1.2,
            'text-halo-blur': 0.5,
        },
    },
    {
        id: 'place-village',
        type: 'symbol',
        source: TILES_SOURCE,
        'source-layer': 'place',
        minzoom: 10,
        filter: classIn(['village', 'hamlet', 'isolated_dwelling']),
        layout: {
            'text-field': NAME,
            'text-font': REGULAR,
            'text-size': ramp([
                [10, 10],
                [13, 12.5],
                [16, 15],
            ]),
            'text-max-width': 8,
        },
        paint: {
            'text-color': p.text,
            'text-halo-color': p.textHalo,
            'text-halo-width': 1.1,
            'text-halo-blur': 0.5,
        },
    },
    {
        id: 'place-suburb',
        type: 'symbol',
        source: TILES_SOURCE,
        'source-layer': 'place',
        minzoom: 11,
        filter: classIn(['suburb', 'quarter', 'neighbourhood', 'island']),
        layout: {
            'text-field': NAME,
            'text-font': REGULAR,
            'text-size': ramp([
                [11, 9.5],
                [14, 12],
                [16, 13.5],
            ]),
            'text-letter-spacing': 0.05,
            'text-max-width': 8,
        },
        paint: {
            'text-color': p.textMinor,
            'text-halo-color': p.textHalo,
            'text-halo-width': 1.1,
            'text-halo-blur': 0.5,
        },
    },
    {
        id: 'water-name',
        type: 'symbol',
        source: TILES_SOURCE,
        'source-layer': 'water_name',
        minzoom: 11,
        layout: {
            'text-field': NAME,
            'text-font': ITALIC,
            'text-size': ramp([
                [11, 10],
                [14, 12.5],
                [16, 14],
            ]),
            'text-max-width': 7,
        },
        paint: {
            'text-color': p.waterText,
            'text-halo-color': p.textHalo,
            'text-halo-width': 1,
        },
    },
    {
        // Google labels a motorway with its number, and Slovakia's drivers
        // navigate by exactly these.
        id: 'road-ref',
        type: 'symbol',
        source: TILES_SOURCE,
        'source-layer': 'transportation_name',
        minzoom: 10,
        filter: [
            'all',
            classIn(['motorway', 'trunk']),
            ['has', 'ref'],
        ] as unknown as FilterSpecification,
        layout: {
            'text-field': ['get', 'ref'] as unknown as ExpressionSpecification,
            'text-font': BOLD,
            'text-size': ramp([
                [10, 9],
                [16, 12],
            ]),
            'symbol-placement': 'line',
            'text-rotation-alignment': 'map',
        },
        paint: {
            'text-color': p.motorwayCasing,
            'text-halo-color': p.textHalo,
            'text-halo-width': 1.4,
        },
    },
    {
        id: 'road-name',
        type: 'symbol',
        source: TILES_SOURCE,
        'source-layer': 'transportation_name',
        minzoom: 14,
        filter: ['has', 'name'] as unknown as FilterSpecification,
        layout: {
            'text-field': NAME,
            'text-font': REGULAR,
            'text-size': ramp([
                [14, 10],
                [18, 13],
            ]),
            'symbol-placement': 'line',
            'text-rotation-alignment': 'map',
            'text-max-angle': 30,
            'text-padding': 4,
        },
        paint: {
            'text-color': p.textMinor,
            'text-halo-color': p.textHalo,
            'text-halo-width': 1.2,
            'text-halo-blur': 0.5,
        },
    },
    {
        // Named features only. The same layer carries gate, bollard and
        // waste_basket -- hundreds per city tile, none of them named -- and an
        // unfiltered POI layer would be a field of unlabelled dots.
        id: 'peak',
        type: 'symbol',
        source: TILES_SOURCE,
        'source-layer': 'mountain_peak',
        minzoom: 11,
        filter: classIn(['peak', 'volcano']),
        layout: {
            'text-field': [
                'case',
                ['has', 'ele'],
                [
                    'concat',
                    NAME,
                    ' ',
                    ['to-string', ['get', 'ele']],
                    ' m',
                ],
                NAME,
            ] as unknown as ExpressionSpecification,
            'text-font': ITALIC,
            'text-size': ramp([
                [11, 9.5],
                [16, 12],
            ]),
        },
        paint: {
            'text-color': p.textMinor,
            'text-halo-color': p.textHalo,
            'text-halo-width': 1.1,
        },
    },
    {
        id: 'aerodrome',
        type: 'symbol',
        source: TILES_SOURCE,
        'source-layer': 'aerodrome_label',
        minzoom: 10,
        filter: ['has', 'name'] as unknown as FilterSpecification,
        layout: {
            'text-field': NAME,
            'text-font': REGULAR,
            'text-size': ramp([
                [10, 10],
                [16, 13],
            ]),
        },
        paint: {
            'text-color': p.textMinor,
            'text-halo-color': p.textHalo,
            'text-halo-width': 1.1,
        },
    },
    {
        id: 'poi',
        type: 'symbol',
        source: TILES_SOURCE,
        'source-layer': 'poi',
        minzoom: 15,
        filter: [
            'all',
            ['has', 'name'],
            // `rank` orders by importance; 30 keeps the notable ones. The
            // coalesce is not decoration -- a missing rank must not read as
            // rank zero and promote a bus shelter above a hospital.
            ['<=', ['coalesce', ['get', 'rank'], 999], 30],
            classIn([
                'restaurant',
                'cafe',
                'bar',
                'beer',
                'pub',
                'fast_food',
                'bakery',
                'butcher',
                'grocery',
                'supermarket',
                'marketplace',
                'clothing_store',
                'hairdresser',
                'bank',
                'atm',
                'pharmacy',
                'hospital',
                'clinic',
                'doctors',
                'dentist',
                'school',
                'university',
                'college',
                'kindergarten',
                'library',
                'town_hall',
                'post',
                'police',
                'fire_station',
                'place_of_worship',
                'castle',
                'museum',
                'art_gallery',
                'theatre',
                'cinema',
                'lodging',
                'hotel',
                'fuel',
                'parking',
                'bus',
                'railway',
                'zoo',
                'stadium',
                'swimming_pool',
                'bicycle_rental',
                'car',
                'information',
                'picnic_site',
            ]),
        ] as unknown as FilterSpecification,
        layout: {
            'text-field': NAME,
            'text-font': REGULAR,
            'text-size': ramp([
                [15, 9.5],
                [18, 11.5],
            ]),
            'text-max-width': 8,
            'symbol-sort-key': ['coalesce', ['get', 'rank'], 999] as unknown as ExpressionSpecification,
        },
        paint: {
            'text-color': p.textMinor,
            'text-halo-color': p.textHalo,
            'text-halo-width': 1.1,
            'text-halo-blur': 0.5,
        },
    },
];

/**
 * The style for one theme.
 *
 * Both flavours are built from the same layer list, so the two cannot drift into
 * different cartography -- only the palette differs. That is also what makes the
 * theme switchable at runtime: `map.setStyle(mapStyle(next))` produces a style
 * whose structure is identical, so nothing about the drawing has to be redone by
 * hand.
 */
export const mapStyle = (dark: boolean): StyleSpecification => ({
    version: 8,
    name: dark ? 'CistaFirma dark' : 'CistaFirma light',
    glyphs: GLYPHS_URL,
    sources: {
        [TILES_SOURCE]: {
            type: 'vector',
            url: TILEJSON_URL,
        },
    },
    layers: layers(dark ? DARK : LIGHT),
});
