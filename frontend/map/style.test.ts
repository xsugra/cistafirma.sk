import {describe, expect, it} from 'vitest';
import {validateStyleMin} from '@maplibre/maplibre-gl-style-spec';
import type {LayerSpecification, StyleSpecification} from '@maplibre/maplibre-gl-style-spec';
import {ATTRIBUTION, GLYPHS_URL, TILEJSON_URL, TILES_SOURCE, mapStyle} from './style';

/**
 * The style is the map. Everything a reader sees comes out of this file, and the
 * way it fails is the way this project keeps paying for: a layer whose
 * `source-layer` does not exist, or whose filter names a field the tile does not
 * carry, renders *nothing* and logs nothing. There is no error to catch at
 * runtime, so the checks have to be here.
 *
 * Two of them are worth more than the rest. The first is that the style passes the
 * style spec's own validator, which checks expression arity, property names and
 * value ranges far more strictly than `tsc` would -- and it is guarded by a test
 * that feeds it a broken style, because a validator that silently validates
 * nothing would make every other assertion in this file vacuous.
 *
 * The second is the `source-layer` list. It is not what the OpenMapTiles
 * documentation says; it is what decoding real OpenFreeMap tiles actually found.
 * Three separate layers in the first draft of this style named fields that do not
 * exist (`boundary.class` and `building.class` among them), and all three would
 * have drawn nothing at all.
 */

/** Layers the tiles were measured to contain, decoded from real OpenFreeMap tiles. */
const MEASURED_SOURCE_LAYERS = [
    'aerodrome_label',
    'aeroway',
    'boundary',
    'building',
    'housenumber',
    'landcover',
    'landuse',
    'mountain_peak',
    'park',
    'place',
    'poi',
    'transportation',
    'transportation_name',
    'water',
    'water_name',
    'waterway',
];

/** Every `['get', 'field']` a filter reads, at any depth. */
const fieldsIn = (expression: unknown): string[] => {
    if (!Array.isArray(expression)) return [];
    if (expression[0] === 'get' && typeof expression[1] === 'string') {
        return [expression[1]];
    }
    return expression.flatMap(fieldsIn);
};

const layersUsing = (style: StyleSpecification, sourceLayer: string) =>
    style.layers.filter(
        (layer) => 'source-layer' in layer && layer['source-layer'] === sourceLayer,
    );

const LIGHT = mapStyle(false);
const DARK = mapStyle(true);

/** A style that is wrong in several independent ways at once. */
const BROKEN: StyleSpecification = {
    version: 8,
    sources: {[TILES_SOURCE]: {type: 'vector', url: TILEJSON_URL}},
    layers: [
        {
            id: 'broken-colour',
            type: 'background',
            paint: {'background-color': 'not-a-colour'},
        } as LayerSpecification,
        {
            id: 'broken-expression',
            type: 'line',
            source: TILES_SOURCE,
            'source-layer': 'transportation',
            paint: {'line-width': ['interpolate', ['linear'], ['zoom']]},
        } as unknown as LayerSpecification,
    ],
};

describe('mapStyle', () => {
    it('passes the style spec its own validator, in both themes', () => {
        expect(validateStyleMin(LIGHT)).toEqual([]);
        expect(validateStyleMin(DARK)).toEqual([]);
    });

    it('is checked by a validator that can actually fail', () => {
        // Without this, the assertion above would pass just as happily against a
        // validator that returned no errors for anything -- which is the shape of
        // every control that has ever read healthy while the thing it guarded was
        // broken.
        const errors = validateStyleMin(BROKEN);

        expect(errors.length).toBeGreaterThan(0);
        expect(errors.map((error) => error.message).join(' ')).toMatch(
            /not-a-colour|Expected at least 4 arguments/,
        );
    });

    it('takes its tiles from the TileJSON document, never from a tile template', () => {
        // The measured trap. `https://tiles.openfreemap.org/planet/{z}/{x}/{y}.pbf`
        // -- the unversioned path nearly every tutorial shows -- answers HTTP 200
        // with a zero-byte body and an `x-ofm-debug: empty tile` header for every
        // tile, so a style built on it draws a blank canvas with nothing in the
        // console to explain it. The versioned path works, and it is the versioned
        // path the TileJSON advertises, so the source has to be the document.
        const source = LIGHT.sources[TILES_SOURCE] as {
            type: string;
            url?: string;
            tiles?: unknown;
        };

        expect(source.type).toBe('vector');
        expect(source.url).toBe(TILEJSON_URL);
        expect(source.tiles).toBeUndefined();
        expect(TILEJSON_URL).not.toMatch(/\{z\}/);
    });

    it('declares the glyphs the TileJSON does not, and no sprite it cannot use', () => {
        // OpenFreeMap's TileJSON declares neither, and a style with text and no
        // `glyphs` draws no text at all -- silently, as ever. A `sprite` would be
        // worse than useless: there is no sprite to fetch, and any layer naming an
        // icon would render an empty gap.
        expect(LIGHT.glyphs).toBe(GLYPHS_URL);
        expect(LIGHT.sprite).toBeUndefined();

        for (const layer of [...LIGHT.layers, ...DARK.layers]) {
            if (layer.type !== 'symbol') continue;
            expect(layer.layout?.['icon-image']).toBeUndefined();
        }
    });

    it('draws only from source layers the tiles were measured to carry', () => {
        for (const layer of [...LIGHT.layers, ...DARK.layers]) {
            if (!('source-layer' in layer)) continue;
            expect(MEASURED_SOURCE_LAYERS).toContain(layer['source-layer']);
        }
    });

    it('filters boundaries on admin_level, because boundary has no class', () => {
        // The measured fact that would have cost the most: `boundary` carries
        // `admin_level`, `disputed` and `maritime` -- and no `class` at all. A
        // filter on `class` is the obvious guess and matches nothing, so Slovakia
        // would have been drawn with no borders and no error anywhere.
        const boundaries = layersUsing(LIGHT, 'boundary');

        expect(boundaries.length).toBeGreaterThan(0);
        for (const layer of boundaries) {
            expect(fieldsIn('filter' in layer ? layer.filter : undefined)).toContain(
                'admin_level',
            );
            expect(
                fieldsIn('filter' in layer ? layer.filter : undefined),
            ).not.toContain('class');
        }
    });

    it('draws every building, because building has no class either', () => {
        const buildings = layersUsing(LIGHT, 'building');

        expect(buildings.length).toBeGreaterThan(0);
        for (const layer of buildings) {
            expect(
                fieldsIn('filter' in layer ? layer.filter : undefined),
            ).not.toContain('class');
        }
    });

    it('draws every park, because park class is free text', () => {
        // Measured values include `Natura 2000`, `Prírodná rezervácia` and
        // `Národná prírodná rezervácia` alongside the English ones, so a `match` on
        // a remembered vocabulary would have dropped Slovakia's protected areas
        // while keeping the generic ones -- the worst kind of partial failure,
        // because it looks like it works.
        const parks = layersUsing(LIGHT, 'park');

        expect(parks.length).toBeGreaterThan(0);
        for (const layer of parks) {
            expect('filter' in layer ? layer.filter : undefined).toBeUndefined();
        }
    });

    it('draws the two themes from one cartography, differing only in colour', () => {
        // A theme toggle runs `setStyle`, so anything that differs between the two
        // apart from the palette would change the map's structure on a toggle --
        // different layers, different filters, a different map. Pinning the
        // structure is what makes that impossible rather than merely unlikely.
        const structure = (style: StyleSpecification) =>
            style.layers.map((layer) => ({
                id: layer.id,
                type: layer.type,
                source: 'source' in layer ? layer.source : undefined,
                sourceLayer:
                    'source-layer' in layer ? layer['source-layer'] : undefined,
                minzoom: 'minzoom' in layer ? layer.minzoom : undefined,
                filter: 'filter' in layer ? layer.filter : undefined,
            }));

        expect(structure(DARK)).toEqual(structure(LIGHT));
    });

    it('credits all three sources the licences require, each linked', () => {
        // A licence obligation rather than decoration, and one that is easy to
        // lose silently: the attribution lives in the TileJSON too, but nothing
        // here would notice if OpenFreeMap changed it.
        expect(ATTRIBUTION.map((credit) => credit.label)).toEqual([
            'OpenFreeMap',
            '© OpenMapTiles',
            'Data from OpenStreetMap',
        ]);
        for (const credit of ATTRIBUTION) {
            expect(credit.href).toMatch(/^https:\/\//);
        }
        // OpenStreetMap's guidelines ask for the credit to reach the copyright
        // page, not the project home page.
        expect(
            ATTRIBUTION.find((credit) => credit.label === 'Data from OpenStreetMap')
                ?.href,
        ).toBe('https://www.openstreetmap.org/copyright');
    });
});
