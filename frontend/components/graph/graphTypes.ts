export interface GraphNode {
  id: string;
  type: 'company' | 'person';
  label: string;
  ico?: string;
  status?: string;
  rolesCount?: number;
  /**
   * What stands behind this one drawn person: how many register rows it
   * gathered, and how many of those identity resolution had kept apart.
   *
   * A person the register wrote twice is drawn once, and that is a judgement --
   * two rows with two addresses may be two people. The judgement is drawn from
   * the same evidence the person table uses, and where it folds over a refusal
   * (`clusters > 1`) the reader is told, so it can be disagreed with. Absent on
   * the graphs that do not gather people this way; `records` of 1 is the
   * ordinary case and renders nothing.
   */
  records?: number;
  clusters?: number;
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
    /**
     * The day this graph is drawn for, or `null` for today. Absent on the person
     * graph, which has no period control: a person's companies are not a period
     * of anything, and a field that endpoint never fills in must not read as
     * "today" on a screen that asked for a year.
     */
    as_of?: string | null;
    /**
     * The years worth offering, newest first -- the ones where the company's
     * record actually changes. Computed by the backend from the whole record,
     * so the chips do not move when one of them is chosen, and so the same row
     * of chips on the Osoby screen offers the same years.
     */
    periods?: number[];
    /**
     * How many relations the period filter could not place because the register
     * never stated a start date. A period view leaves them out -- they cannot be
     * shown to have run on any day -- and this is what keeps that silent drop
     * from being silent.
     */
    undated_excluded?: number;
  };
}
