import {describe, expect, it, vi} from 'vitest';
import {
  LABEL_PRIORITY,
  LABEL_SIZE_STEPS,
  compareLabels,
  labelMetrics,
  layoutLabels,
  rectFor,
  rectsOverlap,
  type LabelRequest,
  type MeasureWidth,
} from './labelLayout';

/**
 * A stand-in for canvas `measureText`: width proportional to the character
 * count. Deliberately simple so the arithmetic in each expectation below can be
 * followed by hand.
 */
const measure: MeasureWidth = (text, fontSize) => text.length * fontSize * 0.6;

/** At globalScale 1: padX = 3, padY = 1.5. "AAAA" at 10px is 24 + 6 = 30 wide. */
const GLOBAL_SCALE = 1;
const PADDING = 2;

function req(over: Partial<LabelRequest> & { id: string; x: number }): LabelRequest {
  return {
    text: 'AAAA',
    kind: 'company',
    y: 0,
    fontSize: 10,
    bold: false,
    priority: LABEL_PRIORITY.rest,
    degree: 0,
    alwaysDraw: false,
    ...over,
  };
}

const layout = (requests: LabelRequest[], steps = LABEL_SIZE_STEPS) =>
  layoutLabels(requests, measure, GLOBAL_SCALE, PADDING, steps);

describe('rectsOverlap', () => {
  const base = {x: 0, y: 0, w: 30, h: 13};

  it('reports overlap for intersecting rectangles', () => {
    expect(rectsOverlap(base, {x: 10, y: 0, w: 30, h: 13}, 0)).toBe(true);
  });

  it('treats a gap narrower than the padding as an overlap', () => {
    // Right edge at 30; the neighbour starts at 31, so the gap is 1 < 2.
    expect(rectsOverlap(base, {x: 31, y: 0, w: 30, h: 13}, 2)).toBe(true);
  });

  it('still reports overlap at exactly the padding, since the test is strict', () => {
    // Right edge at 30, so 32 leaves a gap of exactly 2 — the boundary is
    // inclusive, and this preserves the spacing the graph had before.
    expect(rectsOverlap(base, {x: 32, y: 0, w: 30, h: 13}, 2)).toBe(true);
  });

  it('reports no overlap once the gap exceeds the padding', () => {
    expect(rectsOverlap(base, {x: 33, y: 0, w: 30, h: 13}, 2)).toBe(false);
  });

  it('separates rectangles that only share a row', () => {
    expect(rectsOverlap(base, {x: 0, y: 40, w: 30, h: 13}, 0)).toBe(false);
  });
});

describe('rectFor', () => {
  it('matches the geometry the draw uses, so the test and the pill agree', () => {
    const metrics = labelMetrics(24, 10, GLOBAL_SCALE);
    const rect = rectFor(100, 200, metrics);
    // The pill is drawn at (x - w/2, y - padY), not at (x, y).
    expect(rect).toEqual({x: 100 - 15, y: 200 - 1.5, w: 30, h: 13});
  });
});

describe('compareLabels', () => {
  it('orders the centre before a hovered node and both before the rest', () => {
    const centre = req({id: 'c', x: 0, priority: LABEL_PRIORITY.center});
    const hovered = req({id: 'h', x: 0, priority: LABEL_PRIORITY.hovered});
    const rest = req({id: 'r', x: 0});
    expect([rest, centre, hovered].sort(compareLabels).map(r => r.id)).toEqual(['c', 'h', 'r']);
  });

  it('breaks a priority tie by degree, then by kind, then by id', () => {
    const lowDegree = req({id: 'a', x: 0, degree: 1});
    const highDegree = req({id: 'z', x: 0, degree: 9});
    expect([lowDegree, highDegree].sort(compareLabels).map(r => r.id)).toEqual(['z', 'a']);

    const person = req({id: 'a', x: 0, kind: 'person'});
    const company = req({id: 'z', x: 0, kind: 'company'});
    expect([person, company].sort(compareLabels).map(r => r.id)).toEqual(['z', 'a']);

    const one = req({id: 'a', x: 0});
    const two = req({id: 'b', x: 0});
    expect([two, one].sort(compareLabels).map(r => r.id)).toEqual(['a', 'b']);
  });
});

describe('layoutLabels', () => {
  it('places non-colliding labels at full size', () => {
    const {placed, dropped} = layout([req({id: 'a', x: 0}), req({id: 'b', x: 400})]);
    expect(placed.map(p => p.id)).toEqual(['a', 'b']);
    expect(placed.every(p => p.usedFontSize === 10)).toBe(true);
    expect(dropped).toBe(0);
  });

  it('shrinks a colliding label instead of dropping it when the smaller step fits', () => {
    // Both pills are 30 wide at 10px, so 30 apart collides ((30 + 30) / 2 + 2 = 32 > 30).
    // The second shrinks to 24 wide, and 30 apart clears it ((30 + 24) / 2 + 2 = 29 <= 30).
    const {placed, dropped} = layout([req({id: 'a', x: 0}), req({id: 'b', x: 30})]);
    expect(placed.map(p => p.id)).toEqual(['a', 'b']);
    expect(placed[1].usedFontSize).toBe(7.5);
    expect(dropped).toBe(0);
  });

  it('drops a label that collides at every step', () => {
    const {placed, dropped} = layout([req({id: 'a', x: 0}), req({id: 'b', x: 0})]);
    expect(placed.map(p => p.id)).toEqual(['a']);
    expect(dropped).toBe(1);
  });

  it('never draws two overlapping labels', () => {
    const requests = Array.from({length: 40}, (_, i) => req({id: `n${i}`, x: (i % 8) * 9, y: Math.floor(i / 8) * 6}));
    const {placed} = layout(requests);
    for (let i = 0; i < placed.length; i++) {
      for (let j = i + 1; j < placed.length; j++) {
        expect(rectsOverlap(placed[i].rect, placed[j].rect, PADDING)).toBe(false);
      }
    }
  });

  it('always draws the centre, even where it collides', () => {
    const centre = req({id: 'centre', x: 50, y: 50, priority: LABEL_PRIORITY.center, alwaysDraw: true});
    const {placed} = layout([req({id: 'a', x: 50, y: 50}), centre, req({id: 'b', x: 51, y: 50})]);
    expect(placed.map(p => p.id)).toContain('centre');
    expect(placed[0].id).toBe('centre');
  });

  it('is deterministic: the result does not depend on the order it is handed', () => {
    const requests = Array.from({length: 30}, (_, i) => req({id: `n${i}`, x: (i % 6) * 11, degree: i % 4}));
    const forward = layout(requests).placed.map(p => p.id);
    const backward = layout([...requests].reverse()).placed.map(p => p.id);
    // `compareLabels` is a total order, so the sorted sequence is unique: the
    // same set of names, in the same order, whichever way the input arrives.
    // This is the property the old code lacked — it decided by paint order.
    expect(backward).toEqual(forward);
  });

  it('bounds the work: at most one measurement per label per step', () => {
    const spy = vi.fn(measure);
    const requests = Array.from({length: 200}, (_, i) => req({id: `n${i}`, x: i % 3, y: i % 3}));
    layoutLabels(requests, spy, GLOBAL_SCALE, PADDING);
    // The old per-node path measured once per node per frame with no ceiling on
    // how many times a name was re-measured; this is the ceiling.
    expect(spy.mock.calls.length).toBeLessThanOrEqual(requests.length * LABEL_SIZE_STEPS.length);
  });

  it('scales the number of drawn names with the space available', () => {
    // 200 nodes stacked on the same point: geometry, not the algorithm, is what
    // bounds how many names can be shown.
    const stacked = Array.from({length: 200}, (_, i) => req({id: `n${i}`, x: 0, y: 0}));
    const {placed, dropped} = layout(stacked);
    expect(placed.length + dropped).toBe(200);
    expect(placed.length).toBe(1);

    const spread = Array.from({length: 200}, (_, i) => req({id: `n${i}`, x: i * 40}));
    expect(layout(spread).placed.length).toBe(200);
  });
});
