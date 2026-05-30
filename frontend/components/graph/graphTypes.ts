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
  isActive: boolean;
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
