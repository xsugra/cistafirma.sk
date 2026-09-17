export interface GraphNode {
  id: string;
  type: 'company' | 'person';
  label: string;
  ico?: string;
  status?: string;
  rolesCount?: number;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  role: string;
  /**
   * Three answers, not two: `true` the register states the function is current,
   * `false` it states it ended, `null` we have never read the function's
   * history for this company and therefore do not know.
   *
   * The third value is not a gap to paper over. Until 2026-09-13 the backend
   * wrote `true` for every relation it extracted, so the graph claimed 64 128
   * current offices, six of them in a dissolved družstvo. Drawing `null` as
   * "ended" would be the same mistake pointing the other way.
   */
  isActive: boolean | null;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphEdge[];
}

export interface GraphApiResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta: {
    center_node: string;
    depth: number;
    total_nodes: number;
    truncated: boolean;
  };
}
