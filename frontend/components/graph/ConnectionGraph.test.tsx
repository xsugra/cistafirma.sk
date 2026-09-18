import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
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

/**
 * `GraphCanvas` is where the sizes this component works out become observable:
 * it is the thing being handed `width`, `height` and `focusRect`, and the bug
 * this pins lived entirely on this side of that boundary. Standing in for it
 * also keeps the canvas library -- which wants a real canvas and a real engine
 * -- out of the module graph.
 *
 * It attaches a handle so the `ref` behaves as it does in the app; the specs at
 * the top of this file never reach it, because the container measures 0 x 0
 * there (jsdom has no layout engine) and the `dimensions.width > 0` guard means
 * no canvas is rendered at all.
 */
const canvasProbe = vi.hoisted(() => ({
    props: null as any,
    reset() {
        canvasProbe.props = null;
    },
}));

vi.mock('./GraphCanvas', () => ({
    GraphCanvas: (props: any) => {
        canvasProbe.props = props;
        if (props.ref && typeof props.ref === 'object') {
            props.ref.current = {zoomIn() {}, zoomOut() {}, fitToView() {}, refitIfAuto() {}, exportPng() {}};
        }
        return null;
    },
}));

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

/**
 * jsdom has no layout engine: every `getBoundingClientRect` is 0 x 0, which is
 * precisely the measurement that used to be wrong. These specs put the numbers
 * back -- the ones measured on Home at 393 px (#179) -- so the sizing path can
 * be checked instead of the geometry being taken on faith.
 */
const domRect = (top: number, left: number, width: number, height: number): DOMRect => ({
    top,
    left,
    width,
    height,
    right: left + width,
    bottom: top + height,
    x: left,
    y: top,
    toJSON: () => ({}),
}) as DOMRect;

interface Layout {
    /** The graph's box, in page coordinates. */
    box: DOMRect;
    /** The legend-and-controls strip floating over its top. */
    strip: DOMRect;
    /** The caption at its bottom. */
    caption: DOMRect;
}

/** Measured at 393 px, with the box at the top of the page. */
const PHONE: Layout = {
    box: domRect(0, 0, 359, 639),
    strip: domRect(12, 0, 359, 136),
    caption: domRect(599, 0, 359, 32),
};

/** The same phone, scrolled so only 368 px of the box are on screen. */
const SCROLLED: Layout = {
    box: domRect(400, 0, 359, 639),
    strip: domRect(412, 0, 359, 136),
    caption: domRect(999, 0, 359, 32),
};

/**
 * Answers `getBoundingClientRect` by looking at *which* element is asking.
 *
 * The three elements `ConnectionGraph` measures are identified by their own
 * class lists, which is what the component's markup actually is -- no test ids
 * were added for this. Anything else measures 0 x 0, as in real jsdom.
 */
function withLayout(layout: Layout) {
    const original = Element.prototype.getBoundingClientRect;
    Element.prototype.getBoundingClientRect = function (this: Element) {
        if (this instanceof HTMLParagraphElement) return layout.caption;
        const cls = typeof (this as HTMLElement).className === 'string' ? (this as HTMLElement).className : '';
        if (cls.includes('absolute') && cls.includes('gap-2')) return layout.strip;
        if (cls.includes('h-[75vh]')) return layout.box;
        return domRect(0, 0, 0, 0);
    };
    return () => {
        Element.prototype.getBoundingClientRect = original;
    };
}

/** Patching a prototype is process-wide, so it is undone even if a spec throws. */
let restoreLayout: (() => void) | null = null;

afterEach(() => {
    restoreLayout?.();
    restoreLayout = null;
});

describe('ConnectionGraph — plátno dostane nameranú veľkosť, nie odhad (#179)', () => {
    beforeEach(() => {
        graphMock.data = DATA;
        canvasProbe.reset();
    });

    /**
     * The layout stays installed for the whole spec, not just the render:
     * `focusRect` is a function the canvas calls back at the moment of a fit, so
     * it has to be asked while the elements still measure something.
     */
    const framed = (layout: Layout) => {
        restoreLayout = withLayout(layout);
        renderWithProviders(<ConnectionGraph ico="12345678" />, {route: '/'});
        expect(canvasProbe.props).not.toBeNull();
        return canvasProbe.props;
    };

    it('odovzdá plátnu to, čo kontajner naozaj meria', () => {
        // The regression this whole change is about: `dimensions` started as a
        // hard-coded `{1100, 1000}` and the effect meant to correct it could
        // never run (a null ref on the render that returned the loading branch,
        // and `[isFullscreen]` deps that never changed again). So the canvas was
        // 1100 x 1000 CSS px on every screen for ever -- on this phone, three
        // times the box's width and framing the graph mostly off screen.
        const props = framed(PHONE);
        expect(props.width).toBe(359);
        expect(props.height).toBe(639);
    });

    it('nikdy nedá plátnu menej než podlahu na výšku', () => {
        // A window so short the box measures under the `min-h-[500px]` floor:
        // the canvas keeps its own minimum rather than collapsing.
        const props = framed({...PHONE, box: domRect(0, 0, 359, 120)});
        expect(props.width).toBe(359);
        expect(props.height).toBe(400);
    });

    it('okno na rámovanie je to, čo nie je pod legendou ani pod popisom', () => {
        // 148..599 of the box: the strip's bottom edge to the caption's top
        // edge. 451 px, whose centre is 54 px below the box's own -- which is
        // how far the graph used to be framed away from where the reader was
        // looking.
        const props = framed(PHONE);
        expect(props.focusRect()).toEqual({x: 0, y: 148, width: 359, height: 451});
    });

    it('keď by prekrytia nechali len štrbinu, rámuje sa do viditeľnej časti', () => {
        // Scrolled so 400..768 are on screen: the strip's bottom is at 548 and
        // the caption's top at 999, so honouring both would leave 220 px -- under
        // `MIN_USABLE_WINDOW_PX`. A graph fitted into a slit is worse than one
        // fitted under the legend, so the overlays are dropped.
        const props = framed(SCROLLED);
        expect(props.focusRect()).toEqual({x: 0, y: 0, width: 359, height: 368});
    });

    it('kým box nie je na obrazovke, rámuje sa na celý box', () => {
        // The first load of the company page: the graph is a screen and a half
        // below the fold. Refusing to fit there leaves the graph at the
        // simulation's own spread -- wider than the canvas and clipped by its
        // edge -- until the reader arrives and the debounced refit fires. So
        // the whole box is the window while there is no visible part of it.
        const props = framed({...PHONE, box: domRect(1400, 0, 359, 639),
                              strip: domRect(1412, 0, 359, 136),
                              caption: domRect(1999, 0, 359, 32)});
        expect(props.focusRect()).toEqual({x: 0, y: 0, width: 359, height: 639});
    });

    it('bez merateľného boxu vráti `null`, nie vymyslené číslo', () => {
        // `focusRect` is asked at the moment of a fit, so "cannot measure" is a
        // real state -- and the canvas then frames its whole self, which is what
        // it did before any of this existed. The box is given width but no
        // height, which is the state a display:none ancestor produces and the
        // only one where the canvas is still mounted to be asked.
        const props = framed({...PHONE, box: domRect(0, 0, 359, 0)});
        expect(props.focusRect()).toBeNull();
    });
});
