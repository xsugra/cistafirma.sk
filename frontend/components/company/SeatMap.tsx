/**
 * The seat on a map: a centroid, and the circle that stops it lying.
 *
 * Loaded lazily (`SeatLocationCard`) because Leaflet and its stylesheet are
 * ~150 kB that only this one card needs.
 *
 * Three decisions live here rather than in the card:
 *
 * - **A circle, centred on a dot.** The coordinate is a PSČ centroid, a median
 *   1 980 m from its own address points, so the circle is the claim and the dot
 *   only marks what it is centred on. A bare marker would read as a doorstep.
 * - **The zoom is computed from the radius**, not fixed. Our radii run 270 m to
 *   8 717 m; one zoom for all of them would either hide the circle or shrink it
 *   to a dot, and either way the reader would misread the precision.
 * - **`scrollWheelZoom` off.** The card sits inside a long page, and a map that
 *   captures the wheel traps the reader mid-scroll.
 */

import React from 'react';
import { Circle, CircleMarker, MapContainer, TileLayer } from 'react-leaflet';
import type { SeatLocation } from '../../types';
import 'leaflet/dist/leaflet.css';

/** Keep the circle inside roughly this many pixels of the map's centre. */
const RADIUS_PIXELS = 90;
/** Metres per pixel at zoom 0 on the equator; halved at every zoom step. */
const EQUATOR_METRES_PER_PIXEL = 156543.03392;
const MIN_ZOOM = 7;
const MAX_ZOOM = 16;

const BRAND = '#2563eb';

const zoomFor = (seat: SeatLocation) => {
    const metresPerPixelAtZero =
        EQUATOR_METRES_PER_PIXEL * Math.cos((seat.lat * Math.PI) / 180);
    const ideal = Math.log2(
        (metresPerPixelAtZero * RADIUS_PIXELS) / Math.max(seat.radiusM, 1),
    );
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(ideal)));
};

interface SeatMapProps {
    seat: SeatLocation;
}

export const SeatMap: React.FC<SeatMapProps> = ({ seat }) => {
    const centre: [number, number] = [seat.lat, seat.lon];

    return (
        <MapContainer
            // Keyed on the PSČ: Leaflet holds its own view state, so moving
            // between two companies without a remount would leave the second
            // company's pin on the first company's map.
            key={seat.psc}
            center={centre}
            zoom={zoomFor(seat)}
            scrollWheelZoom={false}
            // The tiles are a light basemap and this app has a dark theme. The
            // filter is confined to the tile pane so the circle, the dot and the
            // attribution keep their own colours instead of being inverted too.
            className="h-full w-full dark:[&_.leaflet-tile-pane]:[filter:invert(1)_hue-rotate(180deg)_brightness(0.95)_contrast(0.9)]"
            style={{ height: '100%', width: '100%' }}
        >
            <TileLayer
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                maxZoom={19}
            />
            <Circle
                center={centre}
                radius={seat.radiusM}
                pathOptions={{
                    color: BRAND,
                    weight: 2,
                    opacity: 0.9,
                    fillColor: BRAND,
                    fillOpacity: 0.12,
                }}
            />
            <CircleMarker
                center={centre}
                radius={4}
                pathOptions={{ color: '#ffffff', weight: 2, fillColor: BRAND, fillOpacity: 1 }}
            />
        </MapContainer>
    );
};
