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

export const FORCE_CONFIG = {
  chargeStrength: -700,
  linkDistance: 220,
  centerStrength: 0.03,
  collideRadius: 65,
} as const;
