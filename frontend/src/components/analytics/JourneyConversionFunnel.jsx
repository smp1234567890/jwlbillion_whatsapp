import React, { useMemo, useState } from "react";
import {
  ShoppingCart, Send, Clock, HelpCircle, Award, Filter,
  ZoomIn, ZoomOut, RotateCcw
} from "lucide-react";

/* ── Config ── */
const CFG = {
  trigger:          { bg: "bg-blue-500",    bar: "bg-blue-400",    count: "text-blue-900",   icon: ShoppingCart },
  whatsapp_message: { bg: "bg-violet-500",  bar: "bg-violet-400",  count: "text-violet-900", icon: Send },
  action_whatsapp:  { bg: "bg-violet-500",  bar: "bg-violet-400",  count: "text-violet-900", icon: Send },
  whatsapp:         { bg: "bg-violet-500",  bar: "bg-violet-400",  count: "text-violet-900", icon: Send },
  delay:            { bg: "bg-amber-500",   bar: "bg-amber-400",   count: "text-amber-900",  icon: Clock },
  condition:        { bg: "bg-purple-600",  bar: "bg-purple-400",  count: "text-purple-900", icon: HelpCircle },
  goal:             { bg: "bg-emerald-500", bar: "bg-emerald-400", count: "text-emerald-900",icon: Award },
  exit:             { bg: "bg-teal-500",    bar: "bg-teal-400",    count: "text-teal-900",   icon: Award },
};
const DFLT = CFG.trigger;

function resolveLabel(edge) {
  let l = edge.label || edge.data?.label || "";
  if (!l && edge.sourceHandle) {
    const h = String(edge.sourceHandle).toUpperCase();
    l = h.includes("YES") || h === "TRUE" ? "YES"
      : h.includes("NO")  || h === "FALSE" ? "NO"
      : edge.sourceHandle;
  }
  return l;
}

/* ── Primitives ── */
function VLine() { return <div className="w-0.5 h-7 bg-gray-200 mx-auto" />; }

function ArrowDown() {
  return (
    <div className="flex justify-center mb-0.5">
      <svg width="10" height="7" viewBox="0 0 10 7">
        <path d="M1 1 L5 5.5 L9 1" stroke="#CBD5E1" strokeWidth="1.5" fill="none"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

function BranchBadge({ label }) {
  const up = (label || "").toUpperCase();
  const isY = up.includes("YES") || up.includes("READ");
  const isN = up.includes("NO")  || up.includes("UNREAD");
  return (
    <span className={`px-2 py-0.5 rounded-full text-[9px] font-black border whitespace-nowrap ${
      isY ? "bg-emerald-50 border-emerald-300 text-emerald-700"
    : isN ? "bg-red-50 border-red-300 text-red-700"
    :       "bg-gray-100 border-gray-300 text-gray-600"}`}>
      {label || "→"}
    </span>
  );
}

/* ── Node card ── */
function NodeCard({ node, count, total, isSelected, onClick }) {
  const t   = (node?.type || "").toLowerCase();
  const cfg = CFG[t] || DFLT;
  const IC  = cfg.icon;
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  let label = node?.label || node?.data?.label || t;

  return (
    <button type="button" onClick={onClick}
      title={`${count} contacts · ${pct}%`}
      className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border-2 w-full max-w-[270px]
        cursor-pointer transition-all duration-150 shadow-sm
        ${isSelected
          ? `${cfg.bg} border-transparent ring-2 ring-offset-2 scale-[1.02] shadow-md`
          : "bg-white border-gray-200 hover:border-gray-300 hover:shadow-md"}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${cfg.bg}`}>
        <IC className="w-4 h-4 text-white" />
      </div>
      <div className="flex-1 text-left min-w-0">
        <div className={`text-[11px] font-semibold leading-snug truncate ${isSelected ? "text-white" : "text-gray-700"}`}>
          {label}
        </div>
        <div className={`font-black font-mono text-base leading-tight ${isSelected ? "text-white" : cfg.count}`}>
          {count}
        </div>
      </div>
      <div className="shrink-0 text-right min-w-[44px]">
        <div className={`text-[10px] font-mono ${isSelected ? "text-white/80" : "text-gray-500"}`}>{pct}%</div>
        <div className="w-10 h-1 bg-gray-100 rounded-full overflow-hidden mt-0.5">
          <div className={`h-full rounded-full ${isSelected ? "bg-white/60" : cfg.bar}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
    </button>
  );
}

/* ── Recursive vertical tree ── */
function VerticalTree({ nodeId, childMap, nodeMap, counts, total, selId, onSel, visited }) {
  if (!nodeId || visited.has(nodeId)) return null;
  const node = nodeMap[nodeId];
  if (!node) return null;

  const nv = new Set(visited); nv.add(nodeId);
  const children = (childMap[nodeId] || []).filter(c => !nv.has(c.target));
  const count    = counts[nodeId] ?? 0;
  const isSel    = selId === nodeId;

  const card = (
    <NodeCard node={node} count={count} total={total}
      isSelected={isSel} onClick={() => onSel(isSel ? null : nodeId)} />
  );

  if (children.length === 0) return <div className="flex flex-col items-center">{card}</div>;

  if (children.length === 1) {
    return (
      <div className="flex flex-col items-center">
        {card}
        <VLine /><ArrowDown />
        <VerticalTree nodeId={children[0].target} childMap={childMap} nodeMap={nodeMap}
          counts={counts} total={total} selId={selId} onSel={onSel} visited={nv} />
      </div>
    );
  }

  /* condition: YES first */
  const sorted = [...children].sort((a, b) => {
    const ay = (a.label||"").toUpperCase().includes("YES");
    const by = (b.label||"").toUpperCase().includes("YES");
    return ay && !by ? -1 : !ay && by ? 1 : 0;
  });

  return (
    <div className="flex flex-col items-center">
      {card}
      <VLine />
      <div className="flex items-start gap-0">
        {sorted.map((child, i) => {
          const childCount = counts[child.target] ?? 0;
          const childPct   = count > 0 ? Math.round((childCount / count) * 100) : 0;
          const isLast     = i === sorted.length - 1;
          return (
            <div key={`${child.target}_${i}`}
              className={`flex flex-col items-center px-5 pt-0
                ${!isLast ? "border-t border-r border-gray-200" : "border-t border-gray-200"}`}>
              <div className="h-4 w-0.5 bg-gray-200 mx-auto" />
              <div className="flex flex-col items-center mb-1">
                <BranchBadge label={child.label} />
                <span className="text-[8px] font-mono text-gray-400 mt-0.5">{childPct}%</span>
              </div>
              <div className="h-3 w-0.5 bg-gray-200 mx-auto" />
              <ArrowDown />
              <VerticalTree nodeId={child.target} childMap={childMap} nodeMap={nodeMap}
                counts={counts} total={total} selId={selId} onSel={onSel} visited={nv} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   MAIN EXPORT
═══════════════════════════════════════════ */
export default function JourneyConversionFunnel({
  flow, sessions = [], selectedStepId, onSelectStep, maxHeight = "520px"
}) {
  const [zoom, setZoom] = useState(0.85);

  const nodes = flow?.nodes || [];
  const edges = flow?.edges || [];
  const total = sessions.length;

  const { childMap, nodeMap, rootId, counts } = useMemo(() => {
    const VALID = new Set(["trigger","whatsapp_message","action_whatsapp","whatsapp","delay","condition","goal","exit"]);
    const nodeMap = {};
    nodes.forEach(n => { nodeMap[String(n.id)] = n; });

    const childMap  = {};
    const hasParent = new Set();
    edges.forEach(e => {
      const src = String(e.source), tgt = String(e.target);
      if (!childMap[src]) childMap[src] = [];
      childMap[src].push({ target: tgt, label: resolveLabel(e) });
      hasParent.add(tgt);
    });

    const filtered = nodes.filter(n => VALID.has((n.type||"").toLowerCase()));
    const root =
      filtered.find(n => (n.type||"").toLowerCase() === "trigger") ||
      filtered.find(n => !hasParent.has(String(n.id))) ||
      filtered[0];

    const counts = {};
    sessions.forEach(s => {
      const seen = new Set();
      (s.history||[]).forEach(h => { if (h.node_id) seen.add(String(h.node_id)); });
      if (s.current_node_id) seen.add(String(s.current_node_id));
      seen.forEach(id => { counts[id] = (counts[id] || 0) + 1; });
    });
    if (root) counts[String(root.id)] = total;

    return { childMap, nodeMap, rootId: root ? String(root.id) : null, counts };
  }, [nodes, edges, sessions, total]);

  /* Zoom helpers */
  const zoomOut  = () => setZoom(z => Math.max(0.3, parseFloat((z - 0.1).toFixed(1))));
  const zoomIn   = () => setZoom(z => Math.min(1.5, parseFloat((z + 0.1).toFixed(1))));
  const zoomReset= () => setZoom(0.85);

  /* Fallback */
  if (!rootId || nodes.length === 0) {
    const generic = [
      { id: "g1", label: "Cart Triggered", type: "trigger",          count: total },
      { id: "g2", label: "WhatsApp Sent",  type: "whatsapp_message", count: sessions.filter(s=>(s.history||[]).some(h=>["whatsapp_message","action_whatsapp"].includes(h.node_type))).length },
      { id: "g3", label: "Wait / Delay",   type: "delay",            count: sessions.filter(s=>s.status==="WAITING_DELAY"||(s.history||[]).some(h=>h.node_type==="delay")).length },
      { id: "g4", label: "Goal Converted", type: "goal",             count: sessions.filter(s=>s.status==="COMPLETED_GOAL").length },
    ];
    return (
      <div className="flex flex-col items-center gap-0 py-4">
        {generic.map((s, i) => {
          const cfg = CFG[s.type] || DFLT; const IC = cfg.icon;
          const pct = total > 0 ? Math.round((s.count / total) * 100) : 0;
          return (
            <div key={s.id} className="flex flex-col items-center">
              <button type="button"
                onClick={() => onSelectStep(selectedStepId===s.id?null:s.id)}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border-2 w-[270px] cursor-pointer transition-all shadow-sm
                  ${selectedStepId===s.id?`${cfg.bg} border-transparent text-white`:"bg-white border-gray-200"}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${cfg.bg}`}><IC className="w-4 h-4 text-white"/></div>
                <div className="flex-1 text-left">
                  <div className={`text-[11px] font-semibold ${selectedStepId===s.id?"text-white":"text-gray-700"}`}>{s.label}</div>
                  <div className={`font-black font-mono text-base ${selectedStepId===s.id?"text-white":cfg.count}`}>{s.count}</div>
                </div>
                <span className={`text-[10px] font-mono ${selectedStepId===s.id?"text-white/80":"text-gray-500"}`}>{pct}%</span>
              </button>
              {i < generic.length - 1 && <><VLine /><ArrowDown /></>}
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div>
      {/* ── Toolbar: zoom + clear filter ── */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        {/* Zoom controls */}
        <div className="flex items-center gap-1 bg-gray-50 border border-gray-200 rounded-lg p-1">
          <button type="button" onClick={zoomOut}
            title="Zoom Out"
            className="flex items-center gap-1 px-2 py-1 rounded-md text-gray-600 hover:bg-white hover:shadow-sm text-xs font-semibold transition cursor-pointer">
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button type="button" onClick={zoomReset}
            className="px-2.5 py-1 rounded-md text-gray-700 hover:bg-white text-[11px] font-mono font-bold min-w-[40px] text-center transition cursor-pointer">
            {Math.round(zoom * 100)}%
          </button>
          <button type="button" onClick={zoomIn}
            title="Zoom In"
            className="flex items-center gap-1 px-2 py-1 rounded-md text-gray-600 hover:bg-white hover:shadow-sm text-xs font-semibold transition cursor-pointer">
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <div className="w-px h-4 bg-gray-200 mx-0.5" />
          <button type="button" onClick={zoomReset}
            title="Reset Zoom"
            className="flex items-center gap-1 px-2 py-1 rounded-md text-gray-500 hover:bg-white text-[10px] transition cursor-pointer">
            <RotateCcw className="w-3 h-3" /> Reset
          </button>
        </div>

        {/* Clear filter */}
        {selectedStepId && (
          <button onClick={() => onSelectStep(null)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-gray-100 hover:bg-gray-200 text-gray-600 border border-gray-200 cursor-pointer transition">
            <Filter className="w-3 h-3" /> Clear Filter
          </button>
        )}
      </div>

      {/* ── Tree (scrollable + zoomable) ── */}
      <div className="overflow-auto border border-gray-100 rounded-xl bg-gray-50/40"
        style={{ maxHeight }}>
        <div
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "top center",
            /* keep scroll area correct at zoom < 1 */
            minHeight: `${Math.round(100 / zoom)}%`,
          }}
        >
          <div className="flex justify-center py-4 px-4 min-w-max mx-auto">
            <VerticalTree
              nodeId={rootId}
              childMap={childMap} nodeMap={nodeMap}
              counts={counts} total={total}
              selId={selectedStepId} onSel={onSelectStep}
              visited={new Set()}
            />
          </div>
        </div>
      </div>

      {/* ── Legend ── */}
      <div className="flex flex-wrap items-center gap-3 mt-3 pt-3 border-t border-gray-100">
        {[
          { c: "bg-blue-500",    l: "Trigger" },
          { c: "bg-violet-500",  l: "WhatsApp" },
          { c: "bg-amber-500",   l: "Wait/Delay" },
          { c: "bg-purple-600",  l: "Condition" },
          { c: "bg-emerald-500", l: "Goal" },
        ].map(x => (
          <div key={x.l} className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${x.c}`} />
            <span className="text-[10px] text-gray-500">{x.l}</span>
          </div>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <span className="px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-emerald-50 border border-emerald-300 text-emerald-700">YES</span>
          <span className="px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-red-50 border border-red-300 text-red-700">NO</span>
          <span className="text-[9px] text-gray-400">= decision branch</span>
        </div>
      </div>
    </div>
  );
}
