import React, { lazy, Suspense } from 'react';
import type { Address, SeatLocation } from '../../types';
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

/**
 * The address string we hand Google, built the same way for both verbs.
 *
 * `street` already carries the house number when there is one -- the register
 * writes "Žilinská cesta 126", not a number in a field of its own -- so this is
 * the whole address and not just its first line.
 */
const addressQuery = (address: Address): string =>
    [address.street, [address.zipCode, address.city].filter(Boolean).join(' ')]
        .map((part) => part.trim())
        .filter(Boolean)
        .join(', ');

/**
 * The Google link, and what it is allowed to say it does.
 *
 * Two verbs, because a route and a search are not the same promise. A `building`
 * is one point on a doorstep, so Google can be asked for a route *to* it. A
 * `street` or a PSČ is an area, and the only point we could hand a router is that
 * area's centroid -- the average this card exists to present as an average. A
 * route there would name the middle of a street as the firm's doorstep, which is
 * the same claim the ring is drawn to refuse. So an area gets a *search*: Google
 * receives the address we hold, disambiguates it itself, and puts a pin on the
 * street the reader can route from. The `title` carries the reason, so the
 * difference between the two buttons is not silent.
 *
 * Both verbs carry the *address*. The building branch used to carry a
 * coordinate, and that is the version that failed. Handed
 * `destination=48.6030256,17.8305999`, Google does not show that point -- it
 * reverse-geocodes it and names the destination after whatever business it
 * knows there. For ECOKLIMA s.r.o. (IČO 48097781) that was "poctive sirupy
 * s.r.o., Žilinská 126, 921 01 Piešťany": a different company's name printed at
 * the end of a route to this one. The point itself was never wrong -- the
 * register's address point for Žilinská cesta 126 is that building, and a
 * reverse lookup confirms it -- so the reader was shown a stranger's name on a
 * correct route, which reads exactly like being sent to the wrong place. Nor
 * was it one company's bad luck: any address point that coincides with a
 * business Google knows picks up that business's name, and 288 966 of our seats
 * sit on such points.
 *
 * The address is safe to hand over *here* because of what `building` means: it
 * is the precision the register reaches only with a house number, so the string
 * names a building rather than a street. Measured 2026-09-15 across all 361 527
 * building-precision seats: every one carries a number in `Ulica` -- the 16 640
 * a first count set aside are `10A`, `4B`, `50E`, number and letter -- and not
 * one is a bare street name. Nor is that text a transcription we are merely
 * hoping is right: `building` is the tier the register reached *by resolving
 * this very string* to a house number, so an address that did not name a real
 * building could not have produced the point we are standing on. That is also
 * why the argument this branch used to give for sending a coordinate ("a
 * geocoder handed our address string can land at the other end of a long
 * street") does not apply to it: it is an argument about streets, and this
 * branch is the one that has house numbers.
 */
export const mapsLink = (
    seat: SeatLocation,
    address: Address,
): { href: string; label: string; icon: string; title: string } => {
    const query = addressQuery(address);

    if (seat.precision === 'building') {
        return {
            href: `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(query)}`,
            label: 'Vypočítať trasu',
            icon: 'fa-diamond-turn-right',
            title: 'Trasa na adresu sídla, ktorú uvádza Register adries',
        };
    }

    return {
        href: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`,
        label: 'Nájsť na Google Maps',
        icon: 'fa-magnifying-glass-location',
        title:
            'Register pozná ulicu alebo PSČ, ale nie konkrétnu budovu — preto Google ' +
            'otvárame s adresou na vyhľadanie, nie s trasou do presného bodu',
    };
};

interface SeatLocationCardProps {
    seat: SeatLocation;
    /**
     * The address as the rest of the profile prints it.
     *
     * Needed only for the link above: a seat drawn as an area has no point worth
     * routing to, and the street name is what Google can be asked to find. Passed
     * in rather than added to `SeatLocation`, because it is a fact about the
     * company record rather than a property of the drawing.
     */
    address: Address;
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
export const SeatLocationCard: React.FC<SeatLocationCardProps> = ({ seat, address }) => {
    const link = mapsLink(seat, address);

    return (
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
            {/* The source and the way out, on one line: the reader who has just
                been told how precise the drawing is is the reader who wants to go
                there, and the credit belongs under the map it credits. It wraps to
                two lines on a narrow card rather than squeezing either half. */}
            <div className="mt-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                <p className="text-xs text-gray-400 dark:text-gray-500">
                    Zdroj: Register adries MV SR
                </p>
                {/* An `<a>`, not a `<button>`: it navigates, so it keeps
                    middle-click, ⌘-click and "open in new tab". The label changes
                    with the precision because the promise does. */}
                <a
                    href={link.href}
                    target="_blank"
                    rel="noreferrer noopener"
                    title={link.title}
                    className="inline-flex items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 transition-colors hover:border-blue-300 hover:bg-blue-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300 dark:hover:border-blue-800 dark:hover:bg-blue-900/50"
                >
                    <i className={`fas ${link.icon}`} aria-hidden="true" />
                    {link.label}
                    <span className="sr-only"> (otvorí sa v novej karte)</span>
                </a>
            </div>
        </div>
    );
};
