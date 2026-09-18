import { useRef, useState, useCallback, useEffect, useImperativeHandle, forwardRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { forceCollide } from 'd3-force-3d';
import { useTheme } from '../../context/ThemeContext';
import {
  FIT_CONFIG,
  FORCE_CONFIG,
  GRAPH_COLORS,
  GRAPH_COLORS_DARK,
  LABEL_FONT_PX,
  LABEL_GAP_PX,
  NODE_SIZES,
} from './graphConfig';
import { fitTransform, type FitTransform, type Rect } from './graphFit';
import {
  LABEL_PRIORITY,
  labelFont,
  layoutLabels,
  type LabelKind,
  type LabelRequest,
  type PlacedLabel,
} from './labelLayout';
import type { GraphData, GraphNode } from './graphTypes';

export interface GraphCanvasHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  /** Frame the graph in what the reader can see, and keep doing so. */
  fitToView: () => void;
  /** The same, but only while the reader has not taken the view over. */
  refitIfAuto: () => void;
  exportPng: () => void;
}

interface GraphCanvasProps {
  data: GraphData;
  centerNode: string | null;
  onNodeClick: (node: GraphNode) => void;
  onNodeHover: (node: GraphNode | null) => void;
  width: number;
  height: number;
  /**
   * The part of the canvas the reader can actually see, in canvas pixels —
   * asked for at the moment of a fit, so it is always current. `null` means the
   * whole canvas, which is what it degrades to when no measurement is available.
   */
  focusRect?: () => Rect | null;
}

/**
 * How long after an automatic fit to judge whether it was left alone. The
 * animation itself is `FIT_CONFIG.duration`; the margin covers the tween's last
 * frame and the timeout's own scheduling.
 */
const FIT_SETTLE_MARGIN_MS = 120;

/**
 * A 2D context kept only to measure text, so that the fit budgets for the pill
 * the painter will draw rather than for a guess at it. `undefined` is "not
 * looked for yet" and `null` is jsdom, which has no 2D context at all.
 */
let measureCtx: CanvasRenderingContext2D | null | undefined;

function measureLabelWidth(text: string, bold: boolean): number {
  if (measureCtx === undefined) {
    measureCtx = document.createElement('canvas').getContext('2d');
  }
  if (!measureCtx) {
    // No canvas in this environment (jsdom). An average glyph is a little over
    // half the font size, which is close enough for an extent nothing will be
    // tested against here.
    return text.length * LABEL_FONT_PX * 0.55;
  }
  measureCtx.font = labelFont(LABEL_FONT_PX, bold);
  return measureCtx.measureText(text).width;
}

/** Is the view where an automatic fit left it? */
function transformMatches(fg: any, target: FitTransform): boolean {
  const zoom = fg.zoom();
  const center = fg.centerAt();
  if (typeof zoom !== 'number' || !center) return false;
  if (Math.abs(zoom - target.zoom) > Math.max(0.002, target.zoom * 0.01)) return false;
  // Two pixels on screen, whatever the zoom — a pan the reader would notice.
  return (
    Math.abs(center.x - target.centerX) * zoom <= 2 &&
    Math.abs(center.y - target.centerY) * zoom <= 2
  );
}

function drawBuildingIcon(ctx: CanvasRenderingContext2D, cx: number, cy: number, size: number, color: string) {
  const s = size;
  ctx.save();
  ctx.fillStyle = color;

  const bw = s * 0.6;
  const bh = s * 0.75;
  const bx = cx - bw / 2;
  const by = cy - bh / 2;
  ctx.fillRect(bx, by, bw, bh);

  ctx.fillStyle = 'rgba(0,0,0,0.3)';
  const winSize = s * 0.1;
  const gap = s * 0.07;
  const cols = 3;
  const rows = 3;
  const totalW = cols * winSize + (cols - 1) * gap;
  const startX = cx - totalW / 2;
  const startY = by + s * 0.1;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      ctx.fillRect(
        startX + c * (winSize + gap),
        startY + r * (winSize + gap * 1.3),
        winSize, winSize,
      );
    }
  }
  ctx.restore();
}

function drawPersonIcon(ctx: CanvasRenderingContext2D, cx: number, cy: number, size: number, color: string) {
  ctx.save();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(cx, cy - size * 0.17, size * 0.2, 0, 2 * Math.PI);
  ctx.fill();
  ctx.beginPath();
  ctx.ellipse(cx, cy + size * 0.22, size * 0.3, size * 0.22, 0, Math.PI, 0, true);
  ctx.fill();
  ctx.restore();
}

function drawCircleNode(
  ctx: CanvasRenderingContext2D,
  x: number, y: number,
  radius: number,
  bgColor: string,
  strokeColor: string,
  glowColor: string,
  globalScale: number,
  isCenter: boolean,
  centerStroke: string,
  centerGlow: string,
) {
  ctx.save();

  if (isCenter) {
    ctx.shadowColor = centerGlow;
    ctx.shadowBlur = 18 / globalScale;
  } else {
    ctx.shadowColor = glowColor;
    ctx.shadowBlur = 8 / globalScale;
  }
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, 2 * Math.PI);
  ctx.fillStyle = bgColor;
  ctx.fill();
  ctx.shadowBlur = 0;

  ctx.lineWidth = isCenter ? 3 / globalScale : 1.5 / globalScale;
  ctx.strokeStyle = isCenter ? centerStroke : strokeColor;
  ctx.stroke();

  if (isCenter) {
    ctx.beginPath();
    ctx.arc(x, y, radius + 4 / globalScale, 0, 2 * Math.PI);
    ctx.strokeStyle = centerStroke;
    ctx.lineWidth = 1.5 / globalScale;
    ctx.setLineDash([3 / globalScale, 3 / globalScale]);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.restore();
}

/**
 * Draws a label the layout has already placed. It consumes `label.rect` exactly
 * rather than recomputing the pill, so the rectangle the collision test used and
 * the rectangle on screen cannot drift apart — they are the same number.
 */
function drawLabel(
  ctx: CanvasRenderingContext2D,
  label: PlacedLabel,
  textColor: string,
  bgColor: string,
  globalScale: number,
) {
  ctx.save();
  ctx.font = labelFont(label.usedFontSize, label.bold);

  ctx.fillStyle = bgColor;
  ctx.beginPath();
  ctx.roundRect(label.rect.x, label.rect.y, label.rect.w, label.rect.h, 3 / globalScale);
  ctx.fill();

  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.fillStyle = textColor;
  ctx.fillText(label.text, label.x, label.y);

  ctx.restore();
}

function labelColor(kind: LabelKind, isDark: boolean): string {
  if (kind === 'company') return isDark ? '#93C5FD' : '#1E40AF';
  return isDark ? '#D1D5DB' : '#374151';
}

function getRoleAbbrev(role: string): string {
  const map: Record<string, string> = {
    'Konateľ': 'Konateľ',
    'Spoločník': 'Spoločník',
    'Prokurista': 'Prokurista',
    'Predstavenstvo': 'Predst.',
    'Dozorná rada': 'Doz. rada',
    'Akcionár': 'Akcionár',
    'Iné': 'Iné',
  };
  return map[role] || role;
}

export const GraphCanvas = forwardRef<GraphCanvasHandle, GraphCanvasProps>(function GraphCanvas(
  { data, centerNode, onNodeClick, onNodeHover, width, height, focusRect }, ref
) {
  const fgRef = useRef<any>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const { isDark } = useTheme();
  const colors = isDark ? GRAPH_COLORS_DARK : GRAPH_COLORS;
  const labelBg = isDark ? 'rgba(2, 6, 23, 0.85)' : 'rgba(255, 255, 255, 0.88)';

  const [hoveredId, setHoveredId] = useState<string | null>(null);

  /**
   * Whether the graph may still frame itself. The reader's own pan or zoom turns
   * this off — nothing is more irritating than a view that re-centres itself
   * every time you move it — and the ⟲ button turns it back on.
   */
  const autoFitRef = useRef(true);
  /** What the last automatic fit aimed at, and the judge of who moved the view. */
  const lastFitRef = useRef<FitTransform | null>(null);
  const settleTimerRef = useRef<number | null>(null);

  /**
   * Labels are collected while the nodes are drawn and placed afterwards, once
   * per frame — see `clearPendingLabels` / `paintLabels` below. A ref, not
   * state: this is written on every frame and must never trigger a re-render.
   */
  const pendingLabelsRef = useRef<LabelRequest[]>([]);

  /**
   * Frame the drawn graph in the reader's window.
   *
   * `fitTransform` does the arithmetic; this is the half that talks to the
   * library and, more importantly, the half that decides whether the reader has
   * since moved the view themselves. d3-zoom emits its `end` event for a
   * programmatic transition exactly as it does for a gesture — during a 400 ms
   * tween it fires on every frame — so the events cannot say who moved the view.
   * What can: the transform the animation was aiming at, compared once it has
   * finished. Anything else in that seat is the reader.
   */
  const fitToRect = useCallback((duration: number) => {
    const fg = fgRef.current;
    if (!fg) return;

    const window_ = focusRect?.() ?? { x: 0, y: 0, width, height };
    const fit = fitTransform(
      (data.nodes as GraphNode[]).map((node: any) => ({
        x: node.x,
        y: node.y,
        radius: node.type === 'company' ? NODE_SIZES.company.radius : NODE_SIZES.person.radius,
        kind: node.type,
        label: node.label,
        bold: node.id === centerNode,
      })),
      measureLabelWidth,
      window_,
      { width, height },
      FIT_CONFIG,
    );
    if (!fit) return;

    // The timer is armed *before* the animation starts, not after: a tween
    // calls its update on the frame it starts, and with no duration the library
    // applies the transform synchronously — either way an `end` event arrives
    // before the next line runs, and a guard armed afterwards would read that
    // event as the reader moving the view.
    lastFitRef.current = fit;
    if (settleTimerRef.current !== null) window.clearTimeout(settleTimerRef.current);
    settleTimerRef.current = window.setTimeout(() => {
      settleTimerRef.current = null;
      if (!transformMatches(fg, fit)) autoFitRef.current = false;
    }, duration + FIT_SETTLE_MARGIN_MS);

    fg.centerAt(fit.centerX, fit.centerY, duration);
    fg.zoom(fit.zoom, duration);
  }, [data, centerNode, focusRect, width, height]);

  useEffect(() => () => {
    if (settleTimerRef.current !== null) window.clearTimeout(settleTimerRef.current);
  }, []);

  useImperativeHandle(ref, () => ({
    zoomIn: () => {
      const fg = fgRef.current;
      if (fg) fg.zoom(fg.zoom() * 1.4, 300);
    },
    zoomOut: () => {
      const fg = fgRef.current;
      if (fg) fg.zoom(fg.zoom() / 1.4, 300);
    },
    fitToView: () => {
      autoFitRef.current = true;
      fitToRect(FIT_CONFIG.duration);
    },
    refitIfAuto: () => {
      if (autoFitRef.current) fitToRect(FIT_CONFIG.duration);
    },
    exportPng: () => {
      const canvas = wrapperRef.current?.querySelector('canvas');
      if (!canvas) return;
      const tmp = document.createElement('canvas');
      tmp.width = canvas.width;
      tmp.height = canvas.height;
      const ctx = tmp.getContext('2d')!;
      ctx.fillStyle = isDark ? '#020617' : '#ffffff';
      ctx.fillRect(0, 0, tmp.width, tmp.height);
      ctx.drawImage(canvas, 0, 0);
      const link = document.createElement('a');
      link.download = 'graf-prepojeni.png';
      link.href = tmp.toDataURL('image/png');
      link.click();
    },
  }));

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force('charge').strength(FORCE_CONFIG.chargeStrength);
    fg.d3Force('link').distance(FORCE_CONFIG.linkDistance);
    if (fg.d3Force('center')) {
      fg.d3Force('center').strength(FORCE_CONFIG.centerStrength);
    }

    const labelCollide = forceCollide((node: any) => {
      const gn = node as GraphNode;
      const baseRadius = gn.type === 'company' ? NODE_SIZES.company.radius : NODE_SIZES.person.radius;
      const labelEstimate = gn.label.length * 3.2 + 10;
      return Math.max(baseRadius + 8, labelEstimate);
    }).iterations(2);
    fg.d3Force('collide', labelCollide);
  }, [data]);

  /**
   * The reader's own gesture. d3-zoom reports a programmatic transition the same
   * way it reports a drag, so the *decision* is not made here — see `fitToRect`.
   * This only asks the question once no fit is in flight.
   */
  const handleZoomEnd = useCallback(() => {
    if (settleTimerRef.current !== null) return;
    const fg = fgRef.current;
    const target = lastFitRef.current;
    if (!fg || !target) return;
    if (!transformMatches(fg, target)) autoFitRef.current = false;
  }, []);

  /**
   * Frame the graph once the layout has stopped moving.
   *
   * Twice, on purpose. The timer frames it shortly after the data arrives, while
   * the forces are still spreading the nodes — that is the frame the reader
   * looks at for the first half second, and it is what the graph used to do. The
   * engine stop is the frame that lasts: by then the nodes are where they will
   * stay, and a fit computed before that would be framing a layout that no
   * longer exists.
   */
  useEffect(() => {
    if (data.nodes.length === 0 || !autoFitRef.current) return;
    const timer = setTimeout(() => {
      if (autoFitRef.current) fitToRect(FIT_CONFIG.duration);
    }, 500);
    return () => clearTimeout(timer);
  }, [data.nodes.length, fitToRect]);

  /**
   * Node chrome only. The name is *requested* here and drawn later, in
   * `paintLabels`, because a node painted further down the list would otherwise
   * cover a label already drawn by an earlier one — its opaque disc and its glow
   * are painted after the label and on top of it. Collecting first and drawing
   * once at the end of the frame removes that whole class of loss.
   */
  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const gn = node as GraphNode;
    const isCenter = gn.id === centerNode;
    // Both constants are screen pixels; dividing by the zoom is what keeps them
    // that. The fit budgets for the same two numbers, so a change here that is
    // not made there would silently frame the wrong rectangle.
    const fontSize = Math.max(LABEL_FONT_PX / globalScale, 4);
    const priority = isCenter
      ? LABEL_PRIORITY.center
      : gn.id === hoveredId
        ? LABEL_PRIORITY.hovered
        : LABEL_PRIORITY.rest;

    if (gn.type === 'company') {
      const r = NODE_SIZES.company.radius;
      drawCircleNode(
        ctx, node.x, node.y, r,
        colors.company.bg, colors.company.stroke, colors.company.glow,
        globalScale, isCenter,
        colors.centerNode.stroke, colors.centerNode.glow,
      );
      drawBuildingIcon(ctx, node.x, node.y, r * 1.3, colors.company.icon);

      pendingLabelsRef.current.push({
        id: gn.id,
        text: gn.label,
        kind: 'company',
        x: node.x,
        y: node.y + r + LABEL_GAP_PX.company / globalScale,
        fontSize,
        bold: isCenter,
        priority,
        degree: gn.rolesCount ?? 0,
        alwaysDraw: isCenter,
      });
    } else {
      const r = NODE_SIZES.person.radius;
      drawCircleNode(
        ctx, node.x, node.y, r,
        colors.person.bg, colors.person.stroke, colors.person.glow,
        globalScale, isCenter,
        colors.centerNode.stroke, colors.centerNode.glow,
      );
      drawPersonIcon(ctx, node.x, node.y, r * 1.2, colors.person.icon);

      pendingLabelsRef.current.push({
        id: gn.id,
        text: gn.label,
        kind: 'person',
        x: node.x,
        y: node.y + r + LABEL_GAP_PX.person / globalScale,
        fontSize,
        bold: false,
        priority,
        degree: gn.rolesCount ?? 0,
        // The centre of the graph is only ever a company (useGraphData.ts), so
        // this is false for a person by construction, not by omission.
        alwaysDraw: false,
      });
    }
  }, [centerNode, colors, hoveredId]);

  /**
   * The frame boundary. `force-graph` calls this once at the start of every
   * redraw, immediately before the nodes are painted — which is the only
   * reliable "new frame" signal available. The previous code guessed at it from
   * a wall clock inside the per-node callback, so on a slow frame the list was
   * cleared mid-paint and a name could be dropped against labels that were no
   * longer on screen.
   */
  const clearPendingLabels = useCallback(() => {
    pendingLabelsRef.current = [];
  }, []);

  /** The second half of the frame: place the collected names and draw them. */
  const paintLabels = useCallback((ctx: CanvasRenderingContext2D, globalScale: number) => {
    const requests = pendingLabelsRef.current;
    if (requests.length === 0) return;

    // Measured on the same context, at the same font, that draws them below.
    const measureWidth = (text: string, fontSize: number, bold: boolean) => {
      ctx.font = labelFont(fontSize, bold);
      return ctx.measureText(text).width;
    };

    const { placed } = layoutLabels(requests, measureWidth, globalScale, 2 / globalScale);
    for (const label of placed) {
      drawLabel(ctx, label, labelColor(label.kind, isDark), labelBg, globalScale);
    }
  }, [isDark, labelBg]);

  const paintLink = useCallback((link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const source = link.source;
    const target = link.target;
    if (!source || !target || typeof source.x === 'undefined') return;

    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist === 0) return;

    const sourceR = (source as GraphNode).type === 'company' ? NODE_SIZES.company.radius : NODE_SIZES.person.radius;
    const targetR = (target as GraphNode).type === 'company' ? NODE_SIZES.company.radius : NODE_SIZES.person.radius;

    const sx = source.x + (dx / dist) * (sourceR + 2);
    const sy = source.y + (dy / dist) * (sourceR + 2);
    const tx = target.x - (dx / dist) * (targetR + 2);
    const ty = target.y - (dy / dist) * (targetR + 2);

    const isActive = link.isActive;
    const roleColor = colors.roles[link.role as string] || colors.edge.active;

    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(tx, ty);

    if (isActive === true) {
      ctx.strokeStyle = roleColor;
      ctx.lineWidth = 1.8 / globalScale;
      ctx.setLineDash([]);
    } else if (isActive === false) {
      ctx.strokeStyle = colors.edge.inactive;
      ctx.lineWidth = 1 / globalScale;
      ctx.setLineDash([5 / globalScale, 4 / globalScale]);
    } else {
      // Unknown: dotted rather than dashed, so it is legible as a third state
      // next to a dashed edge of nearly the same weight.
      ctx.strokeStyle = colors.edge.unknown;
      ctx.lineWidth = 1.2 / globalScale;
      ctx.setLineDash([1.5 / globalScale, 3 / globalScale]);
    }
    ctx.globalAlpha = isActive === true ? 0.55 : 0.35;
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    const role = link.role as string;
    if (role && globalScale > 0.35) {
      const midX = (sx + tx) / 2;
      const midY = (sy + ty) / 2;

      const labelText = getRoleAbbrev(role);
      const labelFontSize = Math.max(11 / globalScale, 3.5);
      ctx.font = `600 ${labelFontSize}px 'Inter', sans-serif`;

      const textWidth = ctx.measureText(labelText).width;
      const padX = 3 / globalScale;
      const padY = 2 / globalScale;
      const pillW = textWidth + padX * 2;
      const pillH = labelFontSize + padY * 2;
      const pillR = pillH / 2;

      ctx.save();
      ctx.translate(midX, midY);

      let angle = Math.atan2(dy, dx);
      if (angle > Math.PI / 2) angle -= Math.PI;
      if (angle < -Math.PI / 2) angle += Math.PI;
      ctx.rotate(angle);

      ctx.beginPath();
      ctx.roundRect(-pillW / 2, -pillH / 2, pillW, pillH, pillR);
      ctx.fillStyle = colors.edge.labelBg;
      ctx.fill();
      ctx.strokeStyle = roleColor;
      ctx.lineWidth = 0.7 / globalScale;
      ctx.globalAlpha = 0.5;
      ctx.stroke();
      ctx.globalAlpha = 1;

      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle =
        isActive === true
          ? roleColor
          : isActive === false
            ? colors.edge.inactive
            : colors.edge.unknown;
      ctx.fillText(labelText, 0, 0.5 / globalScale);

      ctx.restore();
    }
  }, [colors]);

  const handleNodeHover = useCallback((node: any) => {
    const next = node ? (node as GraphNode) : null;
    setHoveredId(next ? next.id : null);
    onNodeHover(next);
  }, [onNodeHover]);

  const getNodeArea = useCallback((node: any) => {
    const r = (node as GraphNode).type === 'company' ? NODE_SIZES.company.radius : NODE_SIZES.person.radius;
    return Math.PI * r * r;
  }, []);

  return (
    <div ref={wrapperRef}>
      <ForceGraph2D
        ref={fgRef}
        graphData={data}
        width={width}
        height={height}
        nodeCanvasObject={paintNode}
        onRenderFramePre={clearPendingLabels}
        onRenderFramePost={paintLabels}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          const r = (node as GraphNode).type === 'company' ? NODE_SIZES.company.radius : NODE_SIZES.person.radius;
          ctx.beginPath();
          ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
        }}
        linkCanvasObject={paintLink}
        onNodeClick={(node: any) => onNodeClick(node as GraphNode)}
        onNodeHover={handleNodeHover}
        // Placing a node by hand is the reader arranging the picture, and a
        // drag reheats the engine — so without this, letting go of a node would
        // be followed by the view sliding back to the middle. Treated like a
        // pan: the graph stops framing itself until the ⟲ is pressed.
        onNodeDrag={() => {
          autoFitRef.current = false;
        }}
        onZoomEnd={handleZoomEnd}
        onEngineStop={() => {
          if (autoFitRef.current) fitToRect(FIT_CONFIG.duration);
        }}
        nodeVal={getNodeArea}
        cooldownTicks={100}
        backgroundColor="transparent"
      />
    </div>
  );
});
