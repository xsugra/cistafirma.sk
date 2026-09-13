/**
 * The circle a PSČ is, as geometry rather than as a renderer's convenience.
 *
 * Google's `Circle` took a centre and a radius in metres and did this
 * internally. MapLibre has no metre-radius primitive at all -- its `circle`
 * layer draws in pixels, and a pixel radius would mean something different on
 * every screen and at every zoom. So the ring is built here, which is the better
 * outcome anyway: the arithmetic is testable without a map, and the same ring is
 * both what the renderer fills and what the tests measure.
 *
 * The distance is walked on a sphere (the haversine destination-point formula),
 * not on the flat Mercator plane the map is drawn on. At the scale of one PSČ the
 * two differ by well under a pixel, but the sphere is the honest one: `radiusM`
 * in `SeatLocation` is a distance on the ground, measured from real address
 * points, and that is the distance this reproduces.
 */

import type {Feature, Polygon, Position} from 'geojson';

/** IUGG mean Earth radius, metres. */
export const EARTH_RADIUS_M = 6371008.8;

/**
 * Vertices in the ring.
 *
 * The ring's edges are straight lines between sampled points, so the drawn
 * polygon is inscribed in the true circle and its worst error is the sagitta,
 * `r * (1 - cos(pi / steps))`. At the largest radius the table stores -- 8 717 m
 * -- 64 steps put that at about 10 m. On a circle drawn 90 px across, 10 m is a
 * tenth of a pixel, and `radiusM` itself is a 90th percentile rather than a
 * measurement, so more vertices would buy nothing a reader could see.
 *
 * The same argument covers the projection: a straight line in longitude and
 * latitude is not straight on screen, but over a span this small the bow is far
 * below one pixel.
 */
export const CIRCLE_STEPS = 64;

export interface Centre {
    lat: number;
    lon: number;
}

/**
 * A closed GeoJSON polygon approximating the circle of `radiusM` around `centre`.
 *
 * The ring runs counter-clockwise, which is what RFC 7946 asks of an exterior
 * ring: the bearings are negated so that the walk starts due north and then turns
 * west. MapLibre's tessellator is winding-agnostic, so this is for whatever reads
 * the geometry next rather than for the renderer.
 *
 * A `radiusM` of zero is not special-cased. It produces a ring whose every vertex
 * is the centre -- a degenerate polygon that draws nothing and raises nothing,
 * which is what zero metres of uncertainty deserves. (`zoomFor` clamps the other
 * end.)
 */
export const circlePolygon = (
    centre: Centre,
    radiusM: number,
    steps: number = CIRCLE_STEPS,
): Feature<Polygon> => {
    const angular = radiusM / EARTH_RADIUS_M;
    const sinAngular = Math.sin(angular);
    const cosAngular = Math.cos(angular);

    const lat1 = (centre.lat * Math.PI) / 180;
    const lon1 = (centre.lon * Math.PI) / 180;
    const sinLat1 = Math.sin(lat1);
    const cosLat1 = Math.cos(lat1);

    const ring: Position[] = [];
    // `<= steps` closes the ring: GeoJSON requires the last position to repeat
    // the first, and a ring that does not close is an invalid polygon.
    for (let i = 0; i <= steps; i++) {
        const bearing = -(i / steps) * 2 * Math.PI;

        const lat2 = Math.asin(
            sinLat1 * cosAngular + cosLat1 * sinAngular * Math.cos(bearing),
        );
        const lon2 =
            lon1 +
            Math.atan2(
                Math.sin(bearing) * sinAngular * cosLat1,
                cosAngular - sinLat1 * Math.sin(lat2),
            );

        ring.push([(lon2 * 180) / Math.PI, (lat2 * 180) / Math.PI]);
    }

    return {
        type: 'Feature',
        properties: {},
        geometry: {type: 'Polygon', coordinates: [ring]},
    };
};
