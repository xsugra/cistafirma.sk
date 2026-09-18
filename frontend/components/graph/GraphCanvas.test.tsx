import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {act, render} from '@testing-library/react';
import {createRef, type Ref} from 'react';
import {LABEL_FONT_PX, LABEL_GAP_PX} from './graphConfig';
import {labelMetrics} from './labelLayout';
import {ThemeProvider} from '../../context/ThemeContext';
import type {GraphData, GraphNode} from './graphTypes';
import type {GraphCanvasHandle} from './GraphCanvas';
import type {Rect} from './graphFit';

/**
 * `react-force-graph-2d` is replaced by a probe that only records the props it
 * was handed. The canvas callbacks are then driven by hand, which is what makes
 * the *sequence* observable: the point of the fix is that node chrome and labels
 * are painted in two separate passes, and that is a claim about call order, not
 * about pixels.
 *
 * It also stands in for the library's own object, because the framing half of
 * the component is a conversation with that object: `centerAt` and `zoom` are
 * the whole output of a fit, and what the reader did to the view afterwards is
 * read back through the same two getters. The fake keeps the transform the
 * setters were given, which is exactly what a real instance does once its tween
 * has finished — so a test can watch the fit and then decide whether it was
 * left alone.
 *
 * `vi.hoisted` because `vi.mock` is lifted above these declarations.
 */
const probe = vi.hoisted(() => {
    class FakeGraph {
        k = 1;
        cx = 0;
        cy = 0;
        calls: {op: 'zoom' | 'centerAt'; args: any[]}[] = [];

        zoom(k?: number) {
            if (k === undefined) return this.k;
            this.calls.push({op: 'zoom', args: [k]});
            this.k = k;
            return this;
        }

        centerAt(x?: number, y?: number) {
            if (x === undefined) return {x: this.cx, y: this.cy};
            this.calls.push({op: 'centerAt', args: [x, y]});
            this.cx = x;
            this.cy = y;
            return this;
        }

        d3Force() {
            const chain = {strength: () => chain, distance: () => chain, iterations: () => chain};
            return chain;
        }

        /** The transform the last `centerAt` + `zoom` pair asked for. */
        get target() {
            const zoom = [...this.calls].reverse().find(c => c.op === 'zoom');
            const centre = [...this.calls].reverse().find(c => c.op === 'centerAt');
            return zoom && centre ? {zoom: zoom.args[0], centerX: centre.args[0], centerY: centre.args[1]} : null;
        }

        /** What the reader is looking at now — changed by the test, not by a fit. */
        movesTo(x: number, y: number, k = this.k) {
            this.cx = x;
            this.cy = y;
            this.k = k;
        }
    }

    const state = {
        props: null as any,
        instance: null as FakeGraph | null,
        make() {
            return new FakeGraph();
        },
        reset() {
            state.props = null;
            state.instance = null;
        },
    };
    return state;
});

vi.mock('react-force-graph-2d', () => ({
    default: (props: any) => {
        probe.props = props;
        if (!probe.instance) probe.instance = probe.make();
        // React 19 hands `ref` to a function component as a plain prop, so the
        // fake attaches itself — which is what a real instance does through its
        // own `useImperativeHandle`.
        if (props.ref && typeof props.ref === 'object') props.ref.current = probe.instance;
        return null;
    },
}));

const {GraphCanvas} = await import('./GraphCanvas');

interface Call {
    op: string;
    args: any[];
}

/**
 * A 2D context that remembers what was done to it, in order. Only the methods
 * the canvas code actually reaches for are implemented; everything else about a
 * real context (rasterising, transforms) is irrelevant to call order.
 */
function fakeCtx() {
    const calls: Call[] = [];
    const push = (op: string) => (...args: any[]) => {
        calls.push({op, args});
    };
    const ctx: any = {
        calls,
        save: push('save'),
        restore: push('restore'),
        beginPath: push('beginPath'),
        arc: push('arc'),
        ellipse: push('ellipse'),
        fill: push('fill'),
        stroke: push('stroke'),
        fillRect: push('fillRect'),
        roundRect: push('roundRect'),
        moveTo: push('moveTo'),
        lineTo: push('lineTo'),
        setLineDash: push('setLineDash'),
        translate: push('translate'),
        rotate: push('rotate'),
        // Reads the font that was just set, as a real context does: a smaller
        // step must measure narrower, or the shrink in the layout is invisible
        // to the test and the ladder can never be observed clearing a collision.
        measureText: (text: string) => {
            const size = Number(/([\d.]+)px/.exec(ctx.font ?? '')?.[1] ?? 10);
            return {width: text.length * size * 0.6};
        },
        fillText: (text: string, x: number, y: number) =>
            calls.push({op: 'fillText', args: [text, x, y, ctx.font]}),
    };
    return ctx;
}

/** The text of every label actually painted, in paint order. */
const labelsOf = (ctx: any): string[] =>
    ctx.calls.filter((c: Call) => c.op === 'fillText').map((c: Call) => c.args[0]);

const fontOf = (ctx: any, text: string): string =>
    ctx.calls.find((c: Call) => c.op === 'fillText' && c.args[0] === text).args[3];

function company(id: string, x: number, over: Partial<GraphNode> = {}): GraphNode {
    return {id, type: 'company', label: `${id} s.r.o.`, x, y: 0, rolesCount: 0, ...over};
}

function mount(nodes: GraphNode[], centerNode: string | null = null, onNodeHover = vi.fn()) {
    const data: GraphData = {nodes, links: []};
    render(
        <ThemeProvider>
            <GraphCanvas
                data={data}
                centerNode={centerNode}
                onNodeClick={vi.fn()}
                onNodeHover={onNodeHover}
                width={800}
                height={600}
            />
        </ThemeProvider>,
    );
    return onNodeHover;
}

/** One redraw, exactly as `force-graph` performs it. */
function paintFrame(ctx: any, globalScale = 1) {
    probe.props.onRenderFramePre(ctx, globalScale);
    for (const node of probe.props.graphData.nodes) {
        probe.props.nodeCanvasObject(node, ctx, globalScale);
    }
    probe.props.onRenderFramePost(ctx, globalScale);
}

/** The canvas size every framing spec below measures against. */
const CANVAS = {width: 359, height: 639};

/**
 * The usable part of the graph's box on a 393 px phone, measured on Home
 * (#179): the legend-and-controls strip covers y 12..148 and the caption
 * y 599..631, so 148..599 is what is left — 451 px whose centre sits 54 px
 * below the canvas's own.
 */
const PHONE_WINDOW: Rect = {x: 0, y: 148, width: 359, height: 451};

/**
 * Module-level so the identity is stable. `fitToRect` closes over `focusRect`,
 * and the effect that arms the first automatic fit depends on `fitToRect` — an
 * inline arrow would be a new function on every render and re-arm the timer,
 * which is a bug in a test that counts calls.
 */
const windowOf = (rect: Rect) => () => rect;
const NO_WINDOW = () => null;

/** Half the pill's drop below its disc: how far the ink's centre sits below the node's. */
const PILL = labelMetrics(0, LABEL_FONT_PX, 1);
const INK_CENTRE_BELOW_NODE = (LABEL_GAP_PX.company - PILL.padY + PILL.h) / 2;

function mountFramed(
    nodes: GraphNode[],
    focusRect: () => Rect | null,
    ref?: Ref<GraphCanvasHandle>,
) {
    const data: GraphData = {nodes, links: []};
    render(
        <ThemeProvider>
            <GraphCanvas
                ref={ref}
                data={data}
                centerNode={null}
                onNodeClick={vi.fn()}
                onNodeHover={vi.fn()}
                {...CANVAS}
                focusRect={focusRect}
            />
        </ThemeProvider>,
    );
}

/** Let every timer the component armed run out. */
const settle = (ms: number) =>
    act(async () => {
        await vi.advanceTimersByTimeAsync(ms);
    });

describe('GraphCanvas label painting', () => {
    it('paints every name after all node chrome, so no node can cover one', () => {
        mount([company('aaa', 0), company('bbb', 400)]);
        const ctx = fakeCtx();
        paintFrame(ctx);

        expect(labelsOf(ctx)).toEqual(['aaa s.r.o.', 'bbb s.r.o.']);

        // This is the regression. Nodes used to be drawn and labelled in one
        // pass, each node's opaque disc and glow landing on top of whatever the
        // node before it had already written. Every name must now come after
        // every disc.
        const firstLabel = ctx.calls.findIndex((c: Call) => c.op === 'fillText');
        const lastDisc = ctx.calls.map((c: Call) => c.op).lastIndexOf('arc');
        expect(lastDisc).toBeLessThan(firstLabel);
    });

    it('picks the same name however the nodes are ordered', () => {
        // Two nodes close enough that their pills collide, so only one name can
        // be shown. The degree decides which — `aaa` has more connections.
        const aaa = company('aaa', 0, {rolesCount: 5});
        const bbb = company('bbb', 20);

        mount([aaa, bbb]);
        const forward = fakeCtx();
        paintFrame(forward);

        mount([bbb, aaa]);
        const backward = fakeCtx();
        paintFrame(backward);

        expect(labelsOf(forward)).toEqual(['aaa s.r.o.']);
        // The old code decided by paint order, so reversing the node list
        // reversed the winner and the graph looked different after every
        // expansion. A total order makes the answer independent of arrival.
        expect(labelsOf(backward)).toEqual(labelsOf(forward));
    });

    it('lets a hovered name win over a better-connected neighbour', () => {
        const aaa = company('aaa', 0, {rolesCount: 5});
        const bbb = company('bbb', 20);
        mount([aaa, bbb]);

        const before = fakeCtx();
        paintFrame(before);
        expect(labelsOf(before)).toEqual(['aaa s.r.o.']);

        act(() => probe.props.onNodeHover(bbb));

        const after = fakeCtx();
        paintFrame(after);
        // The pointer is on `bbb`, so its name is the one worth the space.
        expect(labelsOf(after)).toEqual(['bbb s.r.o.']);
    });

    it('always paints the name of the node the graph is centred on', () => {
        const aaa = company('aaa', 0, {rolesCount: 5});
        const bbb = company('bbb', 20);
        mount([aaa, bbb], 'bbb');

        const ctx = fakeCtx();
        paintFrame(ctx);

        // The centre collides with a better-connected neighbour and is drawn
        // anyway, and first — it is the node the reader navigated to.
        expect(labelsOf(ctx)).toEqual(['bbb s.r.o.']);
        const first = ctx.calls.find((c: Call) => c.op === 'fillText');
        expect(first.args[2]).toBeGreaterThan(0); // positioned below its node
    });

    it('shrinks a colliding name rather than losing it', () => {
        // "aaa s.r.o." is 10 characters (the trailing dot counts), so at 13px the
        // pill is 10 * 13 * 0.6 + 6 = 84 wide and at 9.75px it is 64.5. Two centres
        // 80 apart collide at full size — clearing needs more than 42 + 42 + 2 =
        // 86 — and fit once the second shrinks, which needs only 42 + 32.25 + 2 =
        // 76.25.
        const aaa = company('aaa', 0);
        const bbb = company('bbb', 80);

        mount([aaa, bbb]);
        const ctx = fakeCtx();
        paintFrame(ctx);

        expect(labelsOf(ctx)).toEqual(['aaa s.r.o.', 'bbb s.r.o.']);
        expect(fontOf(ctx, 'aaa s.r.o.')).toContain('13px');
        expect(fontOf(ctx, 'bbb s.r.o.')).toContain('9.75px');
    });

    it('draws a name once per frame, not once per node visit', () => {
        mount([company('aaa', 0), company('bbb', 400)]);
        const ctx = fakeCtx();
        paintFrame(ctx);
        paintFrame(ctx);

        // The buffer is emptied at the frame boundary, so a second frame is a
        // second frame — not a growing pile of labels from every frame so far.
        expect(labelsOf(ctx)).toEqual(['aaa s.r.o.', 'bbb s.r.o.', 'aaa s.r.o.', 'bbb s.r.o.']);
    });

    it('does not leak canvas state out of a label', () => {
        mount([company('aaa', 0)]);
        const ctx = fakeCtx();
        paintFrame(ctx);

        // `drawLabel` used to be the one draw helper with no save/restore, so it
        // left `textAlign`, `textBaseline` and `fillStyle` set for whatever was
        // drawn next — including the link labels, which then inherited them.
        const labelSave = ctx.calls.findIndex((c: Call) => c.op === 'fillText');
        const save = ctx.calls.slice(0, labelSave).map((c: Call) => c.op).lastIndexOf('save');
        const restore = ctx.calls.findIndex((c: Call, i: number) => i > labelSave && c.op === 'restore');
        expect(save).toBeGreaterThanOrEqual(0);
        expect(restore).toBeGreaterThan(labelSave);
    });
});

/**
 * The arithmetic of a fit lives in `graphFit.test.ts`, against `fitTransform`
 * directly. What is checked here is the wiring around it: that the component
 * asks `ConnectionGraph` where the reader is looking and frames *that*, that it
 * tells its own fit apart from the reader's hand, and that the ⟲ hands the
 * framing back.
 */
describe('GraphCanvas — rámovanie do okna, ktoré je vidieť (#179)', () => {
    const nodes = [company('aaa', -300), company('bbb', 300)];

    beforeEach(() => {
        probe.reset();
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    /** The transform the component last asked the library for. */
    const fitted = () => (probe.instance as any)?.target ?? null;

    /**
     * Where the middle of the ink ends up on screen for a transform. The ink's
     * own centre is `INK_CENTRE_BELOW_NODE` below graph y = 0 — half the pill's
     * drop under a disc — and the transform then places graph y = 0 at
     * `canvasCentre - centerY * zoom`.
     */
    const inkCentreY = (fit: {centerY: number; zoom: number}) =>
        INK_CENTRE_BELOW_NODE + CANVAS.height / 2 - fit.centerY * fit.zoom;

    it('sám zarámuje graf do okna, ktoré mu ConnectionGraph odovzdá', async () => {
        mountFramed(nodes, windowOf(PHONE_WINDOW));
        await settle(1100);

        const fit = fitted();
        expect(fit).not.toBeNull();

        // The claim, in one line: the middle of the ink lands on the middle of
        // what the reader can see. Framing the canvas instead would have put it
        // at 319,5 — 54 px higher, under the legend. That 54 px is the measured
        // distance between the canvas's centre and the usable window's.
        expect(inkCentreY(fit)).toBeCloseTo(PHONE_WINDOW.y + PHONE_WINDOW.height / 2, 1);
        expect(CANVAS.height / 2).toBe(319.5);

        // The two nodes are symmetric about x = 0 and their names are the same
        // length, so the window's centre is already the ink's — nothing to shift.
        expect(fit.centerX).toBeCloseTo(0, 6);
    });

    it('posun okna posunie kresbu o presne ten istý posun', async () => {
        // Same size, so the same available space and the same zoom; only the
        // offset differs. Whatever the fit does, it must be a pure function of
        // where the reader is looking.
        const higher: Rect = {...PHONE_WINDOW, y: 0};
        expect(higher.height).toBe(PHONE_WINDOW.height);

        mountFramed(nodes, windowOf(higher));
        await settle(1100);
        const a = fitted();

        probe.reset();
        mountFramed(nodes, windowOf(PHONE_WINDOW));
        await settle(1100);
        const b = fitted();

        expect(a.zoom).toBeCloseTo(b.zoom, 6);
        // 148 px lower on the canvas, and the ink follows it down by 148 px.
        expect(inkCentreY(b) - inkCentreY(a)).toBeCloseTo(PHONE_WINDOW.y, 1);
    });

    it('keď sa okno nedá zmerať, rámuje celé plátno — ako predtým', async () => {
        mountFramed(nodes, NO_WINDOW);
        await settle(1100);
        const fallback = fitted();

        probe.reset();
        mountFramed(nodes, windowOf({x: 0, y: 0, ...CANVAS}));
        await settle(1100);
        const whole = fitted();

        expect(fallback).not.toBeNull();
        expect(fallback.zoom).toBeCloseTo(whole.zoom, 6);
        expect(fallback.centerY).toBeCloseTo(whole.centerY, 6);
        expect(fallback.centerX).toBeCloseTo(whole.centerX, 6);
    });

    it('fit, ktorý nikto nepohol, ostáva aktívny', async () => {
        const ref = createRef<GraphCanvasHandle>();
        mountFramed(nodes, windowOf(PHONE_WINDOW), ref);
        await settle(1100);

        const fg = probe.instance as any;
        const before = fg.calls.length;

        // d3-zoom fires `end` for a programmatic transition on every frame of it,
        // so an `end` on its own cannot mean "the reader moved the view". The
        // transform is the judge, and after the tween it is exactly what the fit
        // asked for.
        act(() => probe.props.onZoomEnd());
        act(() => ref.current!.refitIfAuto());

        // One `centerAt` and one `zoom`.
        expect(fg.calls.length - before).toBe(2);
    });

    it('keď človek pohne grafom, samo sa nevráti — a ⟲ to vráti', async () => {
        const ref = createRef<GraphCanvasHandle>();
        mountFramed(nodes, windowOf(PHONE_WINDOW), ref);
        await settle(1100);

        const fg = probe.instance as any;

        act(() => {
            // A pan and a zoom-in, which is what a gesture leaves behind. Not
            // recorded as a fit — the fake only records what the component asked
            // for, and this is the reader.
            fg.movesTo(5000, 5000, 1.3);
            probe.props.onZoomEnd();
        });

        const before = fg.calls.length;
        act(() => ref.current!.refitIfAuto());
        expect(fg.calls.length).toBe(before);

        act(() => ref.current!.fitToView());
        expect(fg.calls.length).toBeGreaterThan(before);
        expect(fg.k).toBeCloseTo(fitted().zoom, 6);
    });

    it('premiestnenie uzla rukou rámovanie tiež vypne', async () => {
        // A drag reheats the engine, so without this the view would slide back
        // to the middle as soon as the reader let go of the node.
        const ref = createRef<GraphCanvasHandle>();
        mountFramed(nodes, windowOf(PHONE_WINDOW), ref);
        await settle(1100);

        const fg = probe.instance as any;
        act(() => probe.props.onNodeDrag());

        const before = fg.calls.length;
        act(() => ref.current!.refitIfAuto());
        expect(fg.calls.length).toBe(before);

        act(() => ref.current!.fitToView());
        expect(fg.calls.length).toBeGreaterThan(before);
    });
});
