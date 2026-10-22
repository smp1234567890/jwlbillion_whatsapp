import React, { useState } from "react";
import axios from "axios";
import {
  ArrowLeft, Users, GitBranch, Search, RefreshCw,
  ShoppingCart, Send, Clock, CheckCircle2, Award, X, ArrowRight,
  Trash2, AlertTriangle, Check, RotateCcw
} from "lucide-react";
import { formatToIST } from "../utils/dateUtils";
import AnalyticsFlowCanvas from "../components/analytics/AnalyticsFlowCanvas";

/* ── Step pill ── */
const NODE_STYLES = {
  trigger:         { bg: "bg-blue-50 border border-blue-300",    text: "text-blue-700",   icon: ShoppingCart, ic: "text-blue-500" },
  whatsapp_message:{ bg: "bg-violet-50 border border-violet-300",text: "text-violet-700", icon: Send,         ic: "text-violet-500" },
  action_whatsapp: { bg: "bg-violet-50 border border-violet-300",text: "text-violet-700", icon: Send,         ic: "text-violet-500" },
  whatsapp:        { bg: "bg-violet-50 border border-violet-300",text: "text-violet-700", icon: Send,         ic: "text-violet-500" },
  delay:           { bg: "bg-amber-50 border border-amber-300",  text: "text-amber-700",  icon: Clock,        ic: "text-amber-500" },
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
  const s  = getStyle(step);
  const IC = s.icon;
  const isCond  = (step.node_type || "").toLowerCase() === "condition";
  const branch  = (step.branch || "").toUpperCase();
  let label = step.label || step.node_type || "Step";
  if (isCond && (step.condition_type === "MESSAGE_READ" || label.toLowerCase().includes("blue tick") || label.toLowerCase().includes("read"))) {
    label = "Was Message Read?";
  } else if (isCond && (step.condition_type === "ORDER_PLACED" || step.condition_type === "CART_RECOVERED")) {
    label = "Did Customer Purchase?";
  }
  const fullDetails = step.details ? `${label}: ${step.details}` : label;
  if (label.length > 24) label = label.slice(0, 22) + "…";
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

/* ── Last WhatsApp Sent Time & Activity Helpers ── */
export function getLastWhatsAppSentTime(s) {
  if (!s) return 0;
  if (s.state_data?.last_whatsapp_sent_at) {
    const t = new Date(s.state_data.last_whatsapp_sent_at).getTime();
    if (!isNaN(t) && t > 0) return t;
  }
  const hist = Array.isArray(s.history) ? s.history : [];
  for (let i = hist.length - 1; i >= 0; i--) {
    const h = hist[i];
    if (h && typeof h === "object") {
      const type = String(h.node_type || "").toLowerCase();
      const label = String(h.label || "").toLowerCase();
      if (type.includes("whatsapp") || label.includes("whatsapp")) {
        if (h.timestamp) {
          const t = new Date(h.timestamp).getTime();
          if (!isNaN(t) && t > 0) return t;
        }
      }
    }
  }
  return 0;
}

export function getSessionLastActivityTime(s) {
  if (!s) return 0;
  const wa = getLastWhatsAppSentTime(s);
  if (wa > 0) return wa;
  const hist = Array.isArray(s.history) ? s.history : [];
  if (hist.length > 0 && hist[hist.length - 1]?.timestamp) {
    const t = new Date(hist[hist.length - 1].timestamp).getTime();
    if (!isNaN(t) && t > 0) return t;
  }
  if (s.updated_at) {
    const t = new Date(s.updated_at).getTime();
    if (!isNaN(t) && t > 0) return t;
  }
  if (s.created_at) {
    const t = new Date(s.created_at).getTime();
    if (!isNaN(t) && t > 0) return t;
  }
  return s.id || 0;
}

/* ══════════════════════════════════════════
   FULL-PAGE AUTOMATION ANALYTICS
══════════════════════════════════════════ */
export default function AutomationAnalyticsPage({ flow, sessions = [], loading, onBack, token, onRefresh }) {
  const [selectedStepId, setSelectedStepId] = useState(null);
  const [activeTab, setActiveTab]           = useState("funnel");
  const [search, setSearch]                 = useState("");
  const [statusFilter, setStatusFilter]     = useState("ALL");

  // Auto-refresh funnel and session list every 8 seconds when active
  React.useEffect(() => {
    if (!onRefresh) return;
    const interval = setInterval(() => {
      if (!document.hidden) {
        onRefresh();
      }
    }, 8000);
    return () => clearInterval(interval);
  }, [onRefresh]);

  /* Clear Queue Modal State */
  const [showClearModal, setShowClearModal] = useState(false);
  const [clearMode, setClearMode]           = useState("cancel_active"); // "cancel_active" | "delete_all"
  const [clearStats, setClearStats]         = useState(false);
  const [clearCarts, setClearCarts]         = useState(false);
  const [clearing, setClearing]             = useState(false);
  const [clearSuccess, setClearSuccess]     = useState("");
  const [clearError, setClearError]         = useState("");

  const handleExecuteClear = async () => {
    if (!flow?.id) return;
    setClearing(true);
    setClearError("");
    setClearSuccess("");
    try {
      const authToken = token || localStorage.getItem("token");
      const res = await axios.post(
        `/api/workflows/${flow.id}/clear-queue`,
        null,
        {
          params: {
            mode: clearMode,
            clear_stats: clearStats,
            clear_cart_events: clearCarts
          },
          headers: authToken ? { Authorization: `Bearer ${authToken}` } : {}
        }
      );
      setClearSuccess(res.data?.message || "Queue cleared successfully.");
      setTimeout(() => {
        setShowClearModal(false);
        setClearSuccess("");
        if (onRefresh) onRefresh();
      }, 1000);
    } catch (err) {
      setClearError(err.response?.data?.detail || "Failed to clear queue.");
    } finally {
      setClearing(false);
    }
  };

  const totalEnrolled = sessions.length;
  const activeCount   = sessions.filter(s => s.status === "ACTIVE").length;
  const waitingCount  = sessions.filter(s => s.status === "WAITING_DELAY").length;
  const goalCount     = sessions.filter(s => s.status === "COMPLETED_GOAL").length;
  const convPct       = totalEnrolled > 0 ? ((goalCount / totalEnrolled) * 100).toFixed(1) : "0.0";

  /* Filter sessions for contacts tab */
  const term = search.toLowerCase().trim();
  let filtered = (sessions || []).filter(s => {
    if (statusFilter !== "ALL" && s.status !== statusFilter) return false;
    if (!term) return true;
    return (s.customer_phone||"").toLowerCase().includes(term)
        || (s.state_data?.customer_name||"").toLowerCase().includes(term)
        || (s.status||"").toLowerCase().includes(term);
  });
  if (selectedStepId && !selectedStepId.startsWith("stage_")) {
    filtered = filtered.filter(s =>
      String(s.current_node_id) === selectedStepId ||
      (s.history||[]).some(h => String(h.node_id) === selectedStepId)
    );
  }

  // Whichever contact received a WhatsApp message last in the automation comes at the top
  filtered.sort((a, b) => {
    const waA = getLastWhatsAppSentTime(a);
    const waB = getLastWhatsAppSentTime(b);
    if (waA > 0 && waB > 0) {
      if (waA !== waB) return waB - waA;
    }
    if (waA > 0 && waB === 0) return -1;
    if (waB > 0 && waA === 0) return 1;

    const actA = getSessionLastActivityTime(a);
    const actB = getSessionLastActivityTime(b);
    if (actA !== actB) return actB - actA;

    return (b.id || 0) - (a.id || 0);
  });

  return (
    <div className="h-screen max-h-screen bg-gray-50 flex flex-col overflow-hidden">

      {/* ── Top bar ── */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4 flex-shrink-0 sticky top-0 z-20">
        <button type="button" onClick={onBack}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold text-gray-600
            hover:bg-gray-100 border border-gray-200 transition cursor-pointer">
          <ArrowLeft className="w-4 h-4" /> Back
        </button>

        <div className="flex items-center gap-2 flex-1">
          <div className="w-9 h-9 rounded-xl bg-gray-100 flex items-center justify-center">
            <Users className="w-4 h-4 text-gray-500" />
          </div>
          <div>
            <h1 className="font-bold text-base text-gray-900 leading-tight">
              {flow?.name || "Automation"} — Analytics
            </h1>
            <p className="text-[11px] text-gray-400">Journey funnel · contact path inspector · real-time session tracking</p>
          </div>
          <span className="ml-2 px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
            {flow?.trigger_type}
          </span>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-[11px] font-semibold select-none shadow-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Auto-Refresh Active</span>
          </div>

          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold text-gray-700 bg-white hover:bg-gray-100 border border-gray-200 transition cursor-pointer shadow-xs disabled:opacity-50"
              title="Refresh sessions"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-blue-600" : "text-gray-500"}`} />
              <span>Refresh</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => {
              setClearError("");
              setClearSuccess("");
              setShowClearModal(true);
            }}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 transition cursor-pointer shadow-xs"
            title="Empty or cancel automation queue"
          >
            <Trash2 className="w-3.5 h-3.5 text-red-600" />
            <span>Clear Queue</span>
          </button>
        </div>
      </div>

      {/* ── Stat strip ── */}
      <div className="grid grid-cols-4 bg-white border-b border-gray-200 divide-x divide-gray-100 flex-shrink-0">
        <div className="px-6 py-3">
          <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Total Enrolled</p>
          <p className="text-xl font-black text-gray-900 mt-0.5">{totalEnrolled}</p>
        </div>
        <div className="px-6 py-3">
          <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Active in Flow</p>
          <p className="text-xl font-black text-gray-900 mt-0.5">{activeCount + waitingCount}</p>
        </div>
        <div className="px-6 py-3">
          <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Goal Converted</p>
          <p className="text-xl font-black text-emerald-600 mt-0.5">{goalCount}</p>
        </div>
        <div className="px-6 py-3">
          <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Conversion Rate</p>
          <p className="text-xl font-black text-gray-900 mt-0.5">{convPct}%</p>
        </div>
      </div>

      {/* ── Navigation Tabs ── */}
      <div className="bg-white border-b border-gray-200 px-6 flex items-center gap-2 flex-shrink-0">
        {[
          { id: "funnel",   icon: GitBranch, label: "Journey Funnel" },
          { id: "contacts", icon: Users,     label: "Enrolled Contacts" },
        ].map(tab => {
          const IC = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)}
              className={`inline-flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 -mb-px transition-colors cursor-pointer ${
                active ? "border-gray-900 text-gray-900" : "border-transparent text-gray-400 hover:text-gray-700"
              }`}>
              <IC className="w-3.5 h-3.5" />
              {tab.label}
              {tab.id === "contacts" && (
                <span className={`px-1.5 py-0.5 rounded-full text-[9px] font-bold ${
                  active ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-500"}`}>
                  {sessions.length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── Tab Content ── */}
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden relative">

        {/* FUNNEL TAB */}
        {activeTab === "funnel" && (
          <div className="flex-1 h-full w-full relative flex flex-col overflow-hidden">
            {loading ? (
              <div className="py-24 flex justify-center"><RefreshCw className="w-7 h-7 animate-spin text-gray-400" /></div>
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

        {/* CONTACTS TAB */}
        {activeTab === "contacts" && (
          <div className="flex-1 flex flex-col min-h-0 bg-white">
            {/* Filter bar - fixed at top of tab */}
            <div className="bg-white border-b border-gray-200 px-6 py-3 flex flex-wrap items-center gap-3 shrink-0 z-10">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input type="text" placeholder="Search phone, name…"
                  value={search} onChange={e => setSearch(e.target.value)}
                  className="pl-8 pr-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-400 w-52" />
              </div>
              <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-lg">
                {[
                  { v: "ALL",               l: "All" },
                  { v: "ACTIVE",            l: "Active" },
                  { v: "WAITING_DELAY",     l: "Waiting" },
                  { v: "COMPLETED_GOAL",    l: "Goal Met" },
                  { v: "COMPLETED_DROPOUT", l: "Exited" },
                ].map(({ v, l }) => (
                  <button key={v} type="button"
                    onClick={() => setStatusFilter(v)}
                    className={`px-3 py-1 rounded-md text-[11px] font-semibold transition cursor-pointer ${
                      statusFilter === v ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-900"
                    }`}>
                    {l}
                  </button>
                ))}
              </div>
              <span className="text-xs text-gray-400 font-medium">{filtered.length} contacts</span>
              {selectedStepId && (
                <button onClick={() => setSelectedStepId(null)}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 cursor-pointer">
                  Filtered by step — Clear
                </button>
              )}
            </div>

            {loading ? (
              <div className="flex-1 py-24 flex flex-col items-center justify-center gap-2 text-gray-400">
                <RefreshCw className="w-6 h-6 animate-spin" />
                <span className="text-xs">Loading contacts…</span>
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex-1 py-24 text-center space-y-2 flex flex-col items-center justify-center">
                <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mx-auto">
                  <Users className="w-6 h-6 text-gray-400" />
                </div>
                <p className="text-sm font-semibold text-gray-700">No Contacts Found</p>
                <p className="text-xs text-gray-400">No sessions matched your filters.</p>
              </div>
            ) : (
              <div className="flex-1 overflow-auto">
                <table className="w-full text-left text-xs text-gray-600 min-w-[960px] border-collapse">
                  <thead className="bg-gray-50 text-[10px] uppercase font-semibold text-gray-500 border-b border-gray-200 sticky top-0 z-10 shadow-xs">
                    <tr>
                      <th className="px-6 py-3.5 bg-gray-50 whitespace-nowrap">Contact / Phone</th>
                      <th className="px-6 py-3.5 bg-gray-50 whitespace-nowrap">Name</th>
                      <th className="px-6 py-3.5 bg-gray-50 whitespace-nowrap">Cart Value</th>
                      <th className="px-6 py-3.5 bg-gray-50 whitespace-nowrap">Last Message / Enrolled</th>
                      <th className="px-6 py-3.5 bg-gray-50 whitespace-nowrap">Status</th>
                      <th className="px-6 py-3.5 bg-gray-50">Journey Path Traveled</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {filtered.map(s => {
                      const st   = s.state_data || {};
                      const hist = s.history    || [];
                      const waTime = getLastWhatsAppSentTime(s);

                      return (
                        <tr key={s.id} className="hover:bg-gray-50/90 transition group">
                          <td className="px-6 py-4 align-top">
                            <div className="font-bold text-gray-900 font-mono flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full bg-[#25D366] shrink-0" />
                              <span className="tracking-tight">{s.customer_phone}</span>
                            </div>
                            {waTime > 0 && (
                              <div className="mt-1">
                                <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded-full shadow-2xs">
                                  <Send className="w-2.5 h-2.5 text-emerald-600" />
                                  WhatsApp Sent
                                </span>
                              </div>
                            )}
                          </td>
                          <td className="px-6 py-4 align-top">
                            <div className="font-semibold text-gray-800 text-xs">
                              {st.customer_name || "Online Customer"}
                            </div>
                            {st.customer_email && (
                              <div className="text-[10px] text-gray-400 font-mono truncate max-w-[180px]">
                                {st.customer_email}
                              </div>
                            )}
                          </td>
                          <td className="px-6 py-4 align-top font-mono text-emerald-700 font-bold text-xs">
                            {st.cart_value !== undefined ? `₹${st.cart_value}` : "—"}
                          </td>
                          <td className="px-6 py-4 align-top whitespace-nowrap">
                            {waTime > 0 ? (
                              <div className="space-y-1">
                                <div className="inline-flex items-center gap-1.5 font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded text-[10px] shadow-2xs">
                                  <Clock className="w-3 h-3 text-emerald-600" />
                                  <span>{formatToIST(waTime)}</span>
                                </div>
                                <div className="text-[10px] text-gray-400 font-mono">
                                  Enrolled: {formatToIST(s.created_at)}
                                </div>
                              </div>
                            ) : (
                              <div className="space-y-0.5">
                                <div className="font-mono text-[10px] text-gray-700 font-semibold">
                                  {formatToIST(s.created_at)}
                                </div>
                                <span className="text-[10px] text-amber-600 italic">
                                  Awaiting message step
                                </span>
                              </div>
                            )}
                          </td>
                          <td className="px-6 py-4 align-top">
                            <StatusBadge status={s.status} />
                          </td>
                          <td className="px-6 py-4 align-top">
                            {hist.length === 0 ? (
                              <span className="text-gray-400 italic text-[10px]">No steps yet</span>
                            ) : (
                              <div className="flex flex-wrap items-center gap-1.5 max-w-3xl">
                                {hist.map((step, i) => (
                                  <React.Fragment key={i}>
                                    <StepPill step={step} />
                                    {i < hist.length - 1 && <ArrowRight className="w-3 h-3 text-gray-300 shrink-0" />}
                                  </React.Fragment>
                                ))}
                                {s.status === "COMPLETED_GOAL" && (
                                  <>
                                    <ArrowRight className="w-3 h-3 text-gray-300 shrink-0" />
                                    <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-50 border border-teal-300 text-teal-700 shadow-2xs">
                                      <Award className="w-2.5 h-2.5 text-teal-500" />Goal 🎯
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

      {/* ── Clear Automation Queue Modal ── */}
      {showClearModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-60">
          <div className="bg-white rounded-2xl w-full max-w-lg shadow-2xl border border-gray-200 overflow-hidden animate-in fade-in zoom-in duration-150">
            {/* Modal Header */}
            <div className="flex items-start justify-between p-6 border-b border-gray-100 bg-gray-50/50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-red-100 text-red-600 flex items-center justify-center shrink-0">
                  <Trash2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-base text-gray-900 leading-tight">
                    Clear Automation Queue
                  </h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {flow?.name || "Automation"}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowClearModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4">
              {clearSuccess ? (
                <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 flex items-center gap-3 text-sm font-semibold">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                  <span>{clearSuccess}</span>
                </div>
              ) : (
                <>
                  {clearError && (
                    <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-800 flex items-center gap-2 text-xs font-semibold">
                      <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
                      <span>{clearError}</span>
                    </div>
                  )}

                  <p className="text-xs text-gray-600">
                    Select how you want to empty the contacts and scheduled delay queues for this automation:
                  </p>

                  {/* Mode Selector */}
                  <div className="space-y-2.5">
                    <label
                      onClick={() => setClearMode("cancel_active")}
                      className={`flex items-start gap-3 p-3.5 rounded-xl border transition cursor-pointer ${
                        clearMode === "cancel_active"
                          ? "border-red-500 bg-red-50/40 ring-2 ring-red-100"
                          : "border-gray-200 hover:bg-gray-50"
                      }`}
                    >
                      <input
                        type="radio"
                        name="clearMode"
                        checked={clearMode === "cancel_active"}
                        onChange={() => setClearMode("cancel_active")}
                        className="mt-1 text-red-600 focus:ring-red-500 cursor-pointer"
                      />
                      <div className="text-xs">
                        <p className="font-bold text-gray-900">Cancel Active Waiting Sessions</p>
                        <p className="text-gray-500 mt-0.5 leading-relaxed">
                          Immediately cancels all contacts currently waiting in delays. No future WhatsApp messages will be triggered, but session history is kept for review.
                        </p>
                      </div>
                    </label>

                    <label
                      onClick={() => setClearMode("delete_all")}
                      className={`flex items-start gap-3 p-3.5 rounded-xl border transition cursor-pointer ${
                        clearMode === "delete_all"
                          ? "border-red-500 bg-red-50/40 ring-2 ring-red-100"
                          : "border-gray-200 hover:bg-gray-50"
                      }`}
                    >
                      <input
                        type="radio"
                        name="clearMode"
                        checked={clearMode === "delete_all"}
                        onChange={() => setClearMode("delete_all")}
                        className="mt-1 text-red-600 focus:ring-red-500 cursor-pointer"
                      />
                      <div className="text-xs">
                        <p className="font-bold text-gray-900">Delete All Contacts & History</p>
                        <p className="text-gray-500 mt-0.5 leading-relaxed">
                          Permanently purges all enrolled contacts and past traversal logs for this automation from the database.
                        </p>
                      </div>
                    </label>
                  </div>

                  {/* Additional Checkboxes */}
                  <div className="pt-2 border-t border-gray-100 space-y-2">
                    <label className="flex items-center gap-2.5 text-xs text-gray-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={clearStats}
                        onChange={(e) => setClearStats(e.target.checked)}
                        className="rounded border-gray-300 text-red-600 focus:ring-red-500 cursor-pointer"
                      />
                      <span>Reset workflow performance stats (Total Enrolled, Converted, Revenue) to 0</span>
                    </label>

                    <label className="flex items-center gap-2.5 text-xs text-gray-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={clearCarts}
                        onChange={(e) => setClearCarts(e.target.checked)}
                        className="rounded border-gray-300 text-red-600 focus:ring-red-500 cursor-pointer"
                      />
                      <span>Also delete stored cart webhook events (`cart_events`)</span>
                    </label>
                  </div>
                </>
              )}
            </div>

            {/* Modal Footer */}
            {!clearSuccess && (
              <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setShowClearModal(false)}
                  disabled={clearing}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-gray-700 bg-white hover:bg-gray-100 border border-gray-200 transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleExecuteClear}
                  disabled={clearing}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-red-600 hover:bg-red-700 transition cursor-pointer shadow-sm disabled:opacity-50"
                >
                  {clearing ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Clearing...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Confirm & Clear</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
