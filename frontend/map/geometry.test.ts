import {describe, expect, it} from 'vitest';
import {CIRCLE_STEPS, EARTH_RADIUS_M, circlePolygon} from './geometry';
import type {Position} from 'geojson';

/**
 * The ring is the claim, so it is measured rather than eyeballed.
 *
 * `zoomFor` decides how big the circle is drawn; this file decides what the
 * circle *is*. A ring built from the wrong number would still render, still look
 * like a circle, and still be wrong -- which is the failure mode this whole
 * component exists to avoid, since the ring is what tells a reader how much
 * precision a PSČ centroid actually has.
 *
 * The distances below are computed with the haversine *distance* formula, which
 * is a different equation from the destination-point formula `geometry.ts` uses
 * to walk the ring. That is deliberate: a test that re-derived the vertices the
 * same way would agree with the implementation even when the implementation is
 * wrong.
 */

/** Great-circle distance between two `[lon, lat]` positions, in metres. */
const distanceM = (a: Position, b: Position) => {
    const toRad = (degrees: number) => (degrees * Math.PI) / 180;
    const dLat = toRad(b[1] - a[1]);
    const dLon = toRad(b[0] - a[0]);
    const h =
        Math.sin(dLat / 2) ** 2 +
        Math.cos(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.sin(dLon / 2) ** 2;
    return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
};

/** Signed area in the lon/lat plane; positive means counter-clockwise. */
const signedArea = (ring: Position[]) =>
    ring.reduce((sum, [, lat], index) => {
        const [lon] = ring[index];
        const [nextLon, nextLat] = ring[(index + 1) % ring.length];
        return sum + (lon * nextLat - nextLon * lat);
    }, 0) / 2;

/** PSČ 82109 Bratislava, the median-sized area in the table. */
const BRATISLAVA = {lat: 48.14748, lon: 17.14051};

const ringOf = (centre: {lat: number; lon: number}, radiusM: number, steps?: number) =>
    circlePolygon(centre, radiusM, steps).geometry.coordinates[0];

describe('circlePolygon', () => {
    it('returns a closed ring, as GeoJSON requires of a polygon', () => {
        // An unclosed ring is an invalid polygon: renderers disagree about what to
        // do with it, and the disagreement is silent.
        const ring = ringOf(BRATISLAVA, 737);

        expect(ring[0]).toEqual(ring[ring.length - 1]);
    });

    it('puts one vertex per step, plus the repeat that closes it', () => {
        expect(ringOf(BRATISLAVA, 737)).toHaveLength(CIRCLE_STEPS + 1);

        // The step count is a parameter so it can be reasoned about, not because
        // anything calls it with another value.
        expect(ringOf(BRATISLAVA, 737, 8)).toHaveLength(9);
    });

    it('walks the ring counter-clockwise, as RFC 7946 asks of an exterior ring', () => {
        expect(signedArea(ringOf(BRATISLAVA, 737))).toBeGreaterThan(0);
    });

    it('places every vertex the stored radius away from the centre', () => {
        // The contract, stated once per vertex rather than on average: no vertex
        // may be closer or further than `radiusM`, because a reader measuring the
        // drawn circle with the scale bar is measuring exactly this.
        const ring = ringOf(BRATISLAVA, 737);
        const centre: Position = [BRATISLAVA.lon, BRATISLAVA.lat];

        for (const vertex of ring) {
            expect(distanceM(centre, vertex)).toBeCloseTo(737, 3);
        }
    });

    it('holds that distance at the largest radius the table stores', () => {
        const ring = ringOf(BRATISLAVA, 8717);
        const centre: Position = [BRATISLAVA.lon, BRATISLAVA.lat];

        for (const vertex of ring) {
            expect(distanceM(centre, vertex)).toBeCloseTo(8717, 2);
        }
    });

    it('lands exactly one degree north when the radius is one degree of latitude', () => {
        // Ground truth, independent of the table: a radius of one degree of
        // latitude, at the equator, must reach latitude 1. This is the check that
        // would catch a formula that is consistently wrong -- a confusion between
        // mean and equatorial radius, or a swapped pair of arguments -- which the
        // per-vertex test above cannot, because it measures with the same radius
        // constant the ring was built from.
        const oneDegree = (Math.PI / 180) * EARTH_RADIUS_M;
        const ring = ringOf({lat: 0, lon: 0}, oneDegree);

        const lats = ring.map(([, lat]) => lat);
        expect(Math.max(...lats)).toBeCloseTo(1, 9);
        expect(Math.min(...lats)).toBeCloseTo(-1, 9);
    });

    it('starts due north, on the same longitude as the centre', () => {
        // Not load-bearing for the renderer, but it is what makes the ring's first
        // point predictable to whoever reads the geometry next.
        const ring = ringOf(BRATISLAVA, 737);
        const [lon, lat] = ring[0];

        expect(lon).toBeCloseTo(BRATISLAVA.lon, 9);
        expect(lat).toBeGreaterThan(BRATISLAVA.lat);
    });

    it('writes positions longitude-first', () => {
        // `[x, y]`, not `[lat, lon]`. Getting this backwards draws perfectly and
        // puts Slovak companies in the Indian Ocean.
        const [lon, lat] = ringOf(BRATISLAVA, 737)[0];

        expect(lon).toBeCloseTo(17.14051, 4);
        expect(lat).toBeCloseTo(48.1541, 3);
    });

    it('degenerates to a point at zero metres instead of producing NaN', () => {
        // No PSČ has a radius of zero, but `zoomFor` clamps one end of the range
        // and this is the other: a degenerate ring that draws nothing is the right
        // answer for zero metres of uncertainty, and it must not be a polygon full
        // of NaN, which renderers reject loudly and inconsistently.
        const ring = ringOf(BRATISLAVA, 0);

        for (const [lon, lat] of ring) {
            expect(Number.isFinite(lon)).toBe(true);
            expect(Number.isFinite(lat)).toBe(true);
            expect(lon).toBeCloseTo(BRATISLAVA.lon, 9);
            expect(lat).toBeCloseTo(BRATISLAVA.lat, 9);
        }
    });
});
