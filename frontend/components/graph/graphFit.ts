/**
 * Where the connections graph is put: which part of the page counts as "what the
 * reader is looking at", and what zoom and centre put the graph there.
 *
 * Two things are deliberately not used here.
 *
 * **Not `zoomToFit`.** The library's fit measures `getGraphBbox`, which inflates
 * every node to `sqrt(nodeVal) * nodeRelSize`. This graph passes
 * `nodeVal = π·r²` (its discs are *areas*, so that the force engine treats a
 * company as heavier than a person), so a company's bounding radius comes out as
 * `sqrt(π·26²)·4 ≈ 184` graph units for a disc drawn at 26 — about seven times
 * the ink. The graph was therefore fitted to a box mostly made of nothing, and
 * every name sat well inside a frame with a wide margin around it. Here the
 * extent is the *drawn* one: the disc, plus the name pill measured at the font
 * the painter will actually use.
 *
 * **Not the whole canvas.** `zoomToFit` centres on the canvas, and the canvas is
 * not what the reader sees: a legend and a row of controls float over its top
 * (136 px of a 639 px box on a 393 px phone), a caption covers its bottom, and on
 * a short window the box itself is taller than the screen. Fitting to the canvas
 * parks the top of the graph under the legend. `focusWindow` is the part of the
 * box that is both on screen and not under an overlay, and the fit centres the
 * graph on *that*.
 *
 * Pure geometry, no DOM and no canvas: everything it needs is handed in, so it
 * is directly testable.
 */

import { LABEL_FONT_PX, LABEL_GAP_PX } from './graphConfig';
import { labelMetrics } from './labelLayout';

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** A rectangle in page coordinates, as `getBoundingClientRect` reports it. */
export interface PageRect {
  top: number;
  left: number;
  right: number;
  bottom: number;
}

export interface ViewWindow {
  /** The usable part of the graph's box, in pixels from the box's top-left. */
  rect: Rect;
  /**
   * How much of the box's height is on screen at all, 0..1. The reader is
   * considered to be *at* the graph from about a half; below that the graph is
   * scrolling past and re-fitting it would be motion for nothing.
   */
  visibleFraction: number;
}

/**
 * Below this the overlays have eaten the window and are ignored instead: on a
 * 393 px phone held sideways the box is 500 px tall in a 393 px window, and
 * subtracting a 60 px strip and a 16 px caption from the 393 px that are visible
 * leaves 317 px — fine. But on a genuinely short window the two together could
 * leave a slit, and a graph fitted into a slit is worse than one fitted under
 * the legend.
 */
export const MIN_USABLE_WINDOW_PX = 240;

/**
 * The part of the graph's box that is on screen and not under an overlay.
 *
 * `box` and the overlays are in page coordinates; the returned rectangle is
 * relative to the box, which is what the canvas needs — the canvas is drawn at
 * the box's origin.
 */
export function focusWindow(
  box: PageRect,
  viewport: { width: number; height: number },
  overlays: { top?: PageRect | null; bottom?: PageRect | null } = {},
  minUsableHeight: number = MIN_USABLE_WINDOW_PX,
): ViewWindow {
  const visibleTop = Math.max(box.top, 0);
  const visibleBottom = Math.min(box.bottom, viewport.height);
  const visibleLeft = Math.max(box.left, 0);
  const visibleRight = Math.min(box.right, viewport.width);

  const boxHeight = Math.max(box.bottom - box.top, 1);
  const visibleHeight = Math.max(visibleBottom - visibleTop, 0);
  const visibleWidth = Math.max(visibleRight - visibleLeft, 0);
  const visibleFraction = visibleWidth <= 0 ? 0 : Math.min(1, visibleHeight / boxHeight);

  // The overlays float inside the box, so they can only ever take more away.
  let top = visibleTop;
  let bottom = visibleBottom;
  if (overlays.top) top = Math.max(top, overlays.top.bottom);
  if (overlays.bottom) bottom = Math.min(bottom, overlays.bottom.top);
  if (bottom - top < minUsableHeight) {
    top = visibleTop;
    bottom = visibleBottom;
  }

  return {
    rect: {
      x: visibleLeft - box.left,
      y: top - box.top,
      width: visibleWidth,
      height: Math.max(bottom - top, 0),
    },
    visibleFraction,
  };
}

export interface FitNode {
  x: number;
  y: number;
  /** Drawn radius in graph units — `NODE_SIZES`, not `nodeVal`. */
  radius: number;
  kind: 'company' | 'person';
  label: string;
  bold: boolean;
}

/** Measures a label's width in screen pixels at the painter's font. */
export type MeasureLabel = (text: string, bold: boolean) => number;

export interface FitOptions {
  /** Breathing room inside the window, in pixels. */
  padding: number;
  minZoom: number;
  maxZoom: number;
}

export interface FitTransform {
  zoom: number;
  /** The graph coordinate that lands at the *window's* centre. */
  centerX: number;
  centerY: number;
}

/** A graph position, or `null` for the ones the engine has not placed yet. */
function placed(node: FitNode): boolean {
  return Number.isFinite(node.x) && Number.isFinite(node.y);
}

interface Extent {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

/**
 * The drawn extent, in screen pixels, for a candidate zoom.
 *
 * The discs scale with the zoom while the labels do not — the painter divides
 * the font by the zoom precisely so that a name stays 13 px on screen — so the
 * extent is not a rectangle that simply scales, and it is computed here rather
 * than solved for in closed form.
 */
function extentAt(nodes: readonly FitNode[], widths: readonly number[], zoom: number): Extent {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    const cx = node.x * zoom;
    const cy = node.y * zoom;
    const radius = node.radius * zoom;

    // The pill, exactly as `labelLayout` builds it for a graph scale of 1:
    // measured text plus 3 px of padding on each side, 13 px of text plus 1,5 px
    // top and bottom, anchored so its top edge sits `gap - padY` below the disc.
    const metrics = labelMetrics(widths[i], LABEL_FONT_PX, 1);
    const halfWidth = Math.max(radius, metrics.w / 2);
    const labelTop = cy + radius + LABEL_GAP_PX[node.kind] - metrics.padY;

    if (cx - halfWidth < minX) minX = cx - halfWidth;
    if (cx + halfWidth > maxX) maxX = cx + halfWidth;
    if (cy - radius < minY) minY = cy - radius;
    if (labelTop + metrics.h > maxY) maxY = labelTop + metrics.h;
  }

  return { minX, maxX, minY, maxY };
}

/**
 * The zoom and centre that put the drawn graph inside `rect`.
 *
 * `canvas` is the canvas's own size in CSS pixels, because the centre is
 * expressed in the library's terms: the graph coordinate that lands at the
 * canvas centre. Since the window's centre is generally not the canvas's centre
 * (that is the whole point — the legend covers the top of it), the two are
 * converted through the zoom.
 *
 * The extent grows with the zoom and is never negative, so the search is a
 * bisection on a monotone predicate rather than a formula with a
 * scale-dependent term in it.
 */
export function fitTransform(
  nodes: readonly FitNode[],
  measureLabel: MeasureLabel,
  rect: Rect,
  canvas: { width: number; height: number },
  options: FitOptions,
): FitTransform | null {
  const drawable = nodes.filter(placed);
  if (drawable.length === 0) return null;

  const availableWidth = rect.width - options.padding * 2;
  const availableHeight = rect.height - options.padding * 2;
  if (availableWidth <= 0 || availableHeight <= 0) return null;

  const widths = drawable.map(node => measureLabel(node.label, node.bold));

  // The epsilon is for floating point, not for slack: it has to be small enough
  // that the fit is genuinely tight, because "the graph fills the window" is the
  // property that makes this worth doing rather than the library's `zoomToFit`.
  const eps = 1e-6;
  const fits = (zoom: number) => {
    const { minX, maxX, minY, maxY } = extentAt(drawable, widths, zoom);
    return maxX - minX <= availableWidth + eps && maxY - minY <= availableHeight + eps;
  };

  let zoom: number;
  if (fits(options.maxZoom)) {
    zoom = options.maxZoom;
  } else {
    // Invariant: `low` may or may not fit (a graph too large for the window at
    // the smallest zoom is clamped, not refused), `high` never does.
    let low = options.minZoom;
    let high = options.maxZoom;
    for (let i = 0; i < 48; i++) {
      const mid = (low + high) / 2;
      if (fits(mid)) low = mid;
      else high = mid;
    }
    zoom = low;
  }

  const { minX, maxX, minY, maxY } = extentAt(drawable, widths, zoom);
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;

  return {
    zoom,
    centerX: (centerX + canvas.width / 2 - (rect.x + rect.width / 2)) / zoom,
    centerY: (centerY + canvas.height / 2 - (rect.y + rect.height / 2)) / zoom,
  };
}
