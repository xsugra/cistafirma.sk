import { useState, useCallback } from 'react';
import { API_BASE_URL } from '../../constants';
import type { GraphData, GraphApiResponse, GraphNode, GraphEdge } from './graphTypes';

interface UseGraphDataReturn {
  graphData: GraphData | null;
  loading: boolean;
  error: string | null;
  fetchGraph: (ico: string, asOf?: string | null) => Promise<void>;
  expandNode: (ico: string) => Promise<void>;
  expandPerson: (personId: string) => Promise<void>;
  centerNode: string | null;
  truncated: boolean;
  /**
   * The years the company's record actually changes, newest first, as the
   * backend computed them. Empty for the person graph, which has no periods,
   * and empty until the first answer arrives -- so the control renders nothing
   * rather than an empty row.
   */
  periods: number[];
  /** Relations a period view could not place: the register stated no start. */
  undatedExcluded: number;
  /**
   * The day the graph **currently on the canvas** was drawn for, as the backend
   * echoed it back -- not the day the reader has just asked for.
   *
   * They differ for exactly as long as a request is in flight, and in that
   * window a caption reading the requested period would put "Stav k 31. 12.
   * 2015" above a picture of today. The backend refuses to answer a malformed
   * date for the same reason: a period named on screen must be the period shown.
   */
  drawnAsOf: string | null;
}

export function useGraphData(): UseGraphDataReturn {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [centerNode, setCenterNode] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [periods, setPeriods] = useState<number[]>([]);
  const [undatedExcluded, setUndatedExcluded] = useState(0);
  const [drawnAsOf, setDrawnAsOf] = useState<string | null>(null);

  /**
   * `asOf` is the day the graph is drawn for; `null` or omitted is today, which
   * is the call this made before the period control existed.
   *
   * The parameter is sent only when there is one. `?as_of=` with an empty value
   * means the same thing to the backend, but a request that says nothing about
   * a period is not the same request as one that asks for a specific day, and
   * only the second belongs in a URL somebody might read or share.
   */
  const fetchGraph = useCallback(async (ico: string, asOf?: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : '';
      const response = await fetch(`${API_BASE_URL}/companies/${ico}/graph/${query}`);
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
      setPeriods(data.meta.periods ?? []);
      setUndatedExcluded(data.meta.undated_excluded ?? 0);
      setDrawnAsOf(data.meta.as_of ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nepodarilo sa načítať graf prepojení');
      setGraphData(null);
      setDrawnAsOf(null);
      // The period row is cleared too, and for the same reason: `periods` is a
      // property of *a* company's record, and this answer did not arrive. Left
      // standing, the years of the company the reader came from would sit above
      // an error message and offer periods of a record that is not on screen.
      // The cost is that a failed period request takes the "Dnes" chip with it;
      // that is the lesser wrong, because a wrong year is a claim and a missing
      // control is only an inconvenience.
      setPeriods([]);
      setUndatedExcluded(0);
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

  return {
    graphData,
    loading,
    error,
    fetchGraph,
    expandNode,
    expandPerson,
    centerNode,
    truncated,
    periods,
    undatedExcluded,
    drawnAsOf,
  };
}
