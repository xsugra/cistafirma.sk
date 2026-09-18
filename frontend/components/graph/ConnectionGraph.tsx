import { useEffect, useRef, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { GraphCanvas, type GraphCanvasHandle } from './GraphCanvas';
import { GraphControls } from './GraphControls';
import { GraphTooltip } from './GraphTooltip';
import { GraphLegend } from './GraphLegend';
import { useGraphData } from './useGraphData';
import type { GraphNode } from './graphTypes';
import { focusWindow, type Rect } from './graphFit';
import { companyPath, personPath } from '../../constants';

interface ConnectionGraphProps {
  ico: string;
}

/**
 * The canvas never gets shorter than this, whatever the container measures.
 * `min-h-[500px]` already holds the inline card at that height; this is the
 * floor for a window short enough to beat it.
 */
const MIN_CANVAS_HEIGHT = 400;

/** How long to wait after the last scroll or resize before re-framing, in ms. */
const REFIT_DEBOUNCE_MS = 180;

/**
 * Below this much of the box on screen the graph is scrolling past. Re-framing
 * it there would be motion the reader is not looking at — and worse, framing a
 * half-scrolled box makes the graph breathe in and out as they pass it.
 */
const MIN_VISIBLE_FRACTION = 0.55;

/** The viewport, as `focusWindow` wants it. */
function viewport() {
  return { width: window.innerWidth, height: window.innerHeight };
}

export function ConnectionGraph({ ico }: ConnectionGraphProps) {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const stripRef = useRef<HTMLDivElement | null>(null);
  const captionRef = useRef<HTMLParagraphElement | null>(null);
  const canvasRef = useRef<GraphCanvasHandle>(null);
  /**
   * `{0, 0}` until the container has actually been measured.
   *
   * It used to be `{1100, 1000}` -- a guess -- and the effect that was supposed
   * to correct it could never run: it keyed on `[isFullscreen]` and read
   * `containerRef.current`, which is `null` on the first render because the
   * component returns its loading branch before any element carries the ref. So
   * the effect ran once, found nothing, and the canvas stayed 1100x1000 CSS px
   * on every screen for ever. Measured on a 393 px phone: the ink's centre sat
   * 445 px right and 98 px below the middle of the box, and about 85 px of the
   * graph's 700 px were inside it.
   *
   * A callback ref is what fixes that: it fires when the node attaches, which is
   * a different commit from the one that produced no node at all.
   */
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [containerEl, setContainerEl] = useState<HTMLDivElement | null>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);

  const { graphData, loading, error, fetchGraph, expandNode, expandPerson, centerNode, truncated } = useGraphData();

  useEffect(() => {
    fetchGraph(ico);
  }, [ico, fetchGraph]);

  const attachContainer = useCallback((node: HTMLDivElement | null) => {
    containerRef.current = node;
    setContainerEl(node);
  }, []);

  useEffect(() => {
    if (!containerEl) return;

    const measure = () => {
      const rect = containerEl.getBoundingClientRect();
      const width = Math.round(rect.width);
      const height = Math.round(Math.max(rect.height, MIN_CANVAS_HEIGHT));
      // Same size, same object: a rotation or a scroll that does not change the
      // box must not re-render the canvas and restart the simulation.
      setDimensions(prev => (prev.width === width && prev.height === height ? prev : { width, height }));
    };
    measure();

    // A `ResizeObserver` on the container rather than a `window` resize
    // listener, so this also catches what the old code missed: the box changing
    // because the page around it changed, and iOS collapsing its URL bar, which
    // fires no `resize` on the window at all.
    const observer = new ResizeObserver(measure);
    observer.observe(containerEl);
    return () => observer.disconnect();
  }, [containerEl]);

  /**
   * What the reader is looking at, in canvas pixels -- asked for at the moment
   * of a fit rather than kept in state, so it is always the current frame and
   * never a value from a render that has since scrolled away.
   *
   * `null` when the box cannot be measured; `GraphCanvas` then frames the whole
   * canvas, which is what it did before any of this existed.
   */
  const focusRect = useCallback((): Rect | null => {
    const box = containerRef.current?.getBoundingClientRect();
    if (!box || box.width === 0 || box.height === 0) return null;
    const window = focusWindow(
      box,
      viewport(),
      {
        top: stripRef.current?.getBoundingClientRect() ?? null,
        bottom: captionRef.current?.getBoundingClientRect() ?? null,
      },
    ).rect;
    // None of the box is on screen yet -- which is where it is on first load,
    // a screen and a half below the fold. The window then has no height and the
    // fit is refused, so the graph would sit at whatever the simulation
    // produced: spread wider than the canvas and clipped by its edge until the
    // reader arrives and the debounced refit fires, ~580 ms later.
    //
    // Framing the whole box instead means they arrive at a framed graph, and
    // the refit that follows moves the centre by the 54 px the legend covers --
    // a small correction rather than a clipped graph snapping into place.
    if (window.height <= 0) {
      return {x: 0, y: 0, width: box.width, height: box.height};
    }
    return window;
  }, []);

  const isMostlyVisible = useCallback(() => {
    const box = containerRef.current?.getBoundingClientRect();
    if (!box) return false;
    return focusWindow(box, viewport()).visibleFraction >= MIN_VISIBLE_FRACTION;
  }, []);

  /**
   * Re-frame when the window the reader has to look through changes: scrolling
   * the graph into view, rotating the phone, the URL bar collapsing.
   *
   * Debounced, because a scroll is a stream of events and a fit is a 400 ms
   * animation -- one fit per gesture is readable, one per event is not.
   * `refitIfAuto` is what decides; a reader who has panned or zoomed keeps their
   * own framing whatever the window does.
   */
  useEffect(() => {
    let timer: number | null = null;
    const schedule = () => {
      if (timer !== null) window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        timer = null;
        if (!isMostlyVisible()) return;
        canvasRef.current?.refitIfAuto();
      }, REFIT_DEBOUNCE_MS);
    };

    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    // iOS reports a URL bar collapsing on the visual viewport, not on the
    // window; without this the graph is framed for a viewport that is 60 px
    // taller than the one on screen.
    window.visualViewport?.addEventListener('resize', schedule);
    return () => {
      if (timer !== null) window.clearTimeout(timer);
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      window.visualViewport?.removeEventListener('resize', schedule);
    };
  }, [isMostlyVisible]);

  useEffect(() => {
    if (!isFullscreen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsFullscreen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [isFullscreen]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    if (node.type === 'company' && node.ico && node.ico !== ico) {
      expandNode(node.ico);
    } else if (node.type === 'person') {
      const personId = node.id.replace('person_', '');
      expandPerson(personId);
    }
  }, [ico, expandNode, expandPerson]);

  const handleNodeHover = useCallback((node: GraphNode | null) => {
    setHoveredNode(node);
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const container = containerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    setTooltipPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }, []);

  /**
   * A person node carries the id we hold for them (`person_12345`), so it can
   * be opened. This is the only place on a company page where a person link is
   * legitimate: the ORSR-derived officers in the Osoby section have no id, and
   * a link built from a name would point at whoever the search returned first.
   *
   * The `^\d+$` guard is not decoration -- it is what keeps an id that is not
   * one from becoming `/osoba/person_...` and a page that cannot load.
   */
  const handleNodeDoubleClick = useCallback((node: GraphNode) => {
    if (node.type === 'company' && node.ico) {
      navigate(companyPath(node.ico));
      return;
    }
    if (node.type === 'person') {
      const personId = node.id.replace('person_', '');
      if (/^\d+$/.test(personId)) navigate(personPath(personId));
    }
  }, [navigate]);

  if (loading && !graphData) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          Načítavam graf prepojení...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500 dark:text-gray-400">
        <div className="text-center">
          <p className="text-red-500 dark:text-red-400">{error}</p>
          <button
            onClick={() => fetchGraph(ico)}
            className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            Skúsiť znova
          </button>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-500 dark:text-gray-400">
        Žiadne prepojenia neboli nájdené.
      </div>
    );
  }

  /**
   * Edge offsets for the legend, the controls and the caption.
   *
   * `env(safe-area-inset-*)` is a property of the *viewport*, not of where an
   * element happens to sit in it: it is the size of the unsafe strip at that
   * edge of the screen, and it does not fall to 0 for an element further down
   * the page. So it may only be used where the element really is against the
   * edge -- the fullscreen overlay. These are rendered in the inline card as
   * well, where the same declaration would shove them ~59 px down for no
   * reason at all. Hence the conditional, rather than one class list.
   */
  const edgeTop = isFullscreen ? 'top-[calc(0.75rem_+_env(safe-area-inset-top))]' : 'top-3';
  const edgeRight = isFullscreen ? 'right-[calc(0.75rem_+_env(safe-area-inset-right))]' : 'right-3';
  const edgeLeft = isFullscreen ? 'left-[calc(0.75rem_+_env(safe-area-inset-left))]' : 'left-3';
  const edgeBottom = isFullscreen
    ? 'bottom-[calc(0.5rem_+_env(safe-area-inset-bottom))]'
    : 'bottom-2';

  /*
   * Toggling fullscreen unmounts this whole subtree and mounts it again inside
   * the portal -- the element is not moved, it is replaced. That used to need a
   * `[isFullscreen]` effect calling `zoomToFit` after 150 ms; it does not any
   * more, because a fresh `GraphCanvas` starts with its auto-fit armed and
   * frames itself on the first data effect and again when the engine stops.
   */
  const graphContent = (
    <div
      ref={attachContainer}
      // `h-dvh`, not `h-screen`: this one is a child of a `fixed inset-0`
      // overlay, and `100vh` on iOS Safari is the *large* viewport -- taller
      // than what is on screen -- so the bottom of the graph and its caption
      // sat under the browser chrome. Same correction as `AdminLayout`.
      className={`relative w-full ${isFullscreen ? 'h-dvh' : 'h-[75vh] min-h-[500px]'}`}
      onMouseMove={handleMouseMove}
      onDoubleClick={() => {
        if (hoveredNode) handleNodeDoubleClick(hoveredNode);
      }}
    >
      {dimensions.width > 0 && dimensions.height > 0 && (
        <GraphCanvas
          ref={canvasRef}
          data={graphData}
          centerNode={centerNode}
          onNodeClick={handleNodeClick}
          onNodeHover={handleNodeHover}
          width={dimensions.width}
          height={dimensions.height}
          focusRect={focusRect}
        />
      )}
      <GraphTooltip node={hoveredNode} position={tooltipPos} />
      {/*
        The legend and the controls share one absolutely positioned flex strip,
        rather than two independent `absolute` corners. Measured before this:
        at 393 px the legend spanned x 53..352 and the controls x 116..340, both
        starting at y 37 -- so the controls were drawn *over* the legend's
        right-hand items and hid them, and the same collision happened at 900 px.
        Two absolutes in one corner cannot know about each other; one flex row
        can. On a phone they stack (controls first, they are the actions), from
        `md` up they sit on one line at either end.
      */}
      <div
        ref={stripRef}
        className={`absolute ${edgeTop} ${edgeLeft} ${edgeRight} flex flex-col gap-2 pointer-events-none md:flex-row md:items-start md:justify-between`}
      >
        <div className="order-2 min-w-0 md:order-1 md:flex-1">
          <GraphLegend />
        </div>
        <div className="order-1 flex justify-end md:order-2 md:flex-none">
          <GraphControls
            onZoomIn={() => canvasRef.current?.zoomIn()}
            onZoomOut={() => canvasRef.current?.zoomOut()}
            // The ⟲ is how a reader who has panned or zoomed hands the framing
            // back to the graph, so it re-arms the automatic fit as well.
            onReset={() => canvasRef.current?.fitToView()}
            onExportPng={() => canvasRef.current?.exportPng()}
            onToggleFullscreen={() => setIsFullscreen(prev => !prev)}
            isFullscreen={isFullscreen}
            nodeCount={graphData.nodes.length}
            truncated={truncated}
          />
        </div>
      </div>
      <p ref={captionRef} className={`absolute ${edgeBottom} ${edgeLeft} text-xs text-gray-400 dark:text-gray-500 pointer-events-none`}>
        {isFullscreen ? 'Esc pre zatvorenie. ' : ''}Klikni na firmu pre rozbalenie prepojení. Dvojklik na firmu alebo osobu otvorí jej stránku.
      </p>
    </div>
  );

  if (isFullscreen) {
    return createPortal(
      <div className="fixed inset-0 z-[9999] bg-white dark:bg-slate-950 animate-fade-in">
        {graphContent}
      </div>,
      document.body
    );
  }

  return graphContent;
}
