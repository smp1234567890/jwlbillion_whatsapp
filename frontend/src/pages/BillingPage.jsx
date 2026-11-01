import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  CreditCard,
  RefreshCw,
  TrendingUp,
  AlertCircle,
  Megaphone,
  Sliders,
  DollarSign,
  Calendar,
  CheckCircle2,
  Info,
  Layers,
  ArrowUpRight
} from "lucide-react";

export default function BillingPage({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedMonth, setSelectedMonth] = useState(""); // YYYY-MM

  const fetchBilling = async (monthOverride = null) => {
    setLoading(true);
    setError("");
    try {
      const activeMonth = monthOverride !== null ? monthOverride : selectedMonth;
      const url = activeMonth ? `/api/billing/summary?month=${activeMonth}` : "/api/billing/summary";
      const res = await axios.get(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      setData(res.data);
    } catch (err) {
      console.error("Failed to load billing summary:", err);
      setError(err.response?.data?.detail || err.message || "Failed to load billing summary.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBilling();
  }, [selectedMonth]);

  const waba = data?.waba_info;
  const totals = data?.totals || {
    total_cost_inr: 0,
    total_billable_conversations: 0,
    total_messages_dispatched: 0,
    marketing_cost_inr: 0,
    utility_cost_inr: 0
  };
  const cycle = data?.billing_cycle;
  const rates = data?.rates;
  const campaigns = data?.campaigns || [];
  const automations = data?.automations || [];

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Top Header Card */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-lg bg-emerald-50 text-[#25D366] flex items-center justify-center font-bold">
              <CreditCard className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900 leading-tight">
                Meta Billing & Monthly Cost Analytics
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Official Meta WhatsApp Cloud API conversation charges per campaign, automation & monthly cycle
              </p>
            </div>
          </div>
        </div>

        {/* Controls: Month Selector & Refresh */}
        <div className="flex items-center gap-3 self-end md:self-auto">
          <div className="flex items-center gap-1.5 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 text-xs">
            <Calendar className="w-3.5 h-3.5 text-gray-500" />
            <input
              type="month"
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              className="bg-transparent text-gray-700 font-semibold focus:outline-none cursor-pointer text-xs"
            />
          </div>
          <button
            onClick={() => fetchBilling()}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 rounded-lg transition cursor-pointer disabled:opacity-50"
            title="Refresh billing data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Meta Account Status & Cycle Badge */}
      <div className="bg-gradient-to-r from-emerald-50 via-teal-50 to-blue-50 border border-emerald-200/80 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <div className="text-xs">
            <span className="font-bold text-gray-900">
              {waba?.name || "JWL Billion"} (WABA #{waba?.waba_id})
            </span>
            <span className="text-gray-500 ml-2">
              • Currency: <strong className="text-gray-700">{waba?.currency || "INR"}</strong>
            </span>
            <span className="text-gray-500 ml-2">
              • Status:{" "}
              <span className="text-emerald-700 font-bold uppercase text-[11px] bg-emerald-100/80 px-2 py-0.5 rounded">
                {waba?.account_status || "APPROVED"}
              </span>
            </span>
          </div>
        </div>

        <div className="text-xs font-semibold text-gray-700 bg-white/80 px-3 py-1 rounded-lg border border-emerald-100 shadow-2xs">
          Cycle: <span className="text-emerald-700">{cycle?.month || "Current Month"}</span> ({cycle?.start_date} to {cycle?.end_date})
        </div>
      </div>

      {/* 4 Summary Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Cost */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
              Total Cost This Month
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <span className="font-black text-sm">₹</span>
            </div>
          </div>
          <div>
            <div className="text-2xl font-black text-gray-900">
              ₹{totals.total_cost_inr.toFixed(2)}
            </div>
            <p className="text-[11px] text-gray-400 mt-1">
              Charged for {totals.total_billable_conversations} delivered conversation windows
            </p>
          </div>
        </div>

        {/* Marketing Cost */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
              Marketing Broadcasts
            </span>
            <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <Megaphone className="w-4 h-4" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-black text-purple-900">
              ₹{totals.marketing_cost_inr.toFixed(2)}
            </div>
            <p className="text-[11px] text-gray-400 mt-1">
              Meta rate: ₹{rates?.marketing || "0.86"} / conversation
            </p>
          </div>
        </div>

        {/* Utility / Automation Cost */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
              Utility & Automations
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <Sliders className="w-4 h-4" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-black text-blue-900">
              ₹{totals.utility_cost_inr.toFixed(2)}
            </div>
            <p className="text-[11px] text-gray-400 mt-1">
              Meta rate: ₹{rates?.utility || "0.125"} / conversation
            </p>
          </div>
        </div>

        {/* Dispatches vs Billable */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
              Billable Messages
            </span>
            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-black text-gray-900">
              {totals.total_billable_conversations}{" "}
              <span className="text-xs text-gray-400 font-normal">/ {totals.total_messages_dispatched} sent</span>
            </div>
            <p className="text-[11px] text-gray-400 mt-1">
              Meta does NOT bill for failed or rejected numbers
            </p>
          </div>
        </div>
      </div>

      {/* Table 1: Cost Per Campaign */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Megaphone className="w-4 h-4 text-purple-600" />
            <h3 className="font-bold text-gray-900 text-sm">Campaign Cost Breakdown</h3>
            <span className="text-xs text-gray-400 font-mono">({campaigns.length} campaigns)</span>
          </div>
          <span className="text-[11px] text-gray-400">
            Calculated per delivered recipient in {cycle?.month}
          </span>
        </div>

        {campaigns.length === 0 ? (
          <div className="py-12 text-center text-xs text-gray-400">
            No campaigns found for this billing cycle.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 text-[11px] uppercase font-semibold text-gray-500 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3">Campaign</th>
                  <th className="px-6 py-3">Template / Category</th>
                  <th className="px-6 py-3">Meta Unit Rate</th>
                  <th className="px-6 py-3">Recipients</th>
                  <th className="px-6 py-3">Billable (Delivered)</th>
                  <th className="px-6 py-3">Failed (Not Billed)</th>
                  <th className="px-6 py-3 text-right">Total Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-xs">
                {campaigns.map((camp) => (
                  <tr key={camp.campaign_id} className="hover:bg-gray-50/80 transition">
                    <td className="px-6 py-3.5 font-bold text-gray-900">
                      <div>#{camp.campaign_id} - {camp.title}</div>
                      <div className="text-[10px] text-gray-400 font-mono font-normal">
                        {camp.created_at ? new Date(camp.created_at).toLocaleDateString() : ""}
                      </div>
                    </td>
                    <td className="px-6 py-3.5">
                      <div className="font-mono text-gray-700">{camp.template_name}</div>
                      <span className="inline-block text-[10px] font-bold uppercase px-1.5 py-0.2 rounded mt-0.5 bg-purple-50 text-purple-700 border border-purple-200">
                        {camp.category}
                      </span>
                    </td>
                    <td className="px-6 py-3.5 font-mono text-gray-700">
                      ₹{camp.rate_per_msg.toFixed(2)}
                    </td>
                    <td className="px-6 py-3.5 font-semibold text-gray-900">
                      {camp.total_recipients}
                    </td>
                    <td className="px-6 py-3.5 text-emerald-700 font-bold">
                      {camp.delivered_count}
                    </td>
                    <td className="px-6 py-3.5 text-rose-600 font-semibold">
                      {camp.failed_count}
                    </td>
                    <td className="px-6 py-3.5 text-right font-black text-gray-900 text-sm">
                      ₹{camp.estimated_cost_inr.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Table 2: Cost Per Automation Rule & Flow */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-blue-600" />
            <h3 className="font-bold text-gray-900 text-sm">Automations & Journeys Cost Breakdown</h3>
            <span className="text-xs text-gray-400 font-mono">({automations.length} sources)</span>
          </div>
          <span className="text-[11px] text-gray-400">
            Cart recovery, inactivity, and automated journey flows
          </span>
        </div>

        {automations.length === 0 ? (
          <div className="py-12 text-center text-xs text-gray-400">
            No standalone automation dispatches billed in this cycle.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 text-[11px] uppercase font-semibold text-gray-500 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3">Automation / Origin</th>
                  <th className="px-6 py-3">Template / Category</th>
                  <th className="px-6 py-3">Meta Unit Rate</th>
                  <th className="px-6 py-3">Triggered</th>
                  <th className="px-6 py-3">Delivered</th>
                  <th className="px-6 py-3 text-right">Total Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-xs">
                {automations.map((a, idx) => (
                  <tr key={idx} className="hover:bg-gray-50/80 transition">
                    <td className="px-6 py-3.5 font-bold text-gray-900">
                      {a.automation_name}
                    </td>
                    <td className="px-6 py-3.5">
                      <div className="font-mono text-gray-700">{a.template_name || "Custom"}</div>
                      <span className="inline-block text-[10px] font-bold uppercase px-1.5 py-0.2 rounded mt-0.5 bg-blue-50 text-blue-700 border border-blue-200">
                        {a.category}
                      </span>
                    </td>
                    <td className="px-6 py-3.5 font-mono text-gray-700">
                      ₹{a.rate_per_msg.toFixed(2)}
                    </td>
                    <td className="px-6 py-3.5 font-semibold text-gray-900">
                      {a.total_triggered}
                    </td>
                    <td className="px-6 py-3.5 text-emerald-700 font-bold">
                      {a.delivered_count}
                    </td>
                    <td className="px-6 py-3.5 text-right font-black text-gray-900 text-sm">
                      ₹{a.estimated_cost_inr.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Meta Pricing Reference Note */}
      <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-600 flex items-start gap-3">
        <Info className="w-4 h-4 text-gray-400 mt-0.5 shrink-0" />
        <div className="space-y-1">
          <div className="font-bold text-gray-800">
            About Meta WhatsApp Cloud API Billing (India Rates)
          </div>
          <p className="text-gray-500 leading-relaxed">
            Meta bills per 24-hour conversation window based on the template category:
            <strong> Marketing templates</strong> are billed at ~₹0.86 per conversation, and
            <strong> Utility templates</strong> (order updates, cart recovery, account notices) are billed at ~₹0.125.
            Failed dispatches (invalid or non-WhatsApp numbers) are rejected by Meta and incur <strong>₹0 charge</strong>.
          </p>
        </div>
      </div>
    </div>
  );
}
