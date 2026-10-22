import React from "react";
import {
  GitBranch, Play, PlayCircle, Plus, Zap, Sliders, Sparkles, ToggleLeft, ToggleRight, Clock, Trash2, Tag, ShieldCheck, AlertTriangle, RefreshCw, Activity, ShoppingCart, Radio, Send, ChevronRight, Eye, Users, BarChart3
} from "lucide-react";

import FlowchartCanvas from "../components/FlowchartCanvas";
import { formatToIST, formatToISTDate, getTodayISTDateString } from "../utils/dateUtils";

export default function AutomationsPage({
  editingWorkflow,
  setEditingWorkflow,
  handleSaveWorkflow,
  templates = [],
  discountCodes = [],
  workflowFlows = [],
  handleCleanSlate,
  handleOpenNewJourneyModal,
  cartEvents = [],
  messageLogs = [],
  optOuts = [],
  campaigns = [],
  contacts = [],
  handleToggleWorkflow,
  handleDeleteWorkflow,
  handleOpenJourneySessions,
  handleOpenAnalyticsPage,
}) {
  return (
            editingWorkflow ? (
              <FlowchartCanvas
                workflow={editingWorkflow}
                onSave={handleSaveWorkflow}
                onClose={() => setEditingWorkflow(null)}
                availableTemplates={templates}
                availableCoupons={discountCodes}
              />
            ) : (
            <div className="space-y-6">
              {/* ── Automations Header Bar ── */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white border border-gray-200 rounded-2xl p-4 shadow-xs">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-50 text-[#25D366] flex items-center justify-center">
                    <GitBranch className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-gray-900">Visual Journey Automations</h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Multi-step flowchart workflows with delays, smart condition branching, and revenue goals
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2.5">
                  {workflowFlows.length > 0 && (
                    <button
                      onClick={handleCleanSlate}
                      className="flex items-center gap-1.5 bg-gray-100 hover:bg-red-50 text-gray-600 hover:text-red-600 border border-gray-200 px-3.5 py-2 rounded-xl text-xs font-bold transition shadow-xs"
                      title="Clear sample data for a fresh clean slate"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Purge Sample Data</span>
                    </button>
                  )}

                  <button
                    onClick={handleOpenNewJourneyModal}
                    className="flex items-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-4 py-2 rounded-xl text-xs font-bold shadow-xs transition"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Create Journey Flow</span>
                  </button>
                </div>
              </div>
                  {/* ── 📊 CLEAN EXECUTIVE AUTOMATION OVERVIEW (ADMIN PORTAL THEME) ── */}
                  <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
                    <div className="p-5 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
                      
                      {/* LEFT: Clean Circular Progress & Key Metrics */}
                      <div className="lg:col-span-5 flex items-center gap-6 border-b lg:border-b-0 lg:border-r border-gray-100 pb-5 lg:pb-0 lg:pr-6">
                        {/* Minimal Circular Dial */}
                        <div className="relative w-32 h-32 flex items-center justify-center shrink-0">
                          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 120 120">
                            {/* Background track */}
                            <circle cx="60" cy="60" r="48" stroke="#F3F4F6" strokeWidth="8" fill="transparent" />
                            {/* Active Automations Arc */}
                            <circle
                              cx="60"
                              cy="60"
                              r="48"
                              stroke="#25D366"
                              strokeWidth="8"
                              strokeDasharray="301"
                              strokeDashoffset={
                                workflowFlows.length > 0
                                  ? 301 - (301 * (workflowFlows.filter((r) => r.is_active).length / Math.max(1, workflowFlows.length)))
                                  : 301
                              }
                              strokeLinecap="round"
                              fill="transparent"
                              className="transition-all duration-700"
                            />
                          </svg>
                          <div className="absolute flex flex-col items-center justify-center text-center">
                            <span className="text-xl font-black text-gray-900 leading-none">
                              {workflowFlows.filter((r) => r.is_active).length}
                            </span>
                            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mt-0.5">
                              of {workflowFlows.length} Active
                            </span>
                          </div>
                        </div>

                        {/* Clean Executive Readouts */}
                        <div className="space-y-2.5 flex-1">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-gray-500 flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full bg-[#25D366]"></span>
                              Active Journeys
                            </span>
                            <span className="text-xs font-bold text-gray-900">
                              {workflowFlows.filter((r) => r.is_active).length} / {workflowFlows.length}
                            </span>
                          </div>

                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-gray-500 flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full bg-[#F5A623]"></span>
                              Recovered (30d)
                            </span>
                            <span className="text-xs font-bold text-[#D35400] font-mono">
                              ₹{cartEvents.filter((c) => c.status === "RECOVERED").reduce((sum, c) => sum + (c.cart_value || 0), 0).toLocaleString()}
                            </span>
                          </div>

                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-gray-500 flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                              Sent Today
                            </span>
                            <span className="text-xs font-bold text-gray-900 font-mono">
                              {messageLogs.filter((m) => {
                                const todayIST = getTodayISTDateString();
                                const msgDate = m.created_at ? formatToISTDate(m.created_at) : "";
                                // Check if log was created today in IST
                                let s = String(m.created_at || "").trim();
                                if (!s.endsWith("Z") && !s.includes("+") && !s.slice(10).includes("-")) s += "Z";
                                const logISTStr = new Intl.DateTimeFormat("en-CA", {
                                  timeZone: "Asia/Kolkata",
                                  year: "numeric",
                                  month: "2-digit",
                                  day: "2-digit"
                                }).format(new Date(s));
                                return logISTStr === todayIST;
                              }).length} msgs
                            </span>
                          </div>

                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-gray-500 flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                              Opt-Out Rate
                            </span>
                            <span className="text-xs font-bold text-emerald-600 font-mono">
                              {optOuts.length === 0 ? "0% (Healthy)" : `${optOuts.length} opted out`}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* RIGHT: Live Automation Stream & Guardrail Status */}
                      <div className="lg:col-span-7 flex flex-col justify-between space-y-3.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Activity className="w-4 h-4 text-[#25D366]" />
                            <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                              Automation Activity & System Health
                            </h4>
                          </div>
                          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <span className="w-1.5 h-1.5 rounded-full bg-[#25D366] animate-pulse"></span>
                            Scheduler Online
                          </div>
                        </div>

                        {/* Activity Feed Cards */}
                        <div className="space-y-2">
                          {cartEvents.length > 0 ? (
                            <div className="bg-gray-50 border border-gray-100 p-2.5 rounded-lg flex items-center justify-between text-xs">
                              <div className="flex items-center gap-2.5">
                                <ShoppingCart className="w-3.5 h-3.5 text-[#F5A623]" />
                                <span className="text-gray-700">
                                  Latest cart: <strong className="font-mono text-gray-900">₹{cartEvents[0].cart_value || 0}</strong> • Status: <span className="font-semibold text-gray-800">{cartEvents[0].status}</span>
                                </span>
                              </div>
                              <span className="text-[10px] text-gray-400 font-mono">
                                {cartEvents[0].customer_phone ? cartEvents[0].customer_phone.replace(/(\d{5})(\d{5})/, "$1*****") : "Customer"}
                              </span>
                            </div>
                          ) : (
                            <div className="bg-gray-50 border border-gray-100 p-2.5 rounded-lg flex items-center justify-between text-xs text-gray-500">
                              <div className="flex items-center gap-2">
                                <Radio className="w-3.5 h-3.5 text-emerald-600" />
                                <span>Listening for store cart events & inactive customer triggers</span>
                              </div>
                              <span className="text-[11px] font-mono text-gray-400">Idle (Standby)</span>
                            </div>
                          )}

                          {messageLogs.length > 0 ? (
                            <div className="bg-gray-50 border border-gray-100 p-2.5 rounded-lg flex items-center justify-between text-xs">
                              <div className="flex items-center gap-2.5">
                                <Send className="w-3.5 h-3.5 text-[#25D366]" />
                                <span className="text-gray-700">
                                  Dispatched <code className="text-gray-900 font-bold bg-white px-1.5 py-0.5 rounded border border-gray-200 text-[11px]">{messageLogs[0].template_name}</code> to {messageLogs[0].recipient_phone}
                                </span>
                              </div>
                              <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                Sent
                              </span>
                            </div>
                          ) : (
                            <div className="bg-gray-50 border border-gray-100 p-2.5 rounded-lg flex items-center justify-between text-xs text-gray-500">
                              <div className="flex items-center gap-2">
                                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                                <span>Daily safety guardrail active: 0 of 500 WhatsApp limit used</span>
                              </div>
                              <span className="text-[11px] text-emerald-600 font-semibold">100% Capacity</span>
                            </div>
                          )}
                        </div>

                        {/* Operational Guardrails Bar */}
                        <div className="flex items-center justify-between pt-1 text-xs text-gray-500">
                          <div className="flex items-center gap-3 text-[11px]">
                            <span>Opt-out enforcement: <strong className="text-gray-800">Strict DND</strong></span>
                            <span className="text-gray-300">•</span>
                            <span>Deduplication window: <strong className="text-gray-800">3-7 Days</strong></span>
                          </div>
                        </div>
                      </div>

                    </div>
                  </div>

                  {/* Subheader & Actions */}
                  <div className="flex items-center justify-between flex-wrap gap-4 pt-2">
                    <div>
                      <h3 className="text-base font-bold text-gray-900">E-Commerce Customer Journeys</h3>
                      <p className="text-xs text-gray-500 mt-0.5">Multi-step visual flowchart automations with delays, condition branching, and goals</p>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <button
                        onClick={handleOpenNewJourneyModal}
                        className="bg-[#25D366] hover:bg-[#1EBE5D] text-white px-4 py-2 rounded-xl font-bold text-xs shadow-xs transition inline-flex items-center gap-2"
                      >
                        <Plus className="w-4 h-4" />
                        <span>Create Journey Flow</span>
                      </button>
                    </div>
                  </div>

                  {/* Grid of Multi-Step Flow Cards */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    {workflowFlows.map((flow) => {
                      const nodes = flow.nodes || [];
                      const stepCount = nodes.length;

                      return (
                        <div
                          key={flow.id}
                          className="bg-white rounded-2xl border border-gray-200 shadow-xs hover:shadow-md transition p-6 flex flex-col justify-between space-y-5 relative overflow-hidden"
                        >
                          <div className="space-y-3">
                            <div className="flex items-center justify-between gap-3">
                              <div className="flex items-center gap-2">
                                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
                                  {flow.trigger_type}
                                </span>
                                <span className="text-xs text-gray-400 font-mono">
                                  {stepCount} Steps
                                </span>
                              </div>

                              <button
                                onClick={() => handleToggleWorkflow(flow)}
                                className={`flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold transition flex-shrink-0 ${
                                  flow.is_active
                                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                    : "bg-gray-100 text-gray-400 border border-gray-200"
                                }`}
                              >
                                {flow.is_active ? (
                                  <ToggleRight className="w-4 h-4 text-emerald-600" />
                                ) : (
                                  <ToggleLeft className="w-4 h-4 text-gray-400" />
                                )}
                                {flow.is_active ? "Live & Active" : "Paused"}
                              </button>
                            </div>

                            <div>
                              <h3 className="text-base font-bold text-gray-900">
                                {flow.name}
                              </h3>
                              <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                                {flow.description || "Multi-stage automated customer journey"}
                              </p>
                            </div>

                            {/* Visual Mini-Pipeline Preview */}
                            <div className="bg-gray-50 border border-gray-100 rounded-xl p-3 space-y-1.5">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                                Journey Pathway Sequence:
                              </span>
                              <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                                {nodes.slice(0, 5).map((n, i) => (
                                  <React.Fragment key={n.id || i}>
                                    <span
                                      className={`px-2 py-0.5 rounded-md font-semibold border text-[10px] ${
                                        n.type === "trigger"
                                          ? "bg-blue-50 text-blue-700 border-blue-200"
                                          : n.type === "delay"
                                          ? "bg-amber-50 text-amber-700 border-amber-200"
                                          : n.type === "whatsapp_message"
                                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                          : n.type === "condition"
                                          ? "bg-purple-50 text-purple-700 border-purple-200"
                                          : "bg-gray-100 text-gray-700 border-gray-200"
                                      }`}
                                    >
                                      {n.label}
                                    </span>
                                    {i < Math.min(nodes.length - 1, 4) && (
                                      <ChevronRight className="w-3 h-3 text-gray-400 shrink-0" />
                                    )}
                                  </React.Fragment>
                                ))}
                                {nodes.length > 5 && (
                                  <span className="text-[10px] text-gray-400 font-semibold">
                                    +{nodes.length - 5} more
                                  </span>
                                )}
                              </div>
                            </div>

                            {/* Metrics Summary Strip */}
                            <div className="grid grid-cols-4 gap-2 pt-1 border-t border-gray-100 text-xs">
                              <button
                                type="button"
                                onClick={() => handleOpenJourneySessions(flow)}
                                className="text-left p-1.5 -m-1.5 rounded-lg hover:bg-emerald-50/70 transition group cursor-pointer border border-transparent hover:border-emerald-200"
                                title="Click to view all contacts enrolled in this journey"
                              >
                                <span className="text-[10px] text-gray-400 block font-medium group-hover:text-emerald-700 flex items-center gap-0.5">
                                  Enrolled <Eye className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 transition" />
                                </span>
                                <span className="font-bold text-gray-900 group-hover:text-[#25D366] font-mono underline decoration-dotted underline-offset-2">
                                  {flow.stats?.entered || 0}
                                </span>
                              </button>
                              <div>
                                <span className="text-[10px] text-gray-400 block font-medium">Completed</span>
                                <span className="font-bold text-gray-900 font-mono">{flow.stats?.completed || 0}</span>
                              </div>
                              <div>
                                <span className="text-[10px] text-gray-400 block font-medium">Goals Met</span>
                                <span className="font-bold text-emerald-700 font-mono">{flow.stats?.goals_converted || 0}</span>
                              </div>
                              <div>
                                <span className="text-[10px] text-gray-400 block font-medium">Recovered</span>
                                <span className="font-bold text-[#D35400] font-mono">
                                  ₹{(flow.stats?.revenue_recovered || 0).toLocaleString()}
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Card Footer Actions */}
                          <div className="pt-3 border-t border-gray-100 flex items-center justify-between gap-3">
                            <button
                              onClick={() => handleDeleteWorkflow(flow.id)}
                              className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                              title="Delete Flow"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>

                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => handleOpenJourneySessions(flow)}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-xl text-xs font-bold transition shadow-xs cursor-pointer"
                                title="Inspect contacts that traversed this automation"
                              >
                                <Users className="w-3.5 h-3.5" />
                                Contacts ({flow.stats?.entered || 0})
                              </button>
                              {handleOpenAnalyticsPage && (
                                <button
                                  onClick={() => handleOpenAnalyticsPage(flow)}
                                  className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-50 hover:bg-violet-100 text-violet-700 border border-violet-200 rounded-xl text-xs font-bold transition shadow-xs cursor-pointer"
                                  title="Open full-screen analytics for this automation"
                                >
                                  <BarChart3 className="w-3.5 h-3.5" />
                                  Full Analytics
                                </button>
                              )}
                              <button
                                onClick={() => setEditingWorkflow(flow)}
                                className="flex items-center gap-1.5 px-4 py-1.5 bg-[#25D366] hover:bg-[#1EBE5D] text-white rounded-xl text-xs font-bold transition shadow-xs cursor-pointer"
                              >
                                <Sliders className="w-3.5 h-3.5" />
                                Open Flowchart Builder
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {workflowFlows.length === 0 && (
                    <div className="bg-white rounded-2xl border border-dashed border-gray-300 p-12 text-center">
                      <div className="w-14 h-14 rounded-2xl bg-emerald-50 text-[#25D366] flex items-center justify-center mx-auto mb-4">
                        <GitBranch className="w-7 h-7" />
                      </div>
                      <h4 className="text-base font-bold text-gray-900">
                        No Multi-Step Journey Flows Yet
                      </h4>
                      <p className="text-xs text-gray-500 max-w-md mx-auto mt-1 mb-5 leading-relaxed">
                        Create your first visual flowchart automation to guide customers from cart abandonment or festival campaigns through multi-stage follow-ups.
                      </p>
                      <button
                        onClick={handleOpenNewJourneyModal}
                        className="bg-[#25D366] hover:bg-[#1EBE5D] text-white px-5 py-2.5 rounded-xl font-bold text-xs shadow-xs inline-flex items-center gap-2 transition"
                      >
                        <Plus className="w-4 h-4" />
                        <span>Create First Journey Flow</span>
                      </button>
                    </div>
                  )}
                </div>
              )
  );
}
