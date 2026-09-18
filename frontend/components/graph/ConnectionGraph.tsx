import { useEffect, useRef, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { GraphCanvas, type GraphCanvasHandle } from './GraphCanvas';
import { GraphControls } from './GraphControls';
import { GraphTooltip } from './GraphTooltip';
import { GraphLegend } from './GraphLegend';
import { useGraphData } from './useGraphData';
import type { GraphNode } from './graphTypes';
import { companyPath, personPath } from '../../constants';

interface ConnectionGraphProps {
  ico: string;
}

export function ConnectionGraph({ ico }: ConnectionGraphProps) {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<GraphCanvasHandle>(null);
  const [dimensions, setDimensions] = useState({ width: 1100, height: 1000 });
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);

  const { graphData, loading, error, fetchGraph, expandNode, expandPerson, centerNode, truncated } = useGraphData();

  useEffect(() => {
    fetchGraph(ico);
  }, [ico, fetchGraph]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const measure = () => {
      if (isFullscreen) {
        setDimensions({ width: window.innerWidth, height: window.innerHeight });
      } else {
        const rect = el.getBoundingClientRect();
        setDimensions({ width: rect.width, height: Math.max(rect.height, 400) });
      }
    };
    measure();

    if (isFullscreen) {
      window.addEventListener('resize', measure);
      return () => window.removeEventListener('resize', measure);
    }

    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [isFullscreen]);

  // Re-fit graph after fullscreen toggle
  useEffect(() => {
    if (canvasRef.current && graphData && graphData.nodes.length > 0) {
      const timer = setTimeout(() => canvasRef.current?.zoomToFit(), 150);
      return () => clearTimeout(timer);
    }
  }, [isFullscreen, graphData]);

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

  const graphContent = (
    <div
      ref={containerRef}
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
        className={`absolute ${edgeTop} ${edgeLeft} ${edgeRight} flex flex-col gap-2 pointer-events-none md:flex-row md:items-start md:justify-between`}
      >
        <div className="order-2 min-w-0 md:order-1 md:flex-1">
          <GraphLegend />
        </div>
        <div className="order-1 flex justify-end md:order-2 md:flex-none">
          <GraphControls
            onZoomIn={() => canvasRef.current?.zoomIn()}
            onZoomOut={() => canvasRef.current?.zoomOut()}
            onReset={() => canvasRef.current?.zoomToFit()}
            onExportPng={() => canvasRef.current?.exportPng()}
            onToggleFullscreen={() => setIsFullscreen(prev => !prev)}
            isFullscreen={isFullscreen}
            nodeCount={graphData.nodes.length}
            truncated={truncated}
          />
        </div>
      </div>
      <p className={`absolute ${edgeBottom} ${edgeLeft} text-xs text-gray-400 dark:text-gray-500 pointer-events-none`}>
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
