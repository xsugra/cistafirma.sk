import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { GraphCanvas, type GraphCanvasHandle } from './GraphCanvas';
import { GraphControls } from './GraphControls';
import { GraphTooltip } from './GraphTooltip';
import { GraphLegend } from './GraphLegend';
import { useGraphData } from './useGraphData';
import type { GraphNode } from './graphTypes';
import { ROUTES } from '../../constants';

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

  const { graphData, loading, error, fetchGraph, expandNode, expandPerson, centerNode, truncated } = useGraphData();

  useEffect(() => {
    fetchGraph(ico);
  }, [ico, fetchGraph]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const measure = () => {
      const rect = container.getBoundingClientRect();
      setDimensions({
        width: rect.width,
        height: Math.max(rect.height, 400),
      });
    };

    measure();

    const observer = new ResizeObserver(() => measure());
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

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
    const rect = containerRef.current?.getBoundingClientRect();
    if (rect) {
      setTooltipPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    }
  }, []);

  const handleNodeDoubleClick = useCallback((node: GraphNode) => {
    if (node.type === 'company' && node.ico) {
      navigate(`${ROUTES.MONITORING}?ico=${encodeURIComponent(node.ico)}`);
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

  return (
    <div
      ref={containerRef}
      className="relative h-[75vh] min-h-[500px]"
      onMouseMove={handleMouseMove}
      onDoubleClick={(e) => {
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
          nodeCount={graphData.nodes.length}
          truncated={truncated}
        />
      </div>
      <p className="absolute bottom-2 left-3 text-xs text-gray-400 dark:text-gray-500 pointer-events-none">
        Klikni na firmu pre rozbalenie prepojení. Dvojklik pre otvorenie detailu.
      </p>
    </div>
  );
}
