import React from "react";
import {
  BarChart3,
  RefreshCw,
  TrendingUp,
  Send,
  Eye,
  MousePointerClick,
  MessageSquare,
  IndianRupee,
  Activity,
  ArrowRight
} from "lucide-react";

export default function AnalyticsPage({
  analyticsTimeRange,
  setAnalyticsTimeRange,
  fetchAnalytics,
  handleSyncMetaTemplates,
  loading,
  analyticsLoading,
  analyticsData,
  analyticsTemplateStats = [],
  handleTabChange
}) {
  return (
            <div className="space-y-6">
              {/* Top Header & Range Filters */}
              <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-50 text-[#10B981] flex items-center justify-center flex-shrink-0">
                    <BarChart3 className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900 text-base">WhatsApp Delivery & Engagement Analytics</h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Real-time delivery rates, open/read receipts, button clicks, customer replies, and recovered revenue
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 bg-gray-50 p-1.5 rounded-xl border border-gray-200 self-stretch md:self-auto justify-between md:justify-end">
                  {[
                    { id: "today", label: "Today" },
                    { id: "7d", label: "Last 7 Days" },
                    { id: "30d", label: "Last 30 Days" },
                    { id: "all", label: "All Time" }
                  ].map((range) => (
                    <button
                      key={range.id}
                      onClick={() => {
                        setAnalyticsTimeRange(range.id);
                        fetchAnalytics(range.id);
                      }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                        analyticsTimeRange === range.id
                          ? "bg-white text-gray-900 shadow-xs border border-gray-200"
                          : "text-gray-500 hover:text-gray-900"
                      }`}
                    >
                      {range.label}
                    </button>
                  ))}
                  <button
                    onClick={async () => {
                      await handleSyncMetaTemplates();
                      fetchAnalytics(analyticsTimeRange);
                    }}
                    disabled={loading || analyticsLoading}
                    title="Sync templates and read metrics from Meta WhatsApp Manager"
                    className="flex items-center gap-1.5 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-3 py-1.5 rounded-lg text-xs font-bold shadow-xs transition"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
                    Sync from Meta
                  </button>
                  <button
                    onClick={() => fetchAnalytics(analyticsTimeRange)}
                    disabled={analyticsLoading}
                    title="Refresh analytics"
                    className="p-1.5 text-gray-500 hover:text-gray-800 hover:bg-white rounded-lg border border-transparent hover:border-gray-200 transition"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${analyticsLoading ? "animate-spin text-[#F5A623]" : ""}`} />
                  </button>
                </div>
              </div>

              {/* Key Metric Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
                {/* 1. Delivery Rate */}
                <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
                  <div>
                    <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Delivery Rate</span>
                  </div>
                  <div className="mt-3">
                    <span className="text-2xl font-black text-gray-900">
                      {analyticsData?.rates?.delivery_rate ?? 0}%
                    </span>
                    <p className="text-[11px] text-gray-500 mt-1">
                      <span className="font-semibold text-gray-700">{analyticsData?.funnel?.total_delivered ?? 0}</span> / {analyticsData?.funnel?.total_sent ?? 0} sent
                    </p>
                  </div>
                </div>

                {/* 2. Read / Open Rate */}
                <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
                  <div>
                    <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Read / Open Rate</span>
                  </div>
                  <div className="mt-3">
                    <span className="text-2xl font-black text-gray-900">
                      {analyticsData?.rates?.read_rate ?? 0}%
                    </span>
                    <p className="text-[11px] text-gray-500 mt-1">
                      <span className="font-semibold text-gray-700">{analyticsData?.funnel?.total_read ?? 0}</span> read receipts
                    </p>
                  </div>
                </div>

                {/* 4. Customer Reply Rate */}
                <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
                  <div>
                    <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Reply Rate</span>
                  </div>
                  <div className="mt-3">
                    <span className="text-2xl font-black text-gray-900">
                      {analyticsData?.rates?.reply_rate ?? 0}%
                    </span>
                    <p className="text-[11px] text-gray-500 mt-1">
                      <span className="font-semibold text-gray-700">{analyticsData?.funnel?.total_replied ?? 0}</span> customer replies
                    </p>
                  </div>
                </div>

                {/* 5. Revenue Recovered */}
                <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
                  <div>
                    <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Recovered Rev</span>
                  </div>
                  <div className="mt-3">
                    <span className="text-2xl font-black text-gray-900">
                      ₹{Number(analyticsData?.funnel?.revenue_recovered || 0).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </span>
                    <p className="text-[11px] text-gray-500 mt-1">
                      <span className="font-semibold text-gray-700">{analyticsData?.funnel?.recovered_carts ?? 0}</span> carts converted
                    </p>
                  </div>
                </div>

                {/* 6. Meta Quality Rating */}
                <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
                  <div>
                    <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Meta Quality</span>
                  </div>
                  <div className="mt-3">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#10B981] animate-pulse"></span>
                      <span className="text-xl font-black text-gray-900">
                        {analyticsData?.meta_health?.quality_rating || "HIGH"}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-500 mt-1">
                      Opt-out: <span className="font-semibold text-gray-700">{analyticsData?.rates?.opt_out_rate ?? 0}%</span>
                    </p>
                  </div>
                </div>
              </div>

              {/* Conversion Funnel Bar */}
              <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-gray-900 text-base">WhatsApp Broadcast & Recovery Conversion Funnel</h3>
                    <p className="text-xs text-gray-500 mt-0.5">Full customer journey from WhatsApp dispatch to checkout purchase</p>
                  </div>
                  <div className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-md border border-emerald-200">
                    Live Pipeline
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3">
                  {/* Stage 1: Sent */}
                  <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">1. Dispatched</span>
                      </div>
                      <p className="text-2xl font-black text-gray-900 mt-2">{analyticsData?.funnel?.total_sent ?? 0}</p>
                    </div>
                    <div className="mt-3 pt-2 border-t border-gray-200/60 text-[11px] text-gray-500">
                      100% of pipeline
                    </div>
                  </div>

                  {/* Stage 2: Delivered */}
                  <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">2. Delivered</span>
                      </div>
                      <p className="text-2xl font-black text-gray-900 mt-2">{analyticsData?.funnel?.total_delivered ?? 0}</p>
                    </div>
                    <div className="mt-3 pt-2 border-t border-gray-200/60 text-[11px] font-semibold text-gray-700">
                      {analyticsData?.rates?.delivery_rate ?? 0}% delivery rate
                    </div>
                  </div>

                  {/* Stage 3: Read */}
                  <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">3. Opened / Read</span>
                      </div>
                      <p className="text-2xl font-black text-gray-900 mt-2">{analyticsData?.funnel?.total_read ?? 0}</p>
                    </div>
                    <div className="mt-3 pt-2 border-t border-gray-200/60 text-[11px] font-semibold text-gray-700">
                      {analyticsData?.rates?.read_rate ?? 0}% read rate
                    </div>
                  </div>

                  {/* Stage 4: Engaged / Replies */}
                  <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">4. Engaged / Replies</span>
                      </div>
                      <p className="text-2xl font-black text-gray-900 mt-2">
                        {analyticsData?.funnel?.total_replied ?? 0}
                      </p>
                    </div>
                    <div className="mt-3 pt-2 border-t border-gray-200/60 text-[11px] font-semibold text-gray-700">
                      {analyticsData?.funnel?.total_replied ?? 0} customer replies
                    </div>
                  </div>

                  {/* Stage 5: Converted */}
                  <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">5. Converted</span>
                      </div>
                      <p className="text-2xl font-black text-gray-900 mt-2">
                        ₹{Number(analyticsData?.funnel?.revenue_recovered || 0).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </p>
                    </div>
                    <div className="mt-3 pt-2 border-t border-gray-200/60 text-[11px] font-semibold text-gray-700">
                      {analyticsData?.funnel?.recovered_carts ?? 0} carts converted
                    </div>
                  </div>
                </div>
              </div>

              {/* Two Column Grid: Template Performance + Daily Trends & Meta Health */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left 2 Cols: Template Performance Leaderboard */}
                <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden flex flex-col">
                  <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-gray-900 text-base">Template Performance Leaderboard</h3>
                      <p className="text-xs text-gray-500 mt-0.5">Delivery and open rates broken down by WhatsApp template</p>
                    </div>
                    <span className="text-xs font-semibold text-gray-500 bg-gray-50 px-2.5 py-1 rounded-md border border-gray-200">
                      {(analyticsData?.template_performance || []).length} Templates
                    </span>
                  </div>

                  <div className="overflow-x-auto flex-1">
                    <table className="w-full text-left text-sm text-gray-600">
                      <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
                        <tr>
                          <th className="px-6 py-3">Template Name</th>
                          <th className="px-6 py-3 text-right">Sent</th>
                          <th className="px-6 py-3 text-right">Delivered</th>
                          <th className="px-6 py-3 text-right">Read</th>
                          <th className="px-6 py-3 text-center">Read Rate</th>
                          <th className="px-6 py-3 text-center">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {(!analyticsData?.template_performance || analyticsData.template_performance.length === 0) ? (
                          <tr>
                            <td colSpan="6" className="px-6 py-8 text-center text-gray-400 text-xs">
                              No template messages logged during this time period yet.
                            </td>
                          </tr>
                        ) : (
                          analyticsData.template_performance.map((tmpl) => {
                            const isHigh = tmpl.read_rate >= 60;
                            const isMed = tmpl.read_rate >= 30 && tmpl.read_rate < 60;
                            return (
                              <tr key={tmpl.template_name} className="hover:bg-gray-50/80 transition">
                                <td className="px-6 py-4 font-mono font-medium text-xs text-gray-900">
                                  {tmpl.template_name}
                                </td>
                                <td className="px-6 py-4 text-right font-semibold text-gray-800">
                                  {tmpl.sent}
                                </td>
                                <td className="px-6 py-4 text-right text-gray-600 font-semibold">
                                  {tmpl.delivered}
                                </td>
                                <td className="px-6 py-4 text-right font-bold text-gray-900">
                                  {tmpl.read}
                                </td>
                                <td className="px-6 py-4 text-center">
                                  <span
                                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                                      isHigh
                                        ? "bg-green-50 text-[#10B981] border border-green-200"
                                        : isMed
                                        ? "bg-amber-50 text-[#F5A623] border border-amber-200"
                                        : "bg-gray-100 text-gray-600 border border-gray-200"
                                    }`}
                                  >
                                    {tmpl.read_rate}%
                                  </span>
                                </td>
                                <td className="px-6 py-4 text-center">
                                  {tmpl.failed > 0 ? (
                                    <span className="text-[11px] font-semibold text-red-500 bg-red-50 px-2 py-0.5 rounded border border-red-200">
                                      {tmpl.failed} failed
                                    </span>
                                  ) : (
                                    <span className="text-[11px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                      Optimal
                                    </span>
                                  )}
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Right 1 Col: Daily Trends & Meta Health */}
                <div className="space-y-6">
                  {/* Daily Trends Chart/Bars */}
                  <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-bold text-gray-900 text-sm">Daily Message Trends</h3>
                      <span className="text-[11px] text-gray-500">Sent vs Read</span>
                    </div>

                    <div className="space-y-3">
                      {(!analyticsData?.daily_trends || analyticsData.daily_trends.length === 0) ? (
                        <p className="text-xs text-gray-400 text-center py-4">No activity logged in this period</p>
                      ) : (
                        analyticsData.daily_trends.map((day) => {
                          const maxVol = Math.max(1, ...analyticsData.daily_trends.map((d) => d.sent));
                          const sentWidth = Math.min(100, Math.round((day.sent / maxVol) * 100));
                          return (
                            <div key={day.date} className="text-xs">
                              <div className="flex items-center justify-between text-[11px] text-gray-600 mb-1">
                                <span className="font-semibold text-gray-700">{day.date}</span>
                                <span className="text-gray-400">
                                  {day.sent} sent · <span className="text-emerald-600 font-semibold">{day.read} read</span>
                                  {day.replied > 0 && <span className="text-purple-600 font-semibold"> · {day.replied} replied</span>}
                                </span>
                              </div>
                              <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden flex">
                                <div
                                  className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                                  style={{ width: `${Math.max(day.sent > 0 ? 8 : 0, sentWidth)}%` }}
                                ></div>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>

                  {/* Meta Health & Daily Limits Card */}
                  <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-bold text-gray-900 text-sm">Meta Business Health</h3>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-[#10B981] border border-emerald-200">
                        {analyticsData?.meta_health?.phone_status || "ONLINE"}
                      </span>
                    </div>

                    <div className="space-y-3 text-xs">
                      <div>
                        <div className="flex items-center justify-between text-[11px] mb-1">
                          <span className="text-gray-500 font-medium">Daily Outbound Capacity</span>
                          <span className="font-bold text-gray-900">
                            {analyticsData?.meta_health?.used_today ?? 0} / {analyticsData?.meta_health?.daily_limit ?? 200} sent
                          </span>
                        </div>
                        <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-[#25D366] rounded-full"
                            style={{
                              width: `${Math.min(
                                100,
                                Math.round(
                                  ((analyticsData?.meta_health?.used_today ?? 0) /
                                    (analyticsData?.meta_health?.daily_limit ?? 200)) *
                                    100
                                )
                              )}%`
                            }}
                          ></div>
                        </div>
                      </div>

                      <div className="p-3 bg-gray-50 rounded-lg border border-gray-200 space-y-1.5 text-[11px]">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Quality Rating:</span>
                          <span className="font-bold text-emerald-600">
                            {analyticsData?.meta_health?.quality_rating || "HIGH"} (Green)
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Messaging Tier:</span>
                          <span className="font-semibold text-gray-800">
                            {analyticsData?.meta_health?.tier_name || "Tier 1 (1,000 / 24h)"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Opt-Out Safeguard:</span>
                          <span className="font-semibold text-gray-800">Automatic STOP Registry</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

  );
}
