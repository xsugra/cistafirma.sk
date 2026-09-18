import {describe, expect, it, vi} from 'vitest';
import {act, render} from '@testing-library/react';
import {ThemeProvider} from '../../context/ThemeContext';
import type {GraphData, GraphNode} from './graphTypes';

/**
 * `react-force-graph-2d` is replaced by a probe that only records the props it
 * was handed. The canvas callbacks are then driven by hand, which is what makes
 * the *sequence* observable: the point of the fix is that node chrome and labels
 * are painted in two separate passes, and that is a claim about call order, not
 * about pixels.
 *
 * `vi.hoisted` because `vi.mock` is lifted above these declarations.
 */
const probe = vi.hoisted(() => ({props: null as any}));

vi.mock('react-force-graph-2d', () => ({
    default: (props: any) => {
        probe.props = props;
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
