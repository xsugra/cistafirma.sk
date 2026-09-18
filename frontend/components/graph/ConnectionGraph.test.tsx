import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen} from '@testing-library/react';
import {renderWithProviders} from '../../test/testUtils';
import type {GraphData} from './graphTypes';

const graphMock = vi.hoisted(() => ({data: null as unknown}));

vi.mock('./useGraphData', () => ({
    useGraphData: () => ({
        graphData: graphMock.data,
        loading: false,
        error: null,
        fetchGraph: vi.fn(),
        expandNode: vi.fn(),
        expandPerson: vi.fn(),
        centerNode: vi.fn(),
        truncated: false,
    }),
}));

// `GraphCanvas` pulls in `react-force-graph-2d`, which wants a real canvas. It
// is never reached here -- the container measures 0 x 0 in jsdom, so the
// `dimensions.width > 0` guard skips it -- but the import still runs at module
// load, so the mock keeps the module graph loadable.
vi.mock('react-force-graph-2d', () => ({default: () => null}));

const {ConnectionGraph} = await import('./ConnectionGraph');

const DATA: GraphData = {
    nodes: [
        {id: 'company_1', type: 'company', label: 'ACME s.r.o.', ico: '12345678'},
        {id: 'person_1', type: 'person', label: 'Ján Novák'},
    ],
    links: [],
};

/**
 * The legend and the controls used to be two independent `absolute` corners.
 * Measured: at 393 px the legend spanned x 53..352 and the controls x 116..340,
 * both starting at y 37, so the controls were painted over the legend's
 * right-hand items and hid them; at 900 px the same thing happened at the
 * legend's second row. Two absolutes in one corner cannot see each other, so
 * the fix is structural and that is what these specs pin.
 */
describe('ConnectionGraph — legenda a ovládanie sa neprekrývajú (#176, krok 4)', () => {
    beforeEach(() => {
        graphMock.data = DATA;
    });

    const strip = () => {
        const legend = screen.getByText('Konateľ').closest('div.flex-wrap')!;
        const controls = screen.getByTitle('Priblížiť').closest('div.pointer-events-auto')!;
        const legendWrapper = legend.parentElement!;
        const controlsWrapper = controls.parentElement!;
        // The claim: one shared parent, i.e. one flex strip rather than two
        // absolutely positioned boxes that happen to share a corner.
        expect(controlsWrapper.parentElement).toBe(legendWrapper.parentElement);
        return {
            strip: legendWrapper.parentElement!,
            legendWrapper,
            controlsWrapper,
        };
    };

    it('obidve sedia v jednom flex kontajneri, nie v dvoch absolútnych rohoch', () => {
        renderWithProviders(<ConnectionGraph ico="12345678" />, {route: '/'});
        const s = strip();
        expect(s.strip).toHaveClass('absolute', 'flex', 'gap-2', 'md:flex-row', 'md:justify-between');
    });

    it('na telefóne idú ovládanie a legenda pod seba, ovládanie prvé', () => {
        // A column cannot overlap, whatever the content widths are -- which is
        // what makes this hold at 393 px without a magic offset per element.
        renderWithProviders(<ConnectionGraph ico="12345678" />, {route: '/'});
        const s = strip();
        expect(s.strip).toHaveClass('flex-col');
        expect(s.legendWrapper).toHaveClass('order-2', 'md:order-1');
        expect(s.controlsWrapper).toHaveClass('order-1', 'md:order-2');
    });

    it('od `md` vyššie sedia na jednom riadku na opačných koncoch', () => {
        renderWithProviders(<ConnectionGraph ico="12345678" />, {route: '/'});
        const s = strip();
        // `md:flex-1` + `min-w-0` is what lets the legend shrink and wrap
        // instead of running under the controls.
        expect(s.legendWrapper).toHaveClass('min-w-0', 'md:flex-1');
        expect(s.controlsWrapper).toHaveClass('md:flex-none');
    });
});
