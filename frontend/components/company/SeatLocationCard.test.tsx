import {describe, expect, it, vi, beforeEach} from 'vitest';
import {render, screen, waitFor} from '@testing-library/react';
import {SeatLocationCard, formatRadius, mapsLink} from './SeatLocationCard';
import type {Address, SeatLocation} from '../../types';

/**
 * The map is mocked, and the boundary is deliberate: what this card owes the
 * reader is the radius and the sentence that explains it, not the drawing itself.
 * A test that mounted the real map would need a WebGL context and a laid-out
 * container that jsdom does not have, and would say nothing about the two things
 * that can actually be wrong here -- a radius that never reaches the drawing, and
 * a sentence that does not say what the circle means.
 */
const map = vi.hoisted(() => ({seats: [] as SeatLocation[]}));

vi.mock('./SeatMap', () => ({
    SeatMap: (props: {seat: SeatLocation}) => {
        map.seats.push(props.seat);
        return null;
    },
}));

const seat: SeatLocation = {
    lat: 48.14748,
    lon: 17.14051,
    radiusM: 737,
    psc: '82109',
    precision: 'postal_code',
};

const address: Address = {
    street: 'Mlynské nivy 5',
    city: 'Bratislava',
    zipCode: '82109',
    country: 'SK',
};

describe('formatRadius', () => {
    it('keeps metres below a kilometre and switches to kilometres above it', () => {
        // The stored radii run 50 m (a street's floor, `MIN_STREET_RADIUS_M`)
        // to 8 717 m (the widest PSČ), so both branches are ordinary values
        // here rather than edge cases.
        expect(formatRadius(270)).toBe('±270 m');
        expect(formatRadius(737)).toBe('±737 m');
        expect(formatRadius(1000)).toBe('±1,0 km');
        expect(formatRadius(4118)).toBe('±4,1 km');
        expect(formatRadius(8717)).toBe('±8,7 km');
    });

    it('writes the decimal comma Slovak uses, not the dot', () => {
        expect(formatRadius(1200)).toBe('±1,2 km');
    });
});

describe('SeatLocationCard', () => {
    beforeEach(() => {
        map.seats.length = 0;
    });

    it('states the precision as a number, not only as a circle', () => {
        // Nothing on a map tells the reader whether the circle is 300 m or 8 km
        // across, and that difference is the whole honesty of the feature.
        render(<SeatLocationCard seat={seat} address={address} />);

        const precision = screen.getByText(/· presnosť/);
        expect(precision).toHaveTextContent('PSČ 82109');
        expect(precision).toHaveTextContent('±737 m');
    });

    it('says the circle is precision rather than the size of the company', () => {
        // The reading this guards against is "the company owns everything inside
        // the circle". So the card has to name what covers what: 90 % of the
        // addresses sharing this PSČ.
        render(<SeatLocationCard seat={seat} address={address} />);

        expect(screen.getByText('presnosť, nie veľkosť firmy')).toBeInTheDocument();
        expect(screen.getByText(/90 % adries s PSČ 82109/)).toBeInTheDocument();
    });

    it('will not let the sentence drift from the PSČ being drawn', () => {
        render(<SeatLocationCard seat={{...seat, psc: '04001', radiusM: 4118}} address={address} />);

        const precision = screen.getByText(/· presnosť/);
        expect(precision).toHaveTextContent('PSČ 04001');
        expect(precision).toHaveTextContent('±4,1 km');
        expect(screen.getByText(/90 % adries s PSČ 04001/)).toBeInTheDocument();
        expect(screen.queryByText(/82109/)).not.toBeInTheDocument();
    });

    it('hands the whole seat to the map, radius included', async () => {
        // A card that dropped `radiusM` would still draw something, and the
        // drawing would claim a point the data does not support.
        render(<SeatLocationCard seat={seat} address={address} />);

        await waitFor(() => expect(map.seats.length).toBeGreaterThan(0));
        expect(map.seats.at(-1)).toEqual(seat);
    });

    it('names where the position comes from', () => {
        render(<SeatLocationCard seat={seat} address={address} />);

        expect(screen.getByText(/Register adries MV SR/)).toBeInTheDocument();
    });

    it('does not tell a building seat about a circle the map does not draw', () => {
        // The failure this guards against is the card and the map on it saying
        // opposite things: `SeatMap` draws a building as a bare point, so a
        // sentence about "this circle", and the reason it gives -- that the
        // register knows only the PSČ centre -- are both false here. The
        // register is precisely what placed it on the building.
        render(<SeatLocationCard seat={{...seat, radiusM: 0, precision: 'building'}} address={address} />);

        expect(screen.getByText('presná adresa budovy')).toBeInTheDocument();
        expect(screen.getByText(/skutočný adresný bod/)).toBeInTheDocument();
        expect(screen.queryByText(/90 % adries/)).not.toBeInTheDocument();
        // A radius of 0 printed as a measurement would read as "we measured it".
        expect(screen.queryByText(/±0 m/)).not.toBeInTheDocument();
    });

    it('gives a street seat the street\'s own radius, not the PSČ\'s', () => {
        // A street ring is that street's spread. Saying "90 % of the addresses
        // with PSČ 82109" would put the PSČ's number on the street's circle --
        // the two are different populations and different widths.
        render(<SeatLocationCard seat={{...seat, radiusM: 184, precision: 'street'}} address={address} />);

        const precision = screen.getByText(/· presnosť/);
        expect(precision).toHaveTextContent('stred ulice');
        expect(precision).toHaveTextContent('±184 m');
        expect(screen.getByText(/90 % adries na tejto ulici/)).toBeInTheDocument();
        expect(screen.queryByText(/s PSČ 82109/)).not.toBeInTheDocument();
    });

    it('offers Google from an anchor that opens in a new tab', () => {
        // An `<a>` rather than a `<button>`: the reader keeps middle-click and
        // "open in new tab", and the card's own map stays where it is -- which is
        // the point of a card that draws the seat rather than a map application.
        render(<SeatLocationCard seat={{...seat, radiusM: 0, precision: 'building'}} address={address} />);

        const link = screen.getByRole('link', {name: /Vypočítať trasu/});
        expect(link).toHaveAttribute(
            'href',
            'https://www.google.com/maps/dir/?api=1&destination=48.14748,17.14051',
        );
        expect(link).toHaveAttribute('target', '_blank');
        expect(link).toHaveAttribute('rel', 'noreferrer noopener');
    });
});

describe('mapsLink', () => {
    it('asks Google for a route to the exact point when the seat is a building', () => {
        // The register gave us the building's own address point, so this is the
        // one precision where a route's destination is a place rather than an
        // average -- and it goes as a coordinate, because a geocoder handed our
        // address string can land at the other end of a long street.
        const link = mapsLink({...seat, radiusM: 0, precision: 'building'}, address);

        expect(link.href).toBe(
            'https://www.google.com/maps/dir/?api=1&destination=48.14748,17.14051',
        );
        expect(link.label).toBe('Vypočítať trasu');
    });

    it('never routes to the centre of an area, because that centre is an average', () => {
        // The failure this guards against is the link contradicting the ring
        // drawn an inch above it: "somewhere inside this" on the map, "here it
        // is" in the URL. The coordinates must therefore not appear in the link
        // at all, for either area precision.
        for (const precision of ['street', 'postal_code'] as const) {
            const link = mapsLink({...seat, radiusM: 184, precision}, address);

            expect(link.href).not.toContain(String(seat.lat));
            expect(link.href).not.toContain(String(seat.lon));
            expect(link.href).toContain('/maps/search/');
            expect(link.label).toBe('Nájsť na Google Maps');
        }
    });

    it('hands an area the address we hold, encoded, and says why it is a search', () => {
        const link = mapsLink({...seat, precision: 'street'}, address);

        expect(link.href).toBe(
            'https://www.google.com/maps/search/?api=1&query=' +
                encodeURIComponent('Mlynské nivy 5, 82109 Bratislava'),
        );
        // The reader gets the reason, so the two buttons differ in more than
        // their wording.
        expect(link.title).toMatch(/nie konkrétnu budovu/);
    });

    it('still has something to search with when the record carries no street', () => {
        // 943 949 of the register's own address points are rural and carry no
        // street at all, so an empty `street` is an ordinary case rather than a
        // bug -- and "06601 Humenné" is still a query Google answers.
        const link = mapsLink(
            {...seat, precision: 'postal_code'},
            {...address, street: '', city: 'Humenné', zipCode: '06601'},
        );

        expect(link.href).toContain(encodeURIComponent('06601 Humenné'));
        expect(link.href).not.toContain('-,');
    });
});
