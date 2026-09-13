import React, { lazy, Suspense } from 'react';
import type { SeatLocation } from '../../types';
import { formatNumber } from '../../utils/format';

// Lazily: the map pulls in the Maps JavaScript API loader, and no other part of
// the company page needs it. The card itself is tiny, so it still renders its
// heading and its sentence while the chunk is in flight -- and the Google script
// itself is not requested until `SeatMap` mounts and finds a key.
const SeatMap = lazy(() =>
    import('./SeatMap').then((m) => ({ default: m.SeatMap })),
);

/** `±737 m` below a kilometre, `±4,1 km` above it -- Slovak decimal comma. */
export const formatRadius = (radiusM: number): string => {
    if (radiusM < 1000) return `±${formatNumber(radiusM)} m`;
    const km = (radiusM / 1000).toFixed(1).replace('.', ',');
    return `±${km} km`;
};

interface SeatLocationCardProps {
    seat: SeatLocation;
}

/**
 * The registered seat, drawn as the area we actually know rather than a pin.
 *
 * The sentence under the map is not decoration and is not optional. A circle on
 * a map reads as *the company's grounds* unless something says otherwise, and
 * what it means here is the opposite: the register places the seat somewhere
 * inside it and nowhere more precisely. That is why the radius travels from the
 * API at all (`SeatLocation` in `types.ts`), and why this card shows the number
 * next to the heading instead of leaving it to be inferred from the drawing.
 */
export const SeatLocationCard: React.FC<SeatLocationCardProps> = ({ seat }) => (
    <div className="mt-6 border-t border-gray-200 dark:border-slate-800 pt-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                <i className="fas fa-map-location-dot text-blue-500 dark:text-blue-400" aria-hidden="true" />
                Sídlo na mape
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
                PSČ {seat.psc} · presnosť {formatRadius(seat.radiusM)}
            </p>
        </div>

        <div className="mt-3 h-56 overflow-hidden rounded-lg border border-gray-200 dark:border-slate-800">
            <Suspense
                fallback={
                    <div className="flex h-full items-center justify-center bg-gray-50 text-sm text-gray-500 dark:bg-slate-900 dark:text-gray-400">
                        <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                        Načítavam mapu…
                    </div>
                }
            >
                <SeatMap seat={seat} />
            </Suspense>
        </div>

        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
            Kruh je <strong className="font-semibold text-gray-700 dark:text-gray-300">presnosť, nie veľkosť firmy</strong>:
            v tomto kruhu leží 90 % adries s PSČ {seat.psc}. Register adries pozná
            len stred PSČ, takže bližšie sídlo umiestniť nevieme.
        </p>
        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
            Zdroj: Register adries MV SR
        </p>
    </div>
);
