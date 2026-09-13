import React, { lazy, Suspense } from 'react';
import type { SeatLocation } from '../../types';
import { formatNumber } from '../../utils/format';

// Lazily: the renderer is MapLibre GL and it is the largest thing on the page,
// while no other part of the company page needs it. The card itself is tiny, so
// it still renders its heading and its sentence while the chunk is in flight --
// and because MapLibre comes with its own stylesheet, deferring the component is
// also what keeps those ~83 kB of CSS off every other page.
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

/** What the drawing claims, said in the heading rather than left to the shape. */
const precisionNote = (seat: SeatLocation): string => {
    switch (seat.precision) {
        case 'building':
            // No radius: a building is drawn as a bare point, and printing
            // "±0 m" next to it would read as a measurement nobody made.
            return 'presná adresa budovy';
        case 'street':
            return `stred ulice · presnosť ${formatRadius(seat.radiusM)}`;
        default:
            return `PSČ ${seat.psc} · presnosť ${formatRadius(seat.radiusM)}`;
    }
};

/**
 * What the drawing means — one sentence per claim, because the claim differs.
 *
 * A sentence that fits one precision is false for the others, and this is not
 * hypothetical: the `postal_code` wording ("the register knows only the PSČ
 * centre, so we cannot place the seat more precisely") was left standing for
 * every seat, so the 85,5 % of companies the register *does* place were told
 * the opposite of what the map beside the sentence was drawing. A building has
 * no ring at all, and a street's ring is that street's own spread rather than
 * the PSČ's.
 */
const explanation = (seat: SeatLocation): React.ReactNode => {
    switch (seat.precision) {
        case 'building':
            return (
                <>
                    Register adries umiestnil sídlo na{' '}
                    <strong className="font-semibold text-gray-700 dark:text-gray-300">skutočný adresný bod tejto firmy</strong>
                    , preto tu je bod a nie kruh: kruh by tvrdil neistotu, ktorá tu nie je.
                </>
            );
        case 'street':
            return (
                <>
                    Kruh je <strong className="font-semibold text-gray-700 dark:text-gray-300">presnosť, nie veľkosť firmy</strong>:
                    v tomto kruhu leží 90 % adries na tejto ulici. Register adries
                    pozná ulicu, ale nie konkrétnu budovu, takže bližšie sídlo
                    umiestniť nevieme.
                </>
            );
        default:
            return (
                <>
                    Kruh je <strong className="font-semibold text-gray-700 dark:text-gray-300">presnosť, nie veľkosť firmy</strong>:
                    v tomto kruhu leží 90 % adries s PSČ {seat.psc}. Register adries pozná
                    len stred PSČ, takže bližšie sídlo umiestniť nevieme.
                </>
            );
    }
};

/**
 * The registered seat, drawn as precisely as the register allows.
 *
 * The sentence under the map is not decoration and is not optional. A circle on
 * a map reads as *the company's grounds* unless something says otherwise, and
 * what it means here is the opposite: the register places the seat somewhere
 * inside it and nowhere more precisely. That is why the radius travels from the
 * API at all (`SeatLocation` in `types.ts`), and why this card shows the number
 * next to the heading instead of leaving it to be inferred from the drawing.
 *
 * Which sentence, though, depends on `precision` — the field `types.ts` declares
 * is decided on the backend rather than guessed here from the radius. Reading it
 * is what keeps the words and the drawing on the same card from disagreeing.
 */
export const SeatLocationCard: React.FC<SeatLocationCardProps> = ({ seat }) => (
    <div className="mt-6 border-t border-gray-200 dark:border-slate-800 pt-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                <i className="fas fa-map-location-dot text-blue-500 dark:text-blue-400" aria-hidden="true" />
                Sídlo na mape
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
                {precisionNote(seat)}
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
            {explanation(seat)}
        </p>
        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
            Zdroj: Register adries MV SR
        </p>
    </div>
);
