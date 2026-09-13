import {describe, expect, it, vi, beforeEach} from 'vitest';
import {render, screen, waitFor} from '@testing-library/react';
import {SeatLocationCard, formatRadius} from './SeatLocationCard';
import type {SeatLocation} from '../../types';

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
        render(<SeatLocationCard seat={seat} />);

        const precision = screen.getByText(/· presnosť/);
        expect(precision).toHaveTextContent('PSČ 82109');
        expect(precision).toHaveTextContent('±737 m');
    });

    it('says the circle is precision rather than the size of the company', () => {
        // The reading this guards against is "the company owns everything inside
        // the circle". So the card has to name what covers what: 90 % of the
        // addresses sharing this PSČ.
        render(<SeatLocationCard seat={seat} />);

        expect(screen.getByText('presnosť, nie veľkosť firmy')).toBeInTheDocument();
        expect(screen.getByText(/90 % adries s PSČ 82109/)).toBeInTheDocument();
    });

    it('will not let the sentence drift from the PSČ being drawn', () => {
        render(<SeatLocationCard seat={{...seat, psc: '04001', radiusM: 4118}} />);

        const precision = screen.getByText(/· presnosť/);
        expect(precision).toHaveTextContent('PSČ 04001');
        expect(precision).toHaveTextContent('±4,1 km');
        expect(screen.getByText(/90 % adries s PSČ 04001/)).toBeInTheDocument();
        expect(screen.queryByText(/82109/)).not.toBeInTheDocument();
    });

    it('hands the whole seat to the map, radius included', async () => {
        // A card that dropped `radiusM` would still draw something, and the
        // drawing would claim a point the data does not support.
        render(<SeatLocationCard seat={seat} />);

        await waitFor(() => expect(map.seats.length).toBeGreaterThan(0));
        expect(map.seats.at(-1)).toEqual(seat);
    });

    it('names where the position comes from', () => {
        render(<SeatLocationCard seat={seat} />);

        expect(screen.getByText(/Register adries MV SR/)).toBeInTheDocument();
    });

    it('does not tell a building seat about a circle the map does not draw', () => {
        // The failure this guards against is the card and the map on it saying
        // opposite things: `SeatMap` draws a building as a bare point, so a
        // sentence about "this circle", and the reason it gives -- that the
        // register knows only the PSČ centre -- are both false here. The
        // register is precisely what placed it on the building.
        render(<SeatLocationCard seat={{...seat, radiusM: 0, precision: 'building'}} />);

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
        render(<SeatLocationCard seat={{...seat, radiusM: 184, precision: 'street'}} />);

        const precision = screen.getByText(/· presnosť/);
        expect(precision).toHaveTextContent('stred ulice');
        expect(precision).toHaveTextContent('±184 m');
        expect(screen.getByText(/90 % adries na tejto ulici/)).toBeInTheDocument();
        expect(screen.queryByText(/s PSČ 82109/)).not.toBeInTheDocument();
    });
});
