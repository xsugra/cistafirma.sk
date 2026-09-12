import type { Company, OrsrStructured, OrsrPerson, Financials } from '../types';
import type { GraphNode, GraphEdge } from '../components/graph/graphTypes';
import { API_BASE_URL } from '../constants';
import { getLegalFormProfile } from './legalFormProfile';
import { normalizePeople, formatDate, normalizeAmountText } from '../components/company/helpers';
import { formatNumber } from './format';

// ── helpers ────────────────────────────────────────────────────────

function esc(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function eur(amount: number): string {
  return `${formatNumber(amount)} €`;
}

function eurCompact(amount: number | null): string {
  // A figure the statement did not carry is not a zero, and printing `0 €` in
  // an exported document is a claim about the company that nothing supports.
  if (amount == null) return '—';
  if (Math.abs(amount) >= 1_000_000) return (amount / 1_000_000).toFixed(1) + 'M €';
  if (Math.abs(amount) >= 1_000) return Math.round(amount / 1_000) + 'k €';
  return `${formatNumber(amount)} €`;
}

function pct(value: number | null): string {
  if (value == null) return '—';
  return value.toFixed(2) + ' %';
}

function fmtDate(dateStr?: string | null): string {
  if (!dateStr) return '—';
  const d = formatDate(dateStr);
  return d || '—';
}

// ── graph fetch ────────────────────────────────────────────────────

interface GraphResult {
  nodes: GraphNode[];
  edges: GraphEdge[];
  centerNode: string;
}

async function fetchGraph(ico: string): Promise<GraphResult | null> {
  try {
    const r = await fetch(`${API_BASE_URL}/companies/${ico}/graph/`);
    if (!r.ok) return null;
    const d = await r.json();
    return { nodes: d.nodes, edges: d.edges, centerNode: d.meta.center_node };
  } catch {
    return null;
  }
}

// ── hierarchical graph layout ──────────────────────────────────────

interface LayoutNode {
  id: string;
  type: 'company' | 'person';
  label: string;
  layer: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface LayoutResult {
  nodes: LayoutNode[];
  edges: { sx: number; sy: number; tx: number; ty: number; role: string }[];
  width: number;
  height: number;
}

function deduplicateEdges(edges: GraphEdge[]): GraphEdge[] {
  const seen = new Set<string>();
  return edges.filter(e => {
    const src = typeof e.source === 'object' ? (e.source as any).id : e.source;
    const tgt = typeof e.target === 'object' ? (e.target as any).id : e.target;
    const key = `${src}-${tgt}-${e.role}`;
    const reverseKey = `${tgt}-${src}-${e.role}`;
    if (seen.has(key) || seen.has(reverseKey)) return false;
    seen.add(key);
    return true;
  });
}

// ── SVG diagram for small graphs (<=15 nodes) ────────────────────

function layoutGraph(nodes: GraphNode[], edges: GraphEdge[], centerNodeId: string): LayoutResult {
  if (nodes.length === 0) return { nodes: [], edges: [], width: 0, height: 0 };

  const MAX_W = 520;
  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  const adj = new Map<string, { neighbor: string; role: string }[]>();
  for (const n of nodes) adj.set(n.id, []);
  for (const e of edges) {
    const src = typeof e.source === 'object' ? (e.source as any).id : e.source;
    const tgt = typeof e.target === 'object' ? (e.target as any).id : e.target;
    adj.get(src)?.push({ neighbor: tgt, role: e.role });
    adj.get(tgt)?.push({ neighbor: src, role: e.role });
  }

  // BFS layer assignment
  const layerOf = new Map<string, number>();
  const queue = [centerNodeId];
  layerOf.set(centerNodeId, 0);
  while (queue.length > 0) {
    const cur = queue.shift()!;
    for (const { neighbor } of adj.get(cur) || []) {
      if (!layerOf.has(neighbor)) {
        layerOf.set(neighbor, layerOf.get(cur)! + 1);
        queue.push(neighbor);
      }
    }
  }
  for (const n of nodes) {
    if (!layerOf.has(n.id)) layerOf.set(n.id, (layerOf.size > 0 ? Math.max(...layerOf.values()) + 1 : 0));
  }

  const maxLayer = Math.max(...layerOf.values(), 0);
  const layers: string[][] = Array.from({ length: maxLayer + 1 }, () => []);
  for (const [id, layer] of layerOf) layers[layer].push(id);

  // Barycenter crossing reduction
  for (let iter = 0; iter < 3; iter++) {
    for (let l = 1; l <= maxLayer; l++) {
      const prevOrder = new Map(layers[l - 1].map((id, i) => [id, i]));
      const bary = new Map<string, number>();
      for (const id of layers[l]) {
        const neighbors = (adj.get(id) || [])
          .map(e => e.neighbor)
          .filter(n => layerOf.get(n) === l - 1);
        if (neighbors.length > 0) {
          bary.set(id, neighbors.reduce((s, n) => s + (prevOrder.get(n) ?? 0), 0) / neighbors.length);
        } else {
          bary.set(id, layers[l].indexOf(id));
        }
      }
      layers[l].sort((a, b) => (bary.get(a) ?? 0) - (bary.get(b) ?? 0));
    }
  }

  const CHAR_W = 5.2;
  const NODE_H = 22;
  const COMPANY_EXTRA = 8;
  const GAP_X = 14;
  const GAP_Y = 50;
  const PAD = 15;

  function nodeWidth(id: string): number {
    const n = nodeMap.get(id);
    if (!n) return 60;
    const textW = n.label.length * CHAR_W + 16;
    return Math.max(textW, n.type === 'company' ? 80 : 60);
  }

  // Split wide layers into sub-rows to fit MAX_W
  interface SubRow { ids: string[]; width: number }
  const allSubRows: { layer: number; subRows: SubRow[] }[] = [];

  for (let l = 0; l <= maxLayer; l++) {
    const subRows: SubRow[] = [];
    let curRow: string[] = [];
    let curW = 0;
    for (const id of layers[l]) {
      const w = nodeWidth(id);
      const needed = curRow.length > 0 ? curW + GAP_X + w : w;
      if (curRow.length > 0 && needed > MAX_W - PAD * 2) {
        subRows.push({ ids: curRow, width: curW });
        curRow = [id];
        curW = w;
      } else {
        curRow.push(id);
        curW = needed;
      }
    }
    if (curRow.length > 0) subRows.push({ ids: curRow, width: curW });
    allSubRows.push({ layer: l, subRows });
  }

  const positioned: LayoutNode[] = [];
  const posMap = new Map<string, { x: number; y: number; w: number; h: number }>();
  let yOffset = PAD;

  for (const { subRows } of allSubRows) {
    for (const sr of subRows) {
      let x = PAD + (MAX_W - PAD * 2 - sr.width) / 2;
      for (const id of sr.ids) {
        const n = nodeMap.get(id)!;
        const w = nodeWidth(id);
        const h = n.type === 'company' ? NODE_H + COMPANY_EXTRA : NODE_H;
        const cx = x + w / 2;
        const cy = yOffset + h / 2;
        positioned.push({ id, type: n.type, label: n.label, layer: 0, x: cx, y: cy, w, h });
        posMap.set(id, { x: cx, y: cy, w, h });
        x += w + GAP_X;
      }
      yOffset += NODE_H + COMPANY_EXTRA + 8;
    }
    yOffset += GAP_Y - NODE_H - COMPANY_EXTRA - 8;
  }

  const uniqueEdges = deduplicateEdges(edges);
  const layoutEdges: LayoutResult['edges'] = [];
  for (const e of uniqueEdges) {
    const src = typeof e.source === 'object' ? (e.source as any).id : e.source;
    const tgt = typeof e.target === 'object' ? (e.target as any).id : e.target;
    const sp = posMap.get(src);
    const tp = posMap.get(tgt);
    if (!sp || !tp) continue;
    const sBelow = sp.y < tp.y;
    layoutEdges.push({
      sx: sp.x,
      sy: sBelow ? sp.y + sp.h / 2 : sp.y - sp.h / 2,
      tx: tp.x,
      ty: sBelow ? tp.y - tp.h / 2 : tp.y + tp.h / 2,
      role: e.role,
    });
  }

  return {
    nodes: positioned,
    edges: layoutEdges,
    width: MAX_W,
    height: yOffset + PAD,
  };
}

function buildGraphSvg(graph: GraphResult): string {
  const layout = layoutGraph(graph.nodes, graph.edges, graph.centerNode);
  if (layout.nodes.length === 0) return '';

  const vw = layout.width;
  const vh = layout.height;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${vw} ${vh}" width="100%" style="display:block;margin:0 auto;">`;

  interface LabelBox { x: number; y: number; w: number; h: number }
  const placedLabels: LabelBox[] = [];

  function boxOverlaps(a: LabelBox, b: LabelBox): boolean {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  function tryPlaceLabel(cx: number, cy: number, text: string): string | null {
    const estW = text.length * 3.5 + 6;
    const estH = 8;
    const box: LabelBox = { x: cx - estW / 2, y: cy - estH / 2, w: estW, h: estH };
    if (placedLabels.some(p => boxOverlaps(p, box))) return null;
    placedLabels.push(box);
    return `<text x="${cx}" y="${cy + 2.5}" text-anchor="middle" font-size="6" fill="#888">${esc(text)}</text>`;
  }

  for (const e of layout.edges) {
    svg += `<line x1="${e.sx}" y1="${e.sy}" x2="${e.tx}" y2="${e.ty}" stroke="#bbb" stroke-width="0.8"/>`;
    const positions = [0.5, 0.3, 0.7];
    for (const t of positions) {
      const lx = e.sx + (e.tx - e.sx) * t;
      const ly = e.sy + (e.ty - e.sy) * t - 3;
      const label = tryPlaceLabel(lx, ly, e.role);
      if (label) { svg += label; break; }
    }
  }

  for (const n of layout.nodes) {
    const isCenter = n.id === graph.centerNode;
    if (n.type === 'company') {
      svg += `<rect x="${n.x - n.w / 2}" y="${n.y - n.h / 2}" width="${n.w}" height="${n.h}" rx="4" fill="${isCenter ? '#f0f0f0' : '#fff'}" stroke="${isCenter ? '#000' : '#555'}" stroke-width="${isCenter ? 2 : 1}"/>`;
      svg += `<text x="${n.x}" y="${n.y + 4}" text-anchor="middle" font-size="7.5" font-weight="${isCenter ? 'bold' : 'normal'}" fill="#000">${esc(n.label)}</text>`;
    } else {
      const rx = n.w / 2;
      const ry = n.h / 2;
      svg += `<ellipse cx="${n.x}" cy="${n.y}" rx="${rx}" ry="${ry}" fill="#fff" stroke="#888" stroke-width="1"/>`;
      svg += `<text x="${n.x}" y="${n.y + 3.5}" text-anchor="middle" font-size="7" fill="#333">${esc(n.label)}</text>`;
    }
  }

  svg += '</svg>';
  return svg;
}

// ── Table-based view for large graphs (>15 nodes) ────────────────

function buildGraphTable(graph: GraphResult): string {
  const uniqueEdges = deduplicateEdges(graph.edges);
  const nodeMap = new Map(graph.nodes.map(n => [n.id, n]));

  // Group edges by center perspective: person→companies, company→people
  const centerNode = nodeMap.get(graph.centerNode);
  const connections = new Map<string, { node: GraphNode; roles: string[] }>();

  for (const e of uniqueEdges) {
    const src = typeof e.source === 'object' ? (e.source as any).id : e.source;
    const tgt = typeof e.target === 'object' ? (e.target as any).id : e.target;
    const otherId = src === graph.centerNode ? tgt : (tgt === graph.centerNode ? src : null);

    if (otherId) {
      const existing = connections.get(otherId);
      if (existing) {
        if (!existing.roles.includes(e.role)) existing.roles.push(e.role);
      } else {
        const node = nodeMap.get(otherId);
        if (node) connections.set(otherId, { node, roles: [e.role] });
      }
    }
  }

  // Also build indirect connections (depth 2+)
  const directIds = new Set(connections.keys());
  const indirect = new Map<string, { node: GraphNode; via: string; roles: string[] }>();

  for (const e of uniqueEdges) {
    const src = typeof e.source === 'object' ? (e.source as any).id : e.source;
    const tgt = typeof e.target === 'object' ? (e.target as any).id : e.target;
    if (src === graph.centerNode || tgt === graph.centerNode) continue;

    const fromDirect = directIds.has(src) ? src : (directIds.has(tgt) ? tgt : null);
    if (!fromDirect) continue;
    const otherId = fromDirect === src ? tgt : src;
    if (directIds.has(otherId)) continue;

    const existing = indirect.get(otherId);
    const viaNode = nodeMap.get(fromDirect);
    const viaLabel = viaNode?.label || fromDirect;
    if (existing) {
      if (!existing.roles.includes(e.role)) existing.roles.push(e.role);
    } else {
      const node = nodeMap.get(otherId);
      if (node) indirect.set(otherId, { node, via: viaLabel, roles: [e.role] });
    }
  }

  // Split direct connections by type
  const people = [...connections.values()].filter(c => c.node.type === 'person');
  const companies = [...connections.values()].filter(c => c.node.type === 'company');
  const indirectList = [...indirect.values()];

  let html = '';

  if (people.length > 0) {
    html += '<h3>Priame prepojenia — Osoby</h3>';
    html += '<table class="compact"><thead><tr><th>Meno</th><th>Rola</th></tr></thead><tbody>';
    for (const p of people) {
      html += `<tr><td>${esc(p.node.label)}</td><td>${esc(p.roles.join(', '))}</td></tr>`;
    }
    html += '</tbody></table>';
  }

  if (companies.length > 0) {
    html += '<h3>Priame prepojenia — Firmy</h3>';
    html += '<table class="compact"><thead><tr><th>Firma</th><th>IČO</th><th>Rola</th></tr></thead><tbody>';
    for (const c of companies) {
      html += `<tr><td>${esc(c.node.label)}</td><td>${esc(c.node.ico || '—')}</td><td>${esc(c.roles.join(', '))}</td></tr>`;
    }
    html += '</tbody></table>';
  }

  if (indirectList.length > 0) {
    html += '<h3>Nepriame prepojenia</h3>';
    html += '<table class="compact"><thead><tr><th>Subjekt</th><th>Typ</th><th>Cez</th><th>Rola</th></tr></thead><tbody>';
    for (const c of indirectList) {
      const typeLabel = c.node.type === 'company' ? 'Firma' : 'Osoba';
      html += `<tr><td>${esc(c.node.label)}</td><td>${esc(typeLabel)}</td><td>${esc(c.via)}</td><td>${esc(c.roles.join(', '))}</td></tr>`;
    }
    html += '</tbody></table>';
  }

  return html;
}

// ── Graph section builder (auto-selects SVG or table) ────────────

function buildGraphSection(graph: GraphResult): string {
  const SVG_THRESHOLD = 15;
  const useTable = graph.nodes.length > SVG_THRESHOLD;

  if (useTable) {
    return `<div class="section page-break"><h2>Prepojenia osôb a firiem</h2>
      <p class="small" style="margin-bottom:6pt">${graph.nodes.length} subjektov, ${deduplicateEdges(graph.edges).length} prepojení</p>
      ${buildGraphTable(graph)}</div>`;
  }

  return `<div class="section page-break"><h2>Prepojenia osôb a firiem</h2>
    <div class="graph-legend"><span>▮ Firma</span> <span>◯ Osoba</span> <span>— rola</span></div>
    ${buildGraphSvg(graph)}</div>`;
}

// ── HTML sections ──────────────────────────────────────────────────

function buildHeader(c: Company): string {
  const orsr = c.orsr_profile;
  const address = orsr?.sidlo || `${c.address.street}, ${c.address.city} ${c.address.zipCode}`;
  const reg = orsr?.oddiel && orsr?.vlozka_cislo ? `Oddiel: ${orsr.oddiel}, Vložka: ${orsr.vlozka_cislo}` : '';
  return `
<div class="header">
  <h1>${esc(c.name)}</h1>
  <table class="meta"><tbody>
    <tr><td>IČO</td><td><b>${esc(c.ico)}</b></td><td>Právna forma</td><td>${esc(c.legalForm)}</td></tr>
    <tr><td>Sídlo</td><td colspan="3">${esc(address)}</td></tr>
    <tr><td>Dátum vzniku</td><td>${fmtDate(orsr?.den_zapisu || c.registrationDate)}</td><td>Stav</td><td>${esc(c.status)}</td></tr>
    ${reg ? `<tr><td>Register</td><td colspan="3">${esc(reg)}</td></tr>` : ''}
    ${c.vatStatus.icDph ? `<tr><td>IČ DPH</td><td>${esc(c.vatStatus.icDph)}</td><td>Spoľahlivosť</td><td>${esc(c.vatStatus.taxReliabilityIndex)}</td></tr>` : ''}
  </tbody></table>
</div>`;
}

function buildSummary(c: Company): string {
  const totalDebt = c.debts.reduce((s, d) => s + d.amountEur, 0);
  // An absent score prints a dash, not `null` and not a green 100. The report
  // is the artefact that gets forwarded, so a figure invented here would
  // outlive the screen it came from.
  const score = c.riskScore.score;
  return `
<div class="cols-3">
  <div class="box">
    <div class="box-label">Rizikové skóre</div>
    <div class="box-value">${score === null ? '—' : `${score} / 100`}</div>
    <div class="box-sub">${esc(c.riskScore.summary || (score === null ? 'Skóre sa nepodarilo načítať.' : ''))}</div>
  </div>
  <div class="box">
    <div class="box-label">Celkové dlhy</div>
    <div class="box-value ${totalDebt > 0 ? 'negative' : ''}">${eur(totalDebt)}</div>
    <div class="box-sub">${totalDebt > 0 ? c.debts.length + ' záznam(ov)' : 'Bez dlhov'}</div>
  </div>
  <div class="box">
    <div class="box-label">DPH status</div>
    <div class="box-value">${c.vatStatus.isVatPayer ? 'Platiteľ' : 'Neplatiteľ'}</div>
    <div class="box-sub">${esc(c.vatStatus.taxReliabilityIndex)}</div>
  </div>
</div>`;
}

function buildDebts(c: Company): string {
  if (c.debts.length === 0) return `<div class="section"><h2>Dlhy a nedoplatky</h2><p class="ok">Neboli nájdené žiadne aktuálne dlhy.</p></div>`;
  const totalDebt = c.debts.reduce((s, d) => s + d.amountEur, 0);
  let rows = c.debts.map(d =>
    `<tr><td>${esc(d.source)}</td><td class="r">${eur(d.amountEur)}</td><td>${fmtDate(d.dateOfRecord)}</td></tr>`
  ).join('');
  rows += `<tr class="total"><td><b>Celkom</b></td><td class="r"><b>${eur(totalDebt)}</b></td><td></td></tr>`;
  return `<div class="section"><h2>Dlhy a nedoplatky</h2><table><thead><tr><th>Zdroj</th><th class="r">Suma</th><th>K dátumu</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

/** Does this year's statement carry a composition, not just the two totals? */
function hasBreakdown(f: Financials): boolean {
  return [
    f.assetsIntangible, f.assetsTangible, f.assetsFinancial, f.assetsInventory,
    f.assetsReceivablesLong, f.assetsReceivablesShort, f.assetsFinancialAccounts,
    f.assetsAccruals, f.equityBasic, f.equityCapitalFunds, f.equityProfitFunds,
    f.equityRetained, f.liabilitiesReserves, f.liabilitiesLong, f.liabilitiesShort,
    f.liabilitiesAccruals,
  ].some(v => v != null);
}

function buildFinancials(c: Company): string {
  if (c.financials.length === 0) return `<div class="section"><h2>Finančné údaje</h2><p class="empty">Finančné údaje nie sú k dispozícii.</p></div>`;

  const sorted = [...c.financials].sort((a, b) => b.year - a.year);
  const latest = sorted[0];

  // Key indicators
  let kpi = `<div class="section"><h2>Kľúčové ukazovatele ${latest.year}</h2><table><tbody>`;
  // Two rows, because the statement has two. Both used to read `profit`, which
  // held whichever of the two the parser picked by absolute value -- so the KPI
  // block printed the operating result under the label "Zisk po zdanení" for
  // 86 % of the rows where the question can be settled at all.
  const rows: [string, string][] = [
    ['Celkové výnosy', eurCompact(latest.totalRevenue ?? latest.revenue)],
    ['Výsledok hospodárenia z hospodárskej činnosti', eurCompact(latest.profit)],
    ['Zisk po zdanení', eurCompact(latest.profitAfterTax)],
  ];
  if (latest.assetsTotal != null) {
    rows.push(
      ['Celkové aktíva', eurCompact(latest.assetsTotal)],
      ['Vlastný kapitál', eurCompact(latest.equity)],
      ['Celková zadlženosť', pct(latest.debtRatio)],
      ['Hrubá marža', pct(latest.grossMargin)],
    );
  }
  rows.push(
    ['Daň z príjmov', eurCompact(latest.incomeTax)],
    ['Náklady', eurCompact(latest.costs)],
  );
  kpi += rows.map(([l, v]) => `<tr><td>${l}</td><td class="r"><b>${v}</b></td></tr>`).join('');
  kpi += '</tbody></table></div>';

  // Financial history table
  let hist = `<div class="section"><h2>Hospodárske výsledky</h2><table class="compact"><thead><tr><th>Rok</th><th class="r">Výnosy</th><th class="r">VH z hosp. č.</th><th class="r">Zisk po zd.</th><th class="r">Náklady</th><th class="r">Aktíva</th><th class="r">Vlast. kap.</th><th class="r">Zadlž.</th><th class="r">Marža</th></tr></thead><tbody>`;
  for (const f of sorted) {
    hist += `<tr>
      <td><b>${f.year}</b></td>
      <td class="r">${eurCompact(f.totalRevenue ?? f.revenue)}</td>
      <td class="r">${eurCompact(f.profit)}</td>
      <td class="r">${eurCompact(f.profitAfterTax)}</td>
      <td class="r">${eurCompact(f.costs)}</td>
      <td class="r">${eurCompact(f.assetsTotal)}</td>
      <td class="r">${eurCompact(f.equity)}</td>
      <td class="r">${pct(f.debtRatio)}</td>
      <td class="r">${pct(f.grossMargin)}</td>
    </tr>`;
  }
  hist += '</tbody></table></div>';

  // Assets & liabilities breakdown for the latest year that has one. The
  // breakdown is only worth a page when there is a breakdown to print: a
  // statement can file `Aktíva celkom` with no readable composition, and that
  // would render sixteen rows of dashes into the exported document.
  let balance = '';
  const bal = sorted.find(hasBreakdown);
  if (bal) {
    balance = `<div class="section"><h2>Štruktúra majetku a záväzkov ${bal.year}</h2>
    <div class="cols-2">
      <div>
        <h3>Aktíva</h3>
        <table class="compact"><tbody>
          <tr><td>Nehmotný majetok</td><td class="r">${eurCompact(bal.assetsIntangible)}</td></tr>
          <tr><td>Hmotný majetok</td><td class="r">${eurCompact(bal.assetsTangible)}</td></tr>
          <tr><td>Finančný majetok</td><td class="r">${eurCompact(bal.assetsFinancial)}</td></tr>
          <tr><td>Zásoby</td><td class="r">${eurCompact(bal.assetsInventory)}</td></tr>
          <tr><td>Dlhodobé pohľadávky</td><td class="r">${eurCompact(bal.assetsReceivablesLong)}</td></tr>
          <tr><td>Krátkodobé pohľadávky</td><td class="r">${eurCompact(bal.assetsReceivablesShort)}</td></tr>
          <tr><td>Finančné účty</td><td class="r">${eurCompact(bal.assetsFinancialAccounts)}</td></tr>
          <tr class="total"><td><b>Aktíva celkom</b></td><td class="r"><b>${eurCompact(bal.assetsTotal)}</b></td></tr>
        </tbody></table>
      </div>
      <div>
        <h3>Pasíva</h3>
        <table class="compact"><tbody>
          <tr><td>Základné imanie</td><td class="r">${eurCompact(bal.equityBasic)}</td></tr>
          <tr><td>Kapitálové fondy</td><td class="r">${eurCompact(bal.equityCapitalFunds)}</td></tr>
          <tr><td>Fondy zo zisku</td><td class="r">${eurCompact(bal.equityProfitFunds)}</td></tr>
          <tr><td>Nerozdelený VH</td><td class="r">${eurCompact(bal.equityRetained)}</td></tr>
          <tr class="total"><td><b>Vlastný kapitál</b></td><td class="r"><b>${eurCompact(bal.equity)}</b></td></tr>
          <tr><td>Rezervy</td><td class="r">${eurCompact(bal.liabilitiesReserves)}</td></tr>
          <tr><td>Dlhodobé záväzky</td><td class="r">${eurCompact(bal.liabilitiesLong)}</td></tr>
          <tr><td>Krátkodobé záväzky</td><td class="r">${eurCompact(bal.liabilitiesShort)}</td></tr>
          <tr class="total"><td><b>Záväzky celkom</b></td><td class="r"><b>${eurCompact(bal.liabilitiesTotal)}</b></td></tr>
        </tbody></table>
      </div>
    </div>
    </div>`;
  }

  return kpi + hist + balance;
}

function personRow(p: OrsrPerson): string {
  const name = [p.title, p.name].filter(Boolean).join(' ');
  const addr = p.address || p.address_lines?.join(', ') || '';
  const date = p.vznik_funkcie ? fmtDate(p.vznik_funkcie) : (p.od ? fmtDate(p.od) : '');
  return `<tr><td>${esc(name)}</td><td class="small">${esc(addr)}</td><td>${date}</td></tr>`;
}

function deduplicatePeople(people: OrsrPerson[]): OrsrPerson[] {
  const seen = new Set<string>();
  return people.filter(p => {
    const key = p.name?.trim().toLowerCase() || '';
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function buildPeopleSection(title: string, people: OrsrPerson[]): string {
  const deduped = deduplicatePeople(people);
  if (deduped.length === 0) return '';
  return `<div class="subsection"><h3>${esc(title)}</h3><table class="compact"><thead><tr><th>Meno</th><th>Adresa</th><th>Od</th></tr></thead><tbody>${deduped.map(personRow).join('')}</tbody></table></div>`;
}

function buildPeople(c: Company, structured: OrsrStructured, profile: ReturnType<typeof getLegalFormProfile>): string {
  const orsr = c.orsr_profile;
  const statutari = normalizePeople(structured.statutarny_organ?.length ? structured.statutarny_organ : orsr?.statutarny_organ);
  const spolocnici = normalizePeople(structured.spolocnici?.length ? structured.spolocnici : orsr?.spolocnici);
  const prokuristy = normalizePeople(structured.prokura?.length ? structured.prokura : orsr?.prokura);
  const predstavenstvo = normalizePeople(structured.predstavenstvo?.length ? structured.predstavenstvo : orsr?.predstavenstvo);
  const dozornaRada = normalizePeople(structured.dozorna_rada || []);
  const kontrolnaKomisia = normalizePeople(structured.kontrolna_komisia?.length ? structured.kontrolna_komisia : orsr?.kontrolna_komisia);
  const akcionari = normalizePeople(structured.akcionari || []);

  let html = '<div class="section page-break"><h2>Osoby</h2>';

  const showPredstavenstvo = Boolean(profile.predstavenstvo);
  const showStatutar = Boolean(profile.statutar) && (statutari.length > 0) && (!showPredstavenstvo || predstavenstvo.length > 0);

  if (showPredstavenstvo && (predstavenstvo.length > 0 || statutari.length > 0)) {
    html += buildPeopleSection(profile.predstavenstvo!.title, predstavenstvo.length > 0 ? predstavenstvo : statutari);
  }
  if (showStatutar) {
    html += buildPeopleSection(profile.statutar!.title, statutari);
  }
  if (profile.spolocnici && spolocnici.length > 0) {
    html += buildPeopleSection(profile.spolocnici.title, spolocnici);
  }
  if (profile.akcionari && akcionari.length > 0) {
    html += buildPeopleSection(profile.akcionari.title, akcionari);
  }
  if (profile.dozornaRada && dozornaRada.length > 0) {
    html += buildPeopleSection(profile.dozornaRada.title, dozornaRada);
  }
  if (profile.kontrolnaKomisia && kontrolnaKomisia.length > 0) {
    html += buildPeopleSection(profile.kontrolnaKomisia.title, kontrolnaKomisia);
  }
  if (profile.prokura && prokuristy.length > 0) {
    html += buildPeopleSection(profile.prokura.title, prokuristy);
  }

  const konanie = orsr?.konanie_menom_spolocnosti || structured.konanie || orsr?.konanie || '';
  if (konanie) {
    html += `<div class="subsection"><h3>Konanie menom spoločnosti</h3><p class="pre">${esc(konanie)}</p></div>`;
  }

  html += '</div>';
  return html;
}

function buildCapital(c: Company, structured: OrsrStructured, profile: ReturnType<typeof getLegalFormProfile>): string {
  const orsr = c.orsr_profile;
  const capital = structured.vyska_zakladneho_imania;
  const vklady = structured.vklady_spolocnikov || [];
  const akcie = structured.akcie || [];

  const hasAnything = (capital?.imanie || orsr?.vyska_zakladneho_imania || vklady.length > 0 || akcie.length > 0);
  if (!hasAnything) return '';

  let html = '<div class="section"><h2>Kapitál a vklady</h2>';

  if (capital?.imanie) {
    html += `<p><b>Základné imanie:</b> ${esc(normalizeAmountText(capital.imanie))} ${esc(capital.currency || 'EUR')}`;
    if (capital.rozsah_splatenia) html += ` (splatené: ${esc(normalizeAmountText(capital.rozsah_splatenia))} ${esc(capital.currency || 'EUR')})`;
    html += '</p>';
  } else if (orsr?.vyska_zakladneho_imania) {
    html += `<p><b>Základné imanie:</b> ${esc(normalizeAmountText(orsr.vyska_zakladneho_imania))}</p>`;
  }

  if (orsr?.zapisovane_zakladne_imanie) {
    html += `<p><b>Zapisované základné imanie:</b> ${esc(normalizeAmountText(orsr.zapisovane_zakladne_imanie))}</p>`;
  }
  if (orsr?.zakladny_clensky_vklad) {
    html += `<p><b>Základný členský vklad:</b> ${esc(normalizeAmountText(orsr.zakladny_clensky_vklad))}</p>`;
  }

  if (vklady.length > 0) {
    html += '<h3>Vklady spoločníkov</h3><table class="compact"><thead><tr><th>Meno</th><th class="r">Vklad</th><th class="r">Splatené</th></tr></thead><tbody>';
    for (const v of vklady) {
      const cur = v.currency || 'EUR';
      html += `<tr><td>${esc(v.name)}</td><td class="r">${v.vklad ? esc(v.vklad + ' ' + cur) : '—'}</td><td class="r">${v.splatene ? esc(v.splatene + ' ' + cur) : '—'}</td></tr>`;
    }
    html += '</tbody></table>';
  }

  if (akcie.length > 0) {
    html += `<h3>Akcie (${akcie.length} ${akcie.length === 1 ? 'emisia' : akcie.length < 5 ? 'emisie' : 'emisií'})</h3><table class="compact"><thead><tr><th>Počet</th><th>Druh</th><th>Podoba</th><th>Forma</th><th>Menovitá hodnota</th></tr></thead><tbody>`;
    for (const a of akcie) {
      const t = a.text;
      const pocet = t.match(/Počet:\s*(\d[\d\s]*\d|\d)/i)?.[1]?.trim() || '—';
      const druh = t.match(/Druh:\s*(.+?)(?=\s+(?:Podoba|Forma|Menovitá|Obmedzenie)|$)/i)?.[1]?.trim() || '—';
      const podoba = t.match(/Podoba:\s*(.+?)(?=\s+(?:Forma|Menovitá|Obmedzenie)|$)/i)?.[1]?.trim() || '—';
      const forma = t.match(/Forma:\s*(.+?)(?=\s+(?:Menovitá|Obmedzenie)|$)/i)?.[1]?.trim() || '—';
      const mh = t.match(/Menovitá hodnota:\s*(.+?)(?=\s+Obmedzenie|$)/i)?.[1]?.trim() || '—';
      html += `<tr><td class="r">${esc(pocet)}</td><td>${esc(druh)}</td><td>${esc(podoba)}</td><td>${esc(forma)}</td><td class="r">${esc(mh)}</td></tr>`;
    }
    html += '</tbody></table>';
  }

  html += '</div>';
  return html;
}

function buildBusiness(c: Company, structured: OrsrStructured, profile: ReturnType<typeof getLegalFormProfile>): string {
  const predmety = structured.predmet_podnikania?.length
    ? structured.predmet_podnikania.map(p => p.text)
    : (c.orsr_profile?.predmet_podnikania || []);

  if (predmety.length === 0) return '';

  let html = '<div class="section"><h2>Predmety podnikania</h2><ol class="predmety">';
  for (const p of predmety) {
    html += `<li>${esc(p)}</li>`;
  }
  html += '</ol></div>';

  if (profile.dalsiePravneSkutocnosti && c.orsr_profile?.dalske_pravne_skutocnosti) {
    html += `<div class="section"><h2>Ďalšie právne skutočnosti</h2><p class="pre">${esc(c.orsr_profile.dalske_pravne_skutocnosti)}</p></div>`;
  }

  return html;
}

// ── main HTML builder ──────────────────────────────────────────────

function buildHTML(c: Company, graph: GraphResult | null): string {
  const profile = getLegalFormProfile((c.orsr_profile?.oddiel_type || '').toLowerCase());
  const structured: OrsrStructured = c.orsr_profile?.structured || {};

  const graphSection = graph ? buildGraphSection(graph) : '';

  const now = new Date().toLocaleDateString('sk-SK');

  return `<!DOCTYPE html><html lang="sk"><head><meta charset="UTF-8">
<title>${esc(c.name)} — Report</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',sans-serif;font-size:8.5pt;color:#000;background:#fff;padding:12mm 15mm;line-height:1.35}
h1{font-size:16pt;margin-bottom:2pt}
h2{font-size:11pt;border-bottom:1.5pt solid #000;padding-bottom:2pt;margin:12pt 0 6pt}
h3{font-size:9pt;margin:8pt 0 3pt;color:#333}
table{width:100%;border-collapse:collapse;font-size:8pt}
th,td{padding:3pt 5pt;text-align:left;vertical-align:top}
th{font-weight:600;border-bottom:1pt solid #000;white-space:nowrap}
td{border-bottom:0.5pt solid #ddd}
.r{text-align:right}
tr.total td{border-top:1pt solid #000;border-bottom:none;padding-top:4pt}
.meta{margin:4pt 0 0}
.meta td{border:none;padding:1.5pt 8pt 1.5pt 0;font-size:8pt}
.meta td:nth-child(odd){color:#666;white-space:nowrap}
.cols-3{display:flex;gap:8pt;margin:8pt 0}
.cols-2{display:flex;gap:12pt;margin:4pt 0}
.cols-2>div{flex:1;min-width:0}
.cols-3>div{flex:1;min-width:0}
.box{border:0.5pt solid #ccc;padding:6pt 8pt;text-align:center}
.box-label{font-size:6.5pt;text-transform:uppercase;letter-spacing:0.5pt;color:#666;margin-bottom:2pt}
.box-value{font-size:13pt;font-weight:700}
.box-value.negative{color:#c00}
.box-sub{font-size:7pt;color:#666;margin-top:1pt}
.section{margin-top:6pt}
.subsection{margin:6pt 0}
.compact td,.compact th{padding:2pt 4pt;font-size:7.5pt}
.ok{color:#060;font-size:8pt;padding:4pt;border:0.5pt solid #6c6;text-align:center}
.empty{color:#666;font-size:8pt;text-align:center;padding:4pt}
.pre{white-space:pre-line;font-size:8pt;line-height:1.4}
.small{font-size:7pt;color:#555}
.predmety{padding-left:14pt;font-size:8pt}
.predmety li{margin-bottom:2pt}
.graph-legend{font-size:7pt;color:#666;margin-bottom:4pt;display:flex;gap:12pt}
.footer{margin-top:16pt;padding-top:6pt;border-top:0.5pt solid #ccc;font-size:7pt;color:#999;display:flex;justify-content:space-between}
.page-break{page-break-before:always}
@media print{
  body{padding:10mm 12mm}
  .section{page-break-inside:avoid}
  .subsection{page-break-inside:avoid}
  table{page-break-inside:avoid}
  tr{page-break-inside:avoid}
  h2,h3,h4{page-break-after:avoid}
  .page-break{page-break-before:always}
  .no-print{display:none}
}
</style></head><body>
${buildHeader(c)}
${buildSummary(c)}
${buildDebts(c)}
${buildFinancials(c)}
${buildPeople(c, structured, profile)}
${buildCapital(c, structured, profile)}
${buildBusiness(c, structured, profile)}
${graphSection}
<div class="footer">
  <span>Vygenerované: ${now} • cistafirma.sk</span>
  <span>IČO: ${esc(c.ico)}</span>
</div>
<script>
document.fonts.ready.then(function(){setTimeout(function(){window.print()},400)});
</script>
</body></html>`;
}

// ── public API ─────────────────────────────────────────────────────

export async function exportCompanyPDF(company: Company): Promise<void> {
  const graph = await fetchGraph(company.ico);
  const html = buildHTML(company, graph);
  const win = window.open('', '_blank');
  if (!win) {
    alert('Povoľte vyskakovacie okná pre stiahnutie PDF.');
    return;
  }
  win.document.write(html);
  win.document.close();
}
