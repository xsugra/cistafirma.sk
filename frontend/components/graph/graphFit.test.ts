import {describe, expect, it} from 'vitest';
import {FIT_CONFIG, LABEL_FONT_PX, LABEL_GAP_PX} from './graphConfig';
import {
    MIN_USABLE_WINDOW_PX,
    fitTransform,
    focusWindow,
    type FitNode,
    type FitTransform,
    type Rect,
} from './graphFit';
import {labelMetrics} from './labelLayout';

/**
 * A stand-in for `measureText`, and deliberately not the real one: the point of
 * these specs is the arithmetic, and 8 px a character makes the label wide
 * enough that the disk is not always the thing that binds.
 */
const measure = (text: string, bold: boolean) => text.length * 8 * (bold ? 1.15 : 1);

const company = (x: number, y: number, label = 'A', over: Partial<FitNode> = {}): FitNode => ({
    x,
    y,
    radius: 26,
    kind: 'company',
    label,
    bold: false,
    ...over,
});

/** Page coordinates, as `getBoundingClientRect` reports them. */
const box = (top: number, left: number, width: number, height: number) => ({
    top,
    left,
    right: left + width,
    bottom: top + height,
});

/**
 * Where a graph coordinate lands on the canvas once the fit is applied — the
 * library's own mapping (`centerAt` puts the named coordinate at the canvas
 * centre, the zoom scales about it), re-derived here rather than copied from the
 * module under test.
 */
function project(fit: FitTransform, canvas: {width: number; height: number}, x: number, y: number) {
    const tx = canvas.width / 2 - fit.centerX * fit.zoom;
    const ty = canvas.height / 2 - fit.centerY * fit.zoom;
    return {x: x * fit.zoom + tx, y: y * fit.zoom + ty};
}

/**
 * One node's ink on screen: the disc, unioned with the pill the painter draws
 * under it. Built from `labelMetrics` and `LABEL_GAP_PX` — the same constants
 * the fit reads — but through its own arithmetic, so it checks the fit rather
 * than agreeing with it.
 */
function inkOf(node: FitNode, fit: FitTransform, canvas: {width: number; height: number}) {
    const c = project(fit, canvas, node.x, node.y);
    const r = node.radius * fit.zoom;
    const m = labelMetrics(measure(node.label, node.bold), LABEL_FONT_PX, 1);
    return {
        left: Math.min(c.x - r, c.x - m.w / 2),
        right: Math.max(c.x + r, c.x + m.w / 2),
        top: c.y - r,
        bottom: Math.max(c.y + r, c.y + r + LABEL_GAP_PX[node.kind] - m.padY + m.h),
    };
}

function inkBounds(nodes: readonly FitNode[], fit: FitTransform, canvas: {width: number; height: number}) {
    const boxes = nodes.map(n => inkOf(n, fit, canvas));
    return {
        left: Math.min(...boxes.map(b => b.left)),
        right: Math.max(...boxes.map(b => b.right)),
        top: Math.min(...boxes.map(b => b.top)),
        bottom: Math.max(...boxes.map(b => b.bottom)),
    };
}

describe('focusWindow — čo používateľ naozaj vidí', () => {
    const viewport = {width: 393, height: 852};

    it('meria okno od rohu plátna, nie od stránky', () => {
        // The box sits 100 px down the page. The canvas is drawn at the box's
        // origin, so everything after this is relative to that corner -- an
        // absolute page coordinate here would offset every fit by 100 px.
        const {rect, visibleFraction} = focusWindow(box(100, 0, 359, 639), viewport);
        expect(rect).toEqual({x: 0, y: 0, width: 359, height: 639});
        expect(visibleFraction).toBe(1);
    });

    it('odpočíta legendu hore a popis dolu — nameraných 451 px, stred +54 px', () => {
        // Measured on Home at 393 px (#179): the legend-and-controls strip
        // covers container-local y 12..148, the caption y 599..631. What is left
        // is 451 px whose centre is 54 px below the box's own centre -- which is
        // exactly how far down the graph used to be framed from where the reader
        // was looking.
        const {rect} = focusWindow(
            box(100, 0, 359, 639),
            viewport,
            {top: box(112, 0, 359, 136), bottom: box(699, 0, 359, 32)},
        );

        expect(rect).toEqual({x: 0, y: 148, width: 359, height: 451});

        const windowCentre = rect.y + rect.height / 2;
        const boxCentre = 639 / 2;
        expect(windowCentre - boxCentre).toBeCloseTo(54, 5);
    });

    it('odpočíta aj vodorovné odrezanie oknom', () => {
        // A box that starts off the left edge: the graph cannot be framed in the
        // part of itself that is off screen, so the window starts *inside* the
        // box -- 40 px in, because that is where the box's edge meets the
        // viewport's.
        const {rect} = focusWindow(box(0, -40, 500, 400), {width: 393, height: 393});
        expect(rect.x).toBe(40);
        expect(rect.width).toBe(393);
        expect(rect.y).toBe(0);
        expect(rect.height).toBe(393);
    });

    it('hlási, koľko z boxu je na obrazovke', () => {
        // Half the box has been scrolled past.
        const {visibleFraction} = focusWindow(box(400, 0, 359, 639), viewport);
        expect(visibleFraction).toBeCloseTo((852 - 400) / 639, 5);
    });

    it('keď by prekrytia nechali len štrbinu, ignoruje ich', () => {
        // A window 300 px tall with a 200 px strip and a 20 px caption: taking
        // both away leaves 80 px, which is worse than framing under the strip.
        // The two subtractions are 200 and 20, and what is left of 300 is 80.
        expect(300 - 200 - 20).toBeLessThan(MIN_USABLE_WINDOW_PX);

        const {rect} = focusWindow(
            box(0, 0, 359, 500),
            {width: 359, height: 300},
            {top: box(0, 0, 359, 200), bottom: box(280, 0, 359, 20)},
        );

        // The overlays are dropped, not honoured: the whole visible height.
        expect(rect).toEqual({x: 0, y: 0, width: 359, height: 300});
    });
});

describe('fitTransform — graf sa zmestí do toho, čo je vidieť', () => {
    const rect = {x: 0, y: 148, width: 359, height: 451};
    const canvas = {width: 359, height: 639};
    /** 311 x 403 after `padding`. */
    const available = {
        left: rect.x + FIT_CONFIG.padding,
        top: rect.y + FIT_CONFIG.padding,
        right: rect.x + rect.width - FIT_CONFIG.padding,
        bottom: rect.y + rect.height - FIT_CONFIG.padding,
    };

    const three = [company(-300, 0), company(0, 0), company(300, 0)];

    it('rámuje kresbu, nie sedemnásťnásobnú bbox knižnice', () => {
        const fit = fitTransform(three, measure, rect, canvas, FIT_CONFIG)!;
        const ink = inkBounds(three, fit, canvas);

        // Tight: the ink fills the window's width, less the padding.
        expect(ink.right - ink.left).toBeCloseTo(available.right - available.left, 1);

        // And that is a *much* tighter zoom than `zoomToFit` would have chosen.
        // `force-graph` inflates every node to `sqrt(nodeVal) * nodeRelSize`,
        // which for this graph (nodeVal = pi*r^2, nodeRelSize = 4) is 184.3 graph
        // units of bounding radius for a disc drawn at 26 -- so the library would
        // have fitted 600 + 2*184.3 units into the same 311 px, a zoom of 0.321,
        // and left the names floating in a wide empty margin.
        const libraryZoom = (available.right - available.left) / (600 + 2 * (Math.sqrt(Math.PI * 26 * 26) * 4));
        expect(libraryZoom).toBeLessThan(0.34);
        expect(fit.zoom).toBeGreaterThan(0.42);
    });

    it('stred kresby dá do stredu okna, nie do stredu plátna', () => {
        const fit = fitTransform(three, measure, rect, canvas, FIT_CONFIG)!;
        const ink = inkBounds(three, fit, canvas);

        expect((ink.left + ink.right) / 2).toBeCloseTo(rect.x + rect.width / 2, 1);
        expect((ink.top + ink.bottom) / 2).toBeCloseTo(rect.y + rect.height / 2, 1);

        // The canvas's own centre is 54 px above the window's, which is the
        // whole point: framing on the canvas parks the graph under the legend.
        expect((ink.top + ink.bottom) / 2 - canvas.height / 2).toBeCloseTo(54, 1);
    });

    it('zmestí sa do okna aj na výšku, keď je kresba vysoká', () => {
        // Two tall stacks: the extent is height-bound, so the clamping has to
        // come from the height and not only from the width.
        const tall = [company(0, -400), company(0, 400)];
        const fit = fitTransform(tall, measure, rect, canvas, FIT_CONFIG)!;
        const ink = inkBounds(tall, fit, canvas);

        expect(ink.top).toBeGreaterThanOrEqual(available.top - 0.5);
        expect(ink.bottom).toBeLessThanOrEqual(available.bottom + 0.5);
        expect(ink.bottom - ink.top).toBeCloseTo(available.bottom - available.top, 1);
    });

    it('dvojicu uzlov nezväčší do nemožna, ale zastaví ju na maxZoom', () => {
        const fit = fitTransform([company(0, 0)], measure, rect, canvas, FIT_CONFIG)!;
        expect(fit.zoom).toBe(FIT_CONFIG.maxZoom);
    });

    it('graf, ktorý sa nezmestí ani pri minZoom, oreže — neodmietne', () => {
        // Refusing here would leave the graph unframed for ever, which is worse
        // than framing most of it.
        const huge = [company(-50000, 0), company(50000, 0)];
        const fit = fitTransform(huge, measure, rect, canvas, FIT_CONFIG)!;
        expect(fit.zoom).toBe(FIT_CONFIG.minZoom);
    });

    it('počíta s menovkou, ktorá sa so zoomom nemení', () => {
        // The painter divides the font by the zoom so a name stays 13 px on
        // screen. The discs therefore shrink as the reader zooms out but the
        // pills do not -- so the same graph of long names has to be zoomed out
        // further than the graph of short ones, however small the discs become.
        //
        // 31 characters is 254 px of pill at 8 px a character; the two nodes are
        // 300 graph units apart, so at any zoom the pills are what the width is
        // spent on and the discs never bind. (That is the point: with the
        // library's own fit the pills are not in the bbox at all, and both
        // graphs would have been given the same zoom.)
        const LONG = 'Spoločnosť s ručením obmedzeným';
        expect(LONG).toHaveLength(31);

        const apart = [company(-150, 0), company(150, 0)];
        const short = fitTransform(apart, measure, rect, canvas, FIT_CONFIG)!;
        const long = fitTransform(
            apart.map(n => company(n.x, n.y, LONG)),
            measure,
            rect,
            canvas,
            FIT_CONFIG,
        )!;

        expect(short.zoom).toBeGreaterThan(long.zoom * 2);

        // And the long-label fit is still tight -- it is not tight only because
        // it gave up and clamped.
        expect(long.zoom).toBeGreaterThan(FIT_CONFIG.minZoom);
        const ink = inkBounds(apart.map(n => company(n.x, n.y, LONG)), long, canvas);
        expect(ink.right - ink.left).toBeCloseTo(available.right - available.left, 1);
    });

    it('keď sú menovky širšie než okno, rámujú sa disky a menovky prečnievajú', () => {
        // The regression this exists for, at the size it was measured: a real
        // company's graph is 114 nodes whose longest name is 124 characters, and
        // on a 393 px phone the window is 311 px wide. Requiring such names to be
        // inside is unsatisfiable at *every* zoom, so the bisection returned
        // `minZoom` and the live page drew 26-unit discs 0.52 px across. The
        // same shape in miniature: two 60-character names, 480 px of pill each.
        const LONG = 'S'.repeat(60);
        const apart = [company(-150, 0, LONG), company(150, 0, LONG)];
        const fit = fitTransform(apart, measure, rect, canvas, FIT_CONFIG)!;

        // Not clamped: the fit is a real zoom that shows the discs.
        expect(fit.zoom).toBeGreaterThan(FIT_CONFIG.minZoom);
        // 300 units apart, two discs of 26 -> 352 units of ink into 311 px.
        expect(fit.zoom).toBeCloseTo(311 / 352, 3);

        // The discs alone fill the window's width exactly -- tight, as before.
        const discLeft = project(fit, canvas, -150, 0).x - 26 * fit.zoom;
        const discRight = project(fit, canvas, 150, 0).x + 26 * fit.zoom;
        expect(discRight - discLeft).toBeCloseTo(available.right - available.left, 1);
        // And they sit inside it, not on top of the padding.
        expect(discLeft).toBeGreaterThanOrEqual(available.left - 0.5);
        expect(discRight).toBeLessThanOrEqual(available.right + 0.5);

        const ink = inkBounds(apart, fit, canvas);

        // And the cost is stated rather than hidden: the names do overhang the
        // window. `labelLayout` shrinks and drops colliding names, so an
        // overhanging name is one the reader may lose -- which is what makes this
        // strictly better than drawing the whole graph half a pixel wide.
        expect(ink.left).toBeLessThan(available.left);
        expect(ink.right).toBeGreaterThan(available.right);
    });

    it('keď sa menovky nezmestia do šírky, na výšku sa stále počítajú', () => {
        // The fallback drops the names from the *horizontal* extent only. A name
        // hangs below its disc by a bounded ~18 px of screen, so the bottom row of
        // names still gets its room -- otherwise the fallback would clip every
        // name on the lowest disc, which is a cost it does not have to pay.
        const LONG = 'S'.repeat(60);
        const vertical = [company(0, -150, LONG), company(0, 150, LONG)];
        const fit = fitTransform(vertical, measure, rect, canvas, FIT_CONFIG)!;
        expect(fit.zoom).toBeGreaterThan(FIT_CONFIG.minZoom);

        // 300 units of span plus two discs is 352 units of height; the lowest
        // name sits a further `LABEL_GAP - padY + h` = 19.5 px below its disc.
        expect(fit.zoom).toBeCloseTo((available.bottom - available.top - 19.5) / 352, 3);

        const ink = inkBounds(vertical, fit, canvas);
        expect(ink.bottom).toBeLessThanOrEqual(available.bottom + 0.5);
        expect(ink.bottom).toBeCloseTo(available.bottom, 1);
    });

    it('ignoruje uzly, ktoré engine ešte neumiestnil', () => {
        const unplaced = [company(0, 0), {x: undefined as unknown as number, y: 0, radius: 26, kind: 'company' as const, label: 'nikde', bold: false}];
        const fit = fitTransform(unplaced, measure, rect, canvas, FIT_CONFIG);
        expect(fit).not.toBeNull();

        // One placed node and nothing else: the same answer as for that node
        // alone, which is what "the unplaced one was skipped" means.
        const alone = fitTransform([company(0, 0)], measure, rect, canvas, FIT_CONFIG)!;
        expect(fit!.zoom).toBe(alone.zoom);
    });

    it('vráti null, keď niet čo rámovať alebo kde', () => {
        expect(fitTransform([], measure, rect, canvas, FIT_CONFIG)).toBeNull();
        expect(
            fitTransform([{x: undefined as unknown as number, y: 0, radius: 26, kind: 'company', label: 'a', bold: false}], measure, rect, canvas, FIT_CONFIG),
        ).toBeNull();

        // A window narrower than twice the padding has no interior to fit into.
        const sliver: Rect = {x: 0, y: 0, width: FIT_CONFIG.padding * 2 - 1, height: 400};
        expect(fitTransform(three, measure, sliver, canvas, FIT_CONFIG)).toBeNull();
    });
});
