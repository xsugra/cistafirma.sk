export const GRAPH_COLORS = {
  company: {
    bg: '#2563EB',
    bgHover: '#1D4ED8',
    stroke: '#1E40AF',
    glow: 'rgba(37, 99, 235, 0.25)',
    icon: '#FFFFFF',
  },
  person: {
    bg: '#475569',
    bgHover: '#334155',
    stroke: '#64748B',
    glow: 'rgba(100, 116, 139, 0.25)',
    icon: '#FFFFFF',
  },
  edge: {
    active: '#6B7280',
    inactive: '#D1D5DB',
    // Between the two greys on purpose: a third stroke that reads as neither
    // "current" nor "ended", because that is exactly what it means.
    unknown: '#9CA3AF',
    label: '#374151',
    labelBg: 'rgba(255, 255, 255, 0.92)',
  },
  centerNode: {
    stroke: '#10B981',
    glow: 'rgba(16, 185, 129, 0.35)',
  },
  roles: {
    'Konateľ': '#2563EB',
    'Spoločník': '#0EA5E9',
    'Prokurista': '#60A5FA',
    'Predstavenstvo': '#64748B',
    'Dozorná rada': '#9CA3AF',
    'Akcionár': '#1D4ED8',
    'Iné': '#6B7280',
  } as Record<string, string>,
} as const;

export const GRAPH_COLORS_DARK = {
  company: {
    bg: '#1E40AF',
    bgHover: '#1E3A8A',
    stroke: '#3B82F6',
    glow: 'rgba(59, 130, 246, 0.3)',
    icon: '#DBEAFE',
  },
  person: {
    bg: '#334155',
    bgHover: '#1E293B',
    stroke: '#94A3B8',
    glow: 'rgba(148, 163, 184, 0.3)',
    icon: '#E2E8F0',
  },
  edge: {
    active: '#9CA3AF',
    inactive: '#4B5563',
    unknown: '#6B7280',
    label: '#D1D5DB',
    labelBg: 'rgba(17, 24, 39, 0.92)',
  },
  centerNode: {
    stroke: '#34D399',
    glow: 'rgba(52, 211, 153, 0.35)',
  },
  roles: {
    'Konateľ': '#60A5FA',
    'Spoločník': '#38BDF8',
    'Prokurista': '#93C5FD',
    'Predstavenstvo': '#94A3B8',
    'Dozorná rada': '#D1D5DB',
    'Akcionár': '#3B82F6',
    'Iné': '#9CA3AF',
  } as Record<string, string>,
} as const;

export const NODE_SIZES = {
  company: { radius: 26 },
  person: { radius: 20 },
} as const;

/**
 * Label font size in *screen* pixels, and the gap between a node's disc and its
 * name, per node kind.
 *
 * Both are screen measurements even though the painter works in graph units:
 * `paintNode` divides the font by the zoom (`13 / globalScale`) and the gap by
 * the same, so what the reader sees is 13 px of text sitting 5 px (4 px for a
 * person) below the disc at every zoom level. The fit has to budget for the
 * same numbers -- in screen pixels, which is why it can measure them once
 * instead of once per candidate zoom.
 */
export const LABEL_FONT_PX = 13;
export const LABEL_GAP_PX = { company: 5, person: 4 } as const;

/**
 * How the graph is framed in the part of the page the reader can see.
 *
 * The zoom is bounded here rather than by the library's own limits (0.01 to
 * 1000): a fit is meant to *show* the graph, and a two-node graph fitted to a
 * desktop window would otherwise be blown up until the discs filled it.
 */
export const FIT_CONFIG = {
  /** Breathing room between the drawn graph and the edge of the window, in px. */
  padding: 24,
  minZoom: 0.02,
  maxZoom: 2.5,
  /** ms — long enough to follow by eye, short enough not to lag a scroll. */
  duration: 400,
};

export const FORCE_CONFIG = {
  chargeStrength: -700,
  linkDistance: 220,
  centerStrength: 0.03,
  collideRadius: 65,
} as const;
