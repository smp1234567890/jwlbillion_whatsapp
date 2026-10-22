import React, { useState } from "react";
import {
  Users, Search, RefreshCw, ShoppingCart, Send, Clock,
  CheckCircle2, Award, X, ArrowRight, GitBranch, Maximize2, AlertTriangle
} from "lucide-react";
import { formatToIST } from "../../utils/dateUtils";
import AnalyticsFlowCanvas from "../analytics/AnalyticsFlowCanvas";
import { getLastWhatsAppSentTime, getSessionLastActivityTime } from "../../pages/AutomationAnalyticsPage";

/* ── Node-type → pill style (light theme) ── */
const NODE_STYLES = {
  trigger:         { bg: "bg-blue-50 border border-blue-300",    text: "text-blue-700",    icon: ShoppingCart, ic: "text-blue-500" },
  whatsapp_message:{ bg: "bg-violet-50 border border-violet-300",text: "text-violet-700",  icon: Send,         ic: "text-violet-500" },
  action_whatsapp: { bg: "bg-violet-50 border border-violet-300",text: "text-violet-700",  icon: Send,         ic: "text-violet-500" },
  whatsapp:        { bg: "bg-violet-50 border border-violet-300",text: "text-violet-700",  icon: Send,         ic: "text-violet-500" },
  delay:           { bg: "bg-amber-50 border border-amber-300",  text: "text-amber-700",   icon: Clock,        ic: "text-amber-500" },
  condition: {
    YES: { bg: "bg-emerald-50 border border-emerald-300", text: "text-emerald-700", icon: CheckCircle2, ic: "text-emerald-500" },
    NO:  { bg: "bg-red-50 border border-red-300",         text: "text-red-700",     icon: X,            ic: "text-red-500" },
  },
  goal: { bg: "bg-teal-50 border border-teal-300", text: "text-teal-700", icon: Award, ic: "text-teal-500" },
  exit: { bg: "bg-teal-50 border border-teal-300", text: "text-teal-700", icon: Award, ic: "text-teal-500" },
  error: { bg: "bg-rose-50 border border-rose-300", text: "text-rose-700", icon: AlertTriangle, ic: "text-rose-500" },
};

function getStyle(step) {
  const t = (step.node_type || "").toLowerCase();
  const label = (step.label || "").toLowerCase();
  if (t === "error" || label.includes("dropout") || label.includes("error") || label.includes("fail")) {
    return NODE_STYLES.error;
  }
  if (t === "condition") {
    const b = (step.branch || "").toUpperCase();
    return NODE_STYLES.condition[b] || NODE_STYLES.condition.YES;
  }
  return NODE_STYLES[t] || NODE_STYLES.trigger;
}

function StepPill({ step }) {
  const s   = getStyle(step);
  const IC  = s.icon;
  const isCond = (step.node_type || "").toLowerCase() === "condition";
  const branch = (step.branch || "").toUpperCase();
  let label = step.label || step.node_type || "Step";
  const fullDetails = step.details ? `${label}: ${step.details}` : label;
  if (label.length > 20) label = label.slice(0, 18) + "…";

  return (
    <div
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold whitespace-nowrap cursor-help transition-all hover:shadow-sm ${s.bg} ${s.text}`}
      title={fullDetails}
    >
      <IC className={`w-2.5 h-2.5 ${s.ic} shrink-0`} />
      <span>{label}</span>
      {isCond && branch && (
        <span className={`ml-0.5 px-1.5 py-0.5 rounded text-[9px] font-black ${
          branch === "YES" ? "bg-emerald-200 text-emerald-800" : "bg-red-200 text-red-800"
        }`}>{branch}</span>
      )}
    </div>
  );
}

function Arrow() {
  return <ArrowRight className="w-3 h-3 text-gray-400 shrink-0 mx-0.5" />;
}

function StatusBadge({ status }) {
  const map = {
    COMPLETED_GOAL:    { label: "🎯 Goal Converted", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
    WAITING_DELAY:     { label: "⏳ Waiting",         cls: "bg-amber-50 text-amber-700 border-amber-200" },
    COMPLETED_DROPOUT: { label: "🚪 Exited",          cls: "bg-gray-100 text-gray-600 border-gray-200" },
    ACTIVE:            { label: "⚡ Active",           cls: "bg-blue-50 text-blue-700 border-blue-200" },
  };
  const { label, cls } = map[status] || map.ACTIVE;
  return <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${cls}`}>{label}</span>;
}

/* ══════════════════════════════════════════
   MAIN MODAL
══════════════════════════════════════════ */
export default function JourneySessionsModal({ modalState, setModalState, onOpenAnalyticsPage }) {
  const [selectedStepId, setSelectedStepId] = useState(null);
  const [activeTab, setActiveTab]           = useState("funnel"); // "funnel" | "contacts"

  if (!modalState.isOpen) return null;

  const sessions = modalState.sessions || [];
  const flow     = modalState.flow;

  /* KPI counts */
  const totalEnrolled = sessions.length;
  const activeCount   = sessions.filter(s => s.status === "ACTIVE").length;
  const waitingCount  = sessions.filter(s => s.status === "WAITING_DELAY").length;
  const goalCount     = sessions.filter(s => s.status === "COMPLETED_GOAL").length;
  const convPct       = totalEnrolled > 0 ? ((goalCount / totalEnrolled) * 100).toFixed(1) : "0.0";

  /* Filter for contacts tab */
  const term = (modalState.search || "").toLowerCase().trim();
  let filtered = sessions.filter(s => {
    if (modalState.statusFilter !== "ALL" && s.status !== modalState.statusFilter) return false;
    if (!term) return true;
    return (s.customer_phone||"").toLowerCase().includes(term)
        || (s.state_data?.customer_name||"").toLowerCase().includes(term)
        || (s.status||"").toLowerCase().includes(term);
  });

  if (selectedStepId && selectedStepId.startsWith("stage_")) {
    const m = {
      stage_trigger:   () => true,
      stage_whatsapp:  s => (s.history||[]).some(h => ["whatsapp_message","action_whatsapp","whatsapp"].includes(h.node_type)),
      stage_wait:      s => s.status==="WAITING_DELAY"||(s.history||[]).some(h=>h.node_type==="delay"),
      stage_purchased: s => (s.history||[]).some(h=>h.branch==="YES"),
      stage_goal:      s => s.status==="COMPLETED_GOAL",
    };
    const fn = m[selectedStepId]; if (fn) filtered = filtered.filter(fn);
  } else if (selectedStepId) {
    filtered = filtered.filter(s =>
      String(s.current_node_id) === selectedStepId ||
      (s.history||[]).some(h => String(h.node_id) === selectedStepId)
    );
  }

  // Sort: Contacts that were sent a WhatsApp message most recently appear at the top
  filtered = [...filtered].sort((a, b) => {
    const waA = getLastWhatsAppSentTime(a);
    const waB = getLastWhatsAppSentTime(b);
    if (waA > 0 || waB > 0) {
      if (waA !== waB) return waB - waA;
    }
    const actA = getSessionLastActivityTime(a);
    const actB = getSessionLastActivityTime(b);
    if (actA !== actB) return actB - actA;
    return (b.id || 0) - (a.id || 0);
  });

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl w-full max-w-5xl shadow-2xl border border-gray-200 max-h-[92vh] flex flex-col overflow-hidden">

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gray-100 text-gray-400 flex items-center justify-center">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-bold text-base text-gray-900 leading-tight">
                  {flow?.name || "Automation Journey"} — Analytics
                </h3>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
                  {flow?.trigger_type}
                </span>
              </div>
              <p className="text-[11px] text-gray-400 mt-0.5">
                Journey funnel · contact path inspector · real-time tracking
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onOpenAnalyticsPage && (
              <button
                type="button"
                onClick={() => {
                  setModalState(prev => ({ ...prev, isOpen: false }));
                  onOpenAnalyticsPage(flow);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-xs font-semibold transition cursor-pointer"
                title="Open in Dedicated Full Page"
              >
                <Maximize2 className="w-3.5 h-3.5" />
                Full Page
              </button>
            )}
            <button onClick={() => setModalState(prev => ({ ...prev, isOpen: false }))}
              className="text-gray-400 hover:text-gray-700 p-2 rounded-xl hover:bg-gray-100 transition cursor-pointer">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* ── KPI bar (always visible) ── */}
        <div className="grid grid-cols-4 gap-0 flex-shrink-0 border-b border-gray-100">
          {[
            { label: "Total Enrolled",  value: totalEnrolled },
            { label: "Active in Flow",  value: activeCount + waitingCount },
            { label: "Goal Converted",  value: goalCount },
            { label: "Conversion Rate", value: `${convPct}%` },
          ].map((k, i) => (
            <div key={k.label} className={`px-5 py-3 ${i < 3 ? "border-r border-gray-100" : ""}`}>
              <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{k.label}</div>
              <div className="text-xl font-black font-mono text-gray-900 mt-0.5">{k.value}</div>
            </div>
          ))}
        </div>

        {/* ── Tabs ── */}
        <div className="flex border-b border-gray-200 flex-shrink-0 px-6">
          {[
            { id: "funnel",   icon: GitBranch, label: "Journey Funnel" },
            { id: "contacts", icon: Users,     label: "Enrolled Contacts" },
          ].map(tab => {
            const IC = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 -mb-px transition-colors cursor-pointer ${
                  active
                    ? "border-gray-900 text-gray-900"
                    : "border-transparent text-gray-400 hover:text-gray-700"
                }`}
              >
                <IC className="w-3.5 h-3.5" />
                {tab.label}
                {tab.id === "contacts" && (
                  <span className={`px-1.5 py-0.5 rounded-full text-[9px] font-bold ${
                    active ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-500"
                  }`}>
                    {sessions.length}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* ── Tab content ── */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden relative">

          {/* ════ TAB: FUNNEL ════ */}
          {activeTab === "funnel" && (
            <div className="flex-1 h-full w-full relative flex flex-col overflow-hidden min-h-[500px]">
              {modalState.loading ? (
                <div className="py-16 flex justify-center">
                  <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
                </div>
              ) : (
                <AnalyticsFlowCanvas
                  flow={flow}
                  sessions={sessions}
                  selectedStepId={selectedStepId}
                  onSelectStep={setSelectedStepId}
                  onViewContactsAtStep={() => setActiveTab("contacts")}
                />
              )}
            </div>
          )}

          {/* ════ TAB: ENROLLED CONTACTS ════ */}
          {activeTab === "contacts" && (
            <div className="flex-1 overflow-y-auto">
              {/* Filter bar */}
              <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-3 border-b border-gray-100 bg-gray-50/50 sticky top-0 z-10">
                {/* Search */}
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search phone, name…"
                    value={modalState.search}
                    onChange={e => setModalState(prev => ({ ...prev, search: e.target.value }))}
                    className="pl-8 pr-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-400 w-52"
                  />
                </div>

                {/* Status filter */}
                <div className="flex items-center gap-1 bg-white border border-gray-200 p-1 rounded-lg">
                  {[
                    { v: "ALL",               l: "All" },
                    { v: "ACTIVE",            l: "Active" },
                    { v: "WAITING_DELAY",     l: "Waiting" },
                    { v: "COMPLETED_GOAL",    l: "Goal Met" },
                    { v: "COMPLETED_DROPOUT", l: "Exited" },
                  ].map(({ v, l }) => (
                    <button key={v} type="button"
                      onClick={() => setModalState(prev => ({ ...prev, statusFilter: v }))}
                      className={`px-2.5 py-1 rounded-md text-[10px] font-semibold transition cursor-pointer ${
                        modalState.statusFilter === v
                          ? "bg-gray-900 text-white shadow-sm"
                          : "text-gray-500 hover:text-gray-900"
                      }`}>
                      {l}
                    </button>
                  ))}
                </div>

                {selectedStepId && (
                  <span className="text-[11px] text-gray-500">
                    Showing <span className="font-bold text-gray-900">{filtered.length}</span> contacts at selected step
                  </span>
                )}
              </div>

              {/* Table */}
              {modalState.loading ? (
                <div className="py-16 flex flex-col items-center gap-2 text-gray-400">
                  <RefreshCw className="w-6 h-6 animate-spin" />
                  <span className="text-xs">Loading contacts…</span>
                </div>
              ) : filtered.length === 0 ? (
                <div className="py-16 text-center space-y-2">
                  <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mx-auto">
                    <Users className="w-6 h-6 text-gray-400" />
                  </div>
                  <p className="text-sm font-semibold text-gray-700">No Contacts Found</p>
                  <p className="text-xs text-gray-400">
                    {sessions.length === 0
                      ? "No contacts have entered this journey yet."
                      : "No sessions matched your filters."}
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-gray-600 min-w-[780px]">
                    <thead className="bg-gray-50 text-[10px] uppercase font-semibold text-gray-500 border-b border-gray-200">
                      <tr>
                        <th className="px-5 py-3 whitespace-nowrap">Contact / Phone</th>
                        <th className="px-5 py-3 whitespace-nowrap">Name</th>
                        <th className="px-5 py-3 whitespace-nowrap">Last Message / Enrolled</th>
                        <th className="px-5 py-3 whitespace-nowrap">Status</th>
                        <th className="px-5 py-3">Journey Path Traveled</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {filtered.map(s => {
                        const st   = s.state_data || {};
                        const hist = s.history    || [];
                        const waTime = getLastWhatsAppSentTime(s);
                        return (
                          <tr key={s.id} className="hover:bg-gray-50/80 transition">
                            <td className="px-5 py-3.5 align-top">
                              <div className="font-bold text-gray-900 font-mono flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-[#25D366] shrink-0" />
                                {s.customer_phone}
                              </div>
                              {st.cart_value !== undefined && (
                                <div className="text-[10px] text-emerald-600 font-mono mt-0.5">₹{st.cart_value}</div>
                              )}
                            </td>
                            <td className="px-5 py-3.5 align-top text-gray-700">{st.customer_name || "Online Customer"}</td>
                            <td className="px-5 py-3.5 align-top font-mono text-[10px] text-gray-500 whitespace-nowrap">
                              {waTime > 0 ? (
                                <div className="flex flex-col gap-0.5">
                                  <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded w-fit">
                                    <Send className="w-2.5 h-2.5" />
                                    WA: {formatToIST(new Date(waTime).toISOString())}
                                  </span>
                                  <span className="text-[9px] text-gray-400">
                                    Enrolled: {formatToIST(s.created_at)}
                                  </span>
                                </div>
                              ) : (
                                <div>{formatToIST(s.created_at)}</div>
                              )}
                            </td>
                            <td className="px-5 py-3.5 align-top"><StatusBadge status={s.status} /></td>
                            <td className="px-5 py-3.5 align-top">
                              {hist.length === 0 ? (
                                <span className="text-gray-400 text-[10px] italic">No steps yet</span>
                              ) : (
                                <div className="flex flex-wrap items-center gap-1">
                                  {hist.map((step, i) => (
                                    <React.Fragment key={i}>
                                      <StepPill step={step} />
                                      {i < hist.length - 1 && <Arrow />}
                                    </React.Fragment>
                                  ))}
                                  {s.status === "COMPLETED_GOAL" && (
                                    <>
                                      <Arrow />
                                      <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-50 border border-teal-300 text-teal-700">
                                        <Award className="w-2.5 h-2.5 text-teal-500" />
                                        Goal 🎯
                                      </div>
                                    </>
                                  )}
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
