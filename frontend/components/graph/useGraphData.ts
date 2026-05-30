import { useState, useCallback } from 'react';
import { API_BASE_URL } from '../../constants';
import type { GraphData, GraphApiResponse, GraphNode, GraphEdge } from './graphTypes';

interface UseGraphDataReturn {
  graphData: GraphData | null;
  loading: boolean;
  error: string | null;
  fetchGraph: (ico: string) => Promise<void>;
  expandNode: (ico: string) => Promise<void>;
  expandPerson: (personId: string) => Promise<void>;
  centerNode: string | null;
  truncated: boolean;
}

export function useGraphData(): UseGraphDataReturn {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [centerNode, setCenterNode] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);

  const fetchGraph = useCallback(async (ico: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/companies/${ico}/graph/`);
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${response.status}`);
      }
      const data: GraphApiResponse = await response.json();

      setGraphData({
        nodes: data.nodes,
        links: data.edges,
      });
      setCenterNode(data.meta.center_node);
      setTruncated(data.meta.truncated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nepodarilo sa načítať graf prepojení');
      setGraphData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const expandNode = useCallback(async (ico: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/companies/${ico}/graph/`);
      if (!response.ok) return;
      const data: GraphApiResponse = await response.json();

      setGraphData((prev) => {
        if (!prev) return { nodes: data.nodes, links: data.edges };

        const existingNodeIds = new Set(prev.nodes.map((n) => n.id));
        const existingEdgeKeys = new Set(
          prev.links.map((e) => `${e.source}-${e.target}-${e.role}`)
        );

        const newNodes: GraphNode[] = [];
        for (const node of data.nodes) {
          if (!existingNodeIds.has(node.id)) {
            newNodes.push(node);
          }
        }

        const newEdges: GraphEdge[] = [];
        for (const edge of data.edges) {
          const key = `${edge.source}-${edge.target}-${edge.role}`;
          if (!existingEdgeKeys.has(key)) {
            newEdges.push(edge);
          }
        }

        return {
          nodes: [...prev.nodes, ...newNodes],
          links: [...prev.links, ...newEdges],
        };
      });

      if (data.meta.truncated) {
        setTruncated(true);
      }
    } catch {
      // Silently fail on expand — the main graph remains visible
    }
  }, []);

  const expandPerson = useCallback(async (personId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/persons/${personId}/graph/`);
      if (!response.ok) return;
      const data: GraphApiResponse = await response.json();

      setGraphData((prev) => {
        if (!prev) return { nodes: data.nodes, links: data.edges };

        const existingNodeIds = new Set(prev.nodes.map((n) => n.id));
        const existingEdgeKeys = new Set(
          prev.links.map((e) => `${e.source}-${e.target}-${e.role}`)
        );

        const newNodes: GraphNode[] = [];
        for (const node of data.nodes) {
          if (!existingNodeIds.has(node.id)) {
            newNodes.push(node);
          }
        }

        const newEdges: GraphEdge[] = [];
        for (const edge of data.edges) {
          const key = `${edge.source}-${edge.target}-${edge.role}`;
          if (!existingEdgeKeys.has(key)) {
            newEdges.push(edge);
          }
        }

        return {
          nodes: [...prev.nodes, ...newNodes],
          links: [...prev.links, ...newEdges],
        };
      });

      if (data.meta.truncated) {
        setTruncated(true);
      }
    } catch {
      // Silently fail — main graph remains visible
    }
  }, []);

  return { graphData, loading, error, fetchGraph, expandNode, expandPerson, centerNode, truncated };
}
