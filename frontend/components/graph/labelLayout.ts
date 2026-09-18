/**
 * Label placement for the connections graph, as pure geometry.
 *
 * This module exists because label drawing used to be decided *while* nodes were
 * being drawn: a label was skipped if it collided with one already drawn in the
 * same pass, the pass order was `data.nodes` order, and the "is this a new
 * frame?" reset was a wall-clock guess evaluated once per node. Whether a name
 * appeared therefore depended on paint time, on node order and on the hardware —
 * and because the canvas stops redrawing once the simulation settles, the wrong
 * answer stayed frozen on screen until the reader moved the zoom.
 *
 * Placement is now a pure function of the requests: same input, same output, on
 * every machine. Nothing here touches the DOM, React or a canvas, so it is
 * directly testable — which the graph previously had no cover for at all.
 */

export interface LabelRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export type LabelKind = 'company' | 'person';

export interface LabelRequest {
  id: string;
  text: string;
  kind: LabelKind;
  /** Anchor: pill centre on x, text top on y (the canvas uses `textBaseline = 'top'`). */
  x: number;
  y: number;
  fontSize: number;
  bold: boolean;
  /** Lower goes first, so it wins a collision. See `LABEL_PRIORITY`. */
  priority: number;
  /** Connections in the graph. A tiebreak, and what makes the order stable. */
  degree: number;
  /** Drawn even when it collides. True only for the centre of the graph. */
  alwaysDraw: boolean;
}

export interface PlacedLabel extends LabelRequest {
  /** Where the pill goes. Computed once, here, and consumed as-is by the draw. */
  rect: LabelRect;
  /** The size actually used — may be a step down the ladder from `fontSize`. */
  usedFontSize: number;
}

/**
 * Lower wins. The centre is the node the reader navigated to, so it keeps its
 * name; a hovered node is the one under the pointer, so it is next.
 */
export const LABEL_PRIORITY = { center: 0, hovered: 1, rest: 2 } as const;

/**
 * A colliding label is shrunk before it is dropped, and dropped only if even the
 * smallest step collides. The steps are the dial on how many names still need a
 * zoom: fewer steps, more names lost. 0.75 rather than 0.8 because a 20 % shrink
 * usually does not clear a real collision.
 *
 * On screen this is a constant ~13 px stepping down to ~9.75 px, because
 * `fontSize` is inversely proportional to the zoom — a shrunken label is never
 * unreadably small, it is only smaller than its neighbours.
 */
export const LABEL_SIZE_STEPS = [1, 0.75] as const;

export const LABEL_FONT_FAMILY = "'Inter', sans-serif";

/** The one place the label font string is built, so measure and draw cannot disagree. */
export function labelFont(fontSize: number, bold: boolean): string {
  return `${bold ? 'bold ' : '500 '}${fontSize}px ${LABEL_FONT_FAMILY}`;
}

/** Measures the rendered width of `text` in the label font at `fontSize`. */
export type MeasureWidth = (text: string, fontSize: number, bold: boolean) => number;

export interface LabelMetrics {
  w: number;
  h: number;
  padY: number;
}

export function labelMetrics(textWidth: number, fontSize: number, globalScale: number): LabelMetrics {
  const padX = 3 / globalScale;
  const padY = 1.5 / globalScale;
  return { w: textWidth + padX * 2, h: fontSize + padY * 2, padY };
}

/**
 * The pill's rectangle for an anchor. The draw puts the pill at
 * `(x - w / 2, y - padY)`, so the overlap test must use exactly that — testing
 * `y` while drawing `y - padY` left every comparison off by `padY`, which was
 * harmless while the rectangle was only advisory and is not harmless now that
 * the decision rests on it.
 */
export function rectFor(x: number, y: number, metrics: LabelMetrics): LabelRect {
  return { x: x - metrics.w / 2, y: y - metrics.padY, w: metrics.w, h: metrics.h };
}

/**
 * True when `a` and `b` overlap, or come within `padding` of each other. The
 * comparison is strict, so a gap of exactly `padding` still counts as an
 * overlap — that is the spacing the graph had before this module existed and it
 * is kept on purpose.
 */
export function rectsOverlap(a: LabelRect, b: LabelRect, padding: number): boolean {
  return !(
    a.x + a.w + padding < b.x ||
    b.x + b.w + padding < a.x ||
    a.y + a.h + padding < b.y ||
    b.y + b.h + padding < a.y
  );
}

/**
 * A total order, so the same graph always yields the same set of names. Node
 * order from the API is deliberately absent from it: it changes on every
 * expansion, which is what made the losing label move around.
 */
export function compareLabels(a: LabelRequest, b: LabelRequest): number {
  if (a.priority !== b.priority) return a.priority - b.priority;
  if (a.degree !== b.degree) return b.degree - a.degree;
  if (a.kind !== b.kind) return a.kind === 'company' ? -1 : 1;
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

function place(
  request: LabelRequest,
  usedFontSize: number,
  measureWidth: MeasureWidth,
  globalScale: number,
): PlacedLabel {
  const metrics = labelMetrics(measureWidth(request.text, usedFontSize, request.bold), usedFontSize, globalScale);
  return { ...request, rect: rectFor(request.x, request.y, metrics), usedFontSize };
}

export interface LayoutResult {
  placed: PlacedLabel[];
  /** Names that collided at every step and are therefore not drawn. */
  dropped: number;
}

/**
 * Chooses which labels to draw and where. Walks the total order and gives each
 * label the largest step on the ladder that does not collide with one already
 * placed.
 */
export function layoutLabels(
  requests: readonly LabelRequest[],
  measureWidth: MeasureWidth,
  globalScale: number,
  padding: number,
  steps: readonly number[] = LABEL_SIZE_STEPS,
): LayoutResult {
  const placed: PlacedLabel[] = [];
  let dropped = 0;

  for (const request of [...requests].sort(compareLabels)) {
    if (request.alwaysDraw) {
      placed.push(place(request, request.fontSize * steps[0], measureWidth, globalScale));
      continue;
    }

    let chosen: PlacedLabel | null = null;
    for (const step of steps) {
      const candidate = place(request, request.fontSize * step, measureWidth, globalScale);
      if (!placed.some(p => rectsOverlap(candidate.rect, p.rect, padding))) {
        chosen = candidate;
        break;
      }
    }

    if (chosen) placed.push(chosen);
    else dropped += 1;
  }

  return { placed, dropped };
}
