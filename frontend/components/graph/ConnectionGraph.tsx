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

  const graphContent = (
    <div
      ref={containerRef}
      className={`relative w-full ${isFullscreen ? 'h-screen' : 'h-[75vh] min-h-[500px]'}`}
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
      <div className="absolute top-3 left-3 pointer-events-none">
        <GraphLegend />
      </div>
      <div className="absolute top-3 right-3 pointer-events-none">
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
      <p className="absolute bottom-2 left-3 text-xs text-gray-400 dark:text-gray-500 pointer-events-none">
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
