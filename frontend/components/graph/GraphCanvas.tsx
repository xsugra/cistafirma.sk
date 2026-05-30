import { useRef, useCallback, useEffect, useImperativeHandle, forwardRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useTheme } from '../../context/ThemeContext';
import { GRAPH_COLORS, GRAPH_COLORS_DARK, NODE_SIZES, FORCE_CONFIG } from './graphConfig';
import type { GraphData, GraphNode } from './graphTypes';

export interface GraphCanvasHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  zoomToFit: () => void;
}

interface GraphCanvasProps {
  data: GraphData;
  centerNode: string | null;
  onNodeClick: (node: GraphNode) => void;
  onNodeHover: (node: GraphNode | null) => void;
  width: number;
  height: number;
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

function drawLabelWithBg(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number, y: number,
  fontSize: number,
  textColor: string,
  bgColor: string,
  globalScale: number,
  bold: boolean,
) {
  ctx.font = `${bold ? 'bold ' : '500 '}${fontSize}px 'Inter', sans-serif`;
  const tw = ctx.measureText(text).width;
  const padX = 3 / globalScale;
  const padY = 1.5 / globalScale;

  ctx.fillStyle = bgColor;
  ctx.beginPath();
  const pillW = tw + padX * 2;
  const pillH = fontSize + padY * 2;
  ctx.roundRect(x - pillW / 2, y - padY, pillW, pillH, 3 / globalScale);
  ctx.fill();

  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.fillStyle = textColor;
  ctx.fillText(text, x, y);
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
  { data, centerNode, onNodeClick, onNodeHover, width, height }, ref
) {
  const fgRef = useRef<any>(null);
  const { isDark } = useTheme();
  const colors = isDark ? GRAPH_COLORS_DARK : GRAPH_COLORS;
  const labelBg = isDark ? 'rgba(2, 6, 23, 0.85)' : 'rgba(255, 255, 255, 0.88)';

  useImperativeHandle(ref, () => ({
    zoomIn: () => {
      const fg = fgRef.current;
      if (fg) {
        const currentZoom = fg.zoom();
        fg.zoom(currentZoom * 1.4, 300);
      }
    },
    zoomOut: () => {
      const fg = fgRef.current;
      if (fg) {
        const currentZoom = fg.zoom();
        fg.zoom(currentZoom / 1.4, 300);
      }
    },
    zoomToFit: () => fgRef.current?.zoomToFit(400, 60),
  }));

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force('charge').strength(FORCE_CONFIG.chargeStrength);
    fg.d3Force('link').distance(FORCE_CONFIG.linkDistance);
    if (fg.d3Force('center')) {
      fg.d3Force('center').strength(FORCE_CONFIG.centerStrength);
    }
    fg.d3Force('collide', null);
    const d3 = (window as any).d3;
    if (d3?.forceCollide) {
      fg.d3Force('collide', d3.forceCollide(FORCE_CONFIG.collideRadius));
    }
  }, [data]);

  useEffect(() => {
    if (fgRef.current && data.nodes.length > 0) {
      setTimeout(() => fgRef.current?.zoomToFit(400, 60), 500);
    }
  }, [data.nodes.length]);

  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const gn = node as GraphNode;
    const isCenter = gn.id === centerNode;
    const fontSize = Math.max(13 / globalScale, 4);

    if (gn.type === 'company') {
      const r = NODE_SIZES.company.radius;
      drawCircleNode(
        ctx, node.x, node.y, r,
        colors.company.bg, colors.company.stroke, colors.company.glow,
        globalScale, isCenter,
        colors.centerNode.stroke, colors.centerNode.glow,
      );
      drawBuildingIcon(ctx, node.x, node.y, r * 1.3, colors.company.icon);

      drawLabelWithBg(
        ctx, gn.label, node.x, node.y + r + 5 / globalScale,
        fontSize, isDark ? '#93C5FD' : '#1E40AF', labelBg,
        globalScale, isCenter,
      );
    } else {
      const r = NODE_SIZES.person.radius;
      drawCircleNode(
        ctx, node.x, node.y, r,
        colors.person.bg, colors.person.stroke, colors.person.glow,
        globalScale, isCenter,
        colors.centerNode.stroke, colors.centerNode.glow,
      );
      drawPersonIcon(ctx, node.x, node.y, r * 1.2, colors.person.icon);

      drawLabelWithBg(
        ctx, gn.label, node.x, node.y + r + 4 / globalScale,
        fontSize, isDark ? '#D1D5DB' : '#374151', labelBg,
        globalScale, false,
      );
    }
  }, [centerNode, colors, isDark, labelBg]);

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

    if (isActive) {
      ctx.strokeStyle = roleColor;
      ctx.lineWidth = 1.8 / globalScale;
      ctx.setLineDash([]);
    } else {
      ctx.strokeStyle = colors.edge.inactive;
      ctx.lineWidth = 1 / globalScale;
      ctx.setLineDash([5 / globalScale, 4 / globalScale]);
    }
    ctx.globalAlpha = isActive ? 0.55 : 0.35;
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
      ctx.fillStyle = isActive ? roleColor : colors.edge.inactive;
      ctx.fillText(labelText, 0, 0.5 / globalScale);

      ctx.restore();
    }
  }, [colors]);

  const getNodeArea = useCallback((node: any) => {
    const r = (node as GraphNode).type === 'company' ? NODE_SIZES.company.radius : NODE_SIZES.person.radius;
    return Math.PI * r * r;
  }, []);

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={data}
      width={width}
      height={height}
      nodeCanvasObject={paintNode}
      nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
        const r = (node as GraphNode).type === 'company' ? NODE_SIZES.company.radius : NODE_SIZES.person.radius;
        ctx.beginPath();
        ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
      }}
      linkCanvasObject={paintLink}
      onNodeClick={(node: any) => onNodeClick(node as GraphNode)}
      onNodeHover={(node: any) => onNodeHover(node ? (node as GraphNode) : null)}
      nodeVal={getNodeArea}
      cooldownTicks={100}
      backgroundColor="transparent"
    />
  );
});
