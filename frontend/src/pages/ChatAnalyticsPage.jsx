import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import {
  Users,
  MessageSquare,
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  Calendar,
  RefreshCw,
  Search,
  Filter,
  ArrowUpDown,
  ExternalLink,
  ChevronRight
} from "lucide-react";

export default function ChatAnalyticsPage({ token, onOpenChat }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [analyticsData, setAnalyticsData] = useState(null);

  // Time filters
  const [presetRange, setPresetRange] = useState("today"); // today, yesterday, 7d, 30d, custom
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // Table filters & sorting
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all"); // all, replied, unreplied, interactive
  const [sortBy, setSortBy] = useState("time_desc"); // time_desc, time_asc, response_time

  // Calculate default dates for presets
  const applyPreset = (preset) => {
    setPresetRange(preset);
    const now = new Date();
    let s = new Date();
    let e = new Date();

    if (preset === "today") {
      s.setHours(0, 0, 0, 0);
      e.setHours(23, 59, 59, 999);
    } else if (preset === "yesterday") {
      s.setDate(s.getDate() - 1);
      s.setHours(0, 0, 0, 0);
      e.setDate(e.getDate() - 1);
      e.setHours(23, 59, 59, 999);
    } else if (preset === "7d") {
      s.setDate(s.getDate() - 7);
      s.setHours(0, 0, 0, 0);
    } else if (preset === "30d") {
      s.setDate(s.getDate() - 30);
      s.setHours(0, 0, 0, 0);
    } else if (preset === "custom") {
      return; // Keep current inputs
    }

    const formatForInput = (d) => {
      const pad = (n) => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };

    setStartDate(formatForInput(s));
    setEndDate(formatForInput(e));
  };

  // Initial load
  useEffect(() => {
    applyPreset("today");
  }, []);

  const fetchAnalytics = async () => {
    const activeToken = token || localStorage.getItem("token");
    if (!activeToken) return;
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (startDate) params.start_date = new Date(startDate).toISOString();
      if (endDate) params.end_date = new Date(endDate).toISOString();

      const res = await axios.get("/api/chat/analytics", {
        headers: { Authorization: `Bearer ${activeToken}` },
        params
      });
      setAnalyticsData(res.data);
    } catch (err) {
      console.error("Failed to load chat analytics:", err);
      const detailMsg = err?.response?.data?.detail;
      setError(
        typeof detailMsg === "string"
          ? detailMsg
          : "Failed to load chat analytics. Please retry."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (startDate && endDate) {
      fetchAnalytics();
    }
  }, [startDate, endDate]);

  const summary = analyticsData?.summary || {
    total_inbound_people: 0,
    interactive_count: 0,
    interactive_rate: 0,
    replied_count: 0,
    unreplied_count: 0,
    response_rate: 0,
    avg_response_time_minutes: 0
  };

  const contactsList = useMemo(() => {
    if (!analyticsData?.contacts) return [];
    let list = [...analyticsData.contacts];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(
        (c) =>
          (c.customer_name && c.customer_name.toLowerCase().includes(q)) ||
          (c.customer_phone && c.customer_phone.toLowerCase().includes(q)) ||
          (c.first_message_preview && c.first_message_preview.toLowerCase().includes(q)) ||
          (c.customer_city && c.customer_city.toLowerCase().includes(q))
      );
    }

    if (statusFilter === "replied") {
      list = list.filter((c) => c.got_reply);
    } else if (statusFilter === "unreplied") {
      list = list.filter((c) => !c.got_reply);
    } else if (statusFilter === "interactive") {
      list = list.filter((c) => c.got_interactive);
    }

    if (sortBy === "time_desc") {
      list.sort((a, b) => new Date(b.last_inbound_time || 0) - new Date(a.last_inbound_time || 0));
    } else if (sortBy === "time_asc") {
      list.sort((a, b) => new Date(a.last_inbound_time || 0) - new Date(b.last_inbound_time || 0));
    } else if (sortBy === "response_time") {
      list.sort((a, b) => (b.response_time_minutes || 0) - (a.response_time_minutes || 0));
    }

    return list;
  }, [analyticsData, searchQuery, statusFilter, sortBy]);

  const formatDateTime = (isoStr) => {
    if (!isoStr) return "-";
    const d = new Date(isoStr);
    return d.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true
    });
  };

  return (
    <div className="space-y-6">
      {/* Header & Date-Time Filter Bar */}
      <div className="bg-white p-4 sm:p-5 rounded-xl border border-gray-200 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Live Chat Inbox Analytics</h1>
            <p className="text-sm text-gray-500 mt-1">
              Real-time audit of incoming customer messages, interactive menus sent, and team replies.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchAnalytics}
              disabled={loading}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-gray-700 text-sm font-medium transition shadow-sm disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-amber-500" : ""}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="mt-4 pt-4 border-t border-gray-100 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 bg-gray-100 p-1 rounded-lg">
            {[
              { id: "today", label: "Today" },
              { id: "yesterday", label: "Yesterday" },
              { id: "7d", label: "Last 7 Days" },
              { id: "30d", label: "Last 30 Days" },
              { id: "custom", label: "Custom Range" }
            ].map((p) => (
              <button
                key={p.id}
                onClick={() => applyPreset(p.id)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${
                  presetRange === p.id
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-600 hover:text-gray-900"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-gray-600 bg-gray-50 px-2.5 py-1.5 rounded-lg border border-gray-200">
              <Calendar className="w-3.5 h-3.5 text-gray-400" />
              <span>From:</span>
              <input
                type="datetime-local"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value);
                  setPresetRange("custom");
                }}
                className="bg-transparent text-gray-800 text-xs focus:outline-none cursor-pointer"
              />
            </div>

            <div className="flex items-center gap-1.5 text-xs font-medium text-gray-600 bg-gray-50 px-2.5 py-1.5 rounded-lg border border-gray-200">
              <Calendar className="w-3.5 h-3.5 text-gray-400" />
              <span>To:</span>
              <input
                type="datetime-local"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value);
                  setPresetRange("custom");
                }}
                className="bg-transparent text-gray-800 text-xs focus:outline-none cursor-pointer"
              />
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Total Inbound People */}
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Inbound Customers
          </div>
          <div className="mt-3">
            <div className="text-3xl font-bold text-gray-900">{summary.total_inbound_people}</div>
            <p className="text-xs text-gray-500 mt-1">Unique people who sent a message</p>
          </div>
        </div>

        {/* Chat Links Clicked */}
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wider text-blue-600">
            Chat Links Clicked
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <div className="text-3xl font-bold text-blue-600">{summary.chat_total_clicks || 0}</div>
            <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
              {summary.chat_unique_clickers || 0} unique
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">Product links tapped inside chat</p>
        </div>

        {/* Got Interactive Template */}
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Interactive Menu Sent
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <div className="text-3xl font-bold text-gray-900">{summary.interactive_count}</div>
            <span className="text-xs font-semibold text-purple-600 bg-purple-50 px-2 py-0.5 rounded">
              {summary.interactive_rate}%
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">Received interactive menu template</p>
        </div>

        {/* Replied Count */}
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Replies Delivered
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <div className="text-3xl font-bold text-emerald-600">{summary.replied_count}</div>
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
              {summary.response_rate}% rate
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">Manual replies and quick replies sent</p>
        </div>

        {/* Unreplied / Pending */}
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Awaiting Reply
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <div className={`text-3xl font-bold ${summary.unreplied_count > 0 ? "text-amber-600" : "text-gray-900"}`}>
              {summary.unreplied_count}
            </div>
            <span className="text-xs text-gray-500">
              Avg speed: {summary.avg_response_time_minutes}m
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">Inbound messages needing a response</p>
        </div>
      </div>

      {/* Customer Activity Log Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {/* Table Toolbar */}
        <div className="p-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-gray-50/50">
          <div className="flex items-center gap-2 flex-1 max-w-md">
            <div className="relative w-full">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search by customer name, phone, or message..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-500"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 text-xs text-gray-600">
              <Filter className="w-3.5 h-3.5 text-gray-400" />
              <span>Filter:</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-white border border-gray-200 rounded-lg px-2 py-1 text-xs font-medium text-gray-700 focus:outline-none"
              >
                <option value="all">All Inquiries ({analyticsData?.contacts?.length || 0})</option>
                <option value="replied">Replied Only</option>
                <option value="unreplied">Unreplied Only</option>
                <option value="interactive">Got Interactive Menu</option>
              </select>
            </div>

            <div className="flex items-center gap-1 text-xs text-gray-600">
              <ArrowUpDown className="w-3.5 h-3.5 text-gray-400" />
              <span>Sort:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="bg-white border border-gray-200 rounded-lg px-2 py-1 text-xs font-medium text-gray-700 focus:outline-none"
              >
                <option value="time_desc">Newest Inbound</option>
                <option value="time_asc">Oldest Inbound</option>
                <option value="response_time">Slowest Response</option>
              </select>
            </div>
          </div>
        </div>

        {/* Table Body */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-gray-50/80 border-b border-gray-200 text-gray-600 uppercase font-semibold">
                <th className="py-3 px-4">Customer</th>
                <th className="py-3 px-4">Inquiry Time</th>
                <th className="py-3 px-4">Customer Message</th>
                <th className="py-3 px-4">Interactive Menu</th>
                <th className="py-3 px-4">Our Reply</th>
                <th className="py-3 px-4">Link Clicks</th>
                <th className="py-3 px-4">Auto Response</th>
                <th className="py-3 px-4">Manual Response</th>
                <th className="py-3 px-4">Customer Took</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-gray-400">
                    <div className="inline-flex items-center gap-2">
                      <RefreshCw className="w-4 h-4 animate-spin text-amber-500" />
                      Loading chat analytics data...
                    </div>
                  </td>
                </tr>
              ) : contactsList.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-gray-500">
                    No inbound customer messages found in this selected time range.
                  </td>
                </tr>
              ) : (
                contactsList.map((item, idx) => (
                  <tr key={idx} className="hover:bg-gray-50/80 transition">
                    {/* Customer */}
                    <td className="py-3 px-4">
                      <div className="font-semibold text-gray-900">{item.customer_name}</div>
                      <div className="text-gray-500 font-mono text-[11px]">{item.customer_phone}</div>
                      {item.customer_city && (
                        <span className="text-[10px] text-gray-400">{item.customer_city}</span>
                      )}
                    </td>

                    {/* Inquiry Time */}
                    <td className="py-3 px-4 whitespace-nowrap text-gray-600">
                      <div>{formatDateTime(item.first_inbound_time)}</div>
                      {item.inbound_messages_count > 1 && (
                        <span className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-medium">
                          {item.inbound_messages_count} messages
                        </span>
                      )}
                    </td>

                    {/* Customer Message */}
                    <td className="py-3 px-4 max-w-xs truncate text-gray-800" title={item.first_message_preview}>
                      {item.first_message_preview || "-"}
                    </td>

                    {/* Interactive Template Status */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      {item.got_interactive ? (
                        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 font-medium">
                          <CheckCircle2 className="w-3.5 h-3.5 text-purple-600" />
                          <span>Sent</span>
                        </div>
                      ) : (
                        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 font-medium">
                          <XCircle className="w-3.5 h-3.5 text-gray-400" />
                          <span>Not Sent</span>
                        </div>
                      )}
                    </td>

                    {/* Reply Status */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      {item.got_reply ? (
                        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          <span>Replied ({item.reply_count})</span>
                        </div>
                      ) : (
                        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 font-medium">
                          <Clock className="w-3.5 h-3.5 text-amber-600" />
                          <span>Pending</span>
                        </div>
                      )}
                    </td>

                    {/* Link Clicks */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      {item.link_clicks_count > 0 ? (
                        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 font-semibold border border-blue-200">
                          <ExternalLink className="w-3 h-3 text-blue-600" />
                          <span>{item.link_clicks_count} click{item.link_clicks_count > 1 ? "s" : ""}</span>
                        </div>
                      ) : (
                        <span className="text-gray-400 font-normal">-</span>
                      )}
                    </td>

                    {/* Auto Response Time */}
                    <td className="py-3 px-4 whitespace-nowrap text-gray-600">
                      {item.auto_response_time_minutes !== null && item.auto_response_time_minutes !== undefined ? (
                        <span className="inline-flex items-center gap-1 font-medium text-purple-700 bg-purple-50 px-2 py-0.5 rounded">
                          {item.auto_response_time_minutes < 0.1
                            ? "< 3s (Bot)"
                            : `${Math.round(item.auto_response_time_minutes * 60)}s`}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>

                    {/* Manual Response Time */}
                    <td className="py-3 px-4 whitespace-nowrap text-gray-600">
                      {item.manual_response_time_minutes !== null && item.manual_response_time_minutes !== undefined ? (
                        <span className="inline-flex items-center gap-1 font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                          {item.manual_response_time_minutes < 1
                            ? `${Math.round(item.manual_response_time_minutes * 60)}s`
                            : `${item.manual_response_time_minutes} min`}
                        </span>
                      ) : (
                        <span className="text-gray-400 italic">No manual reply</span>
                      )}
                    </td>

                    {/* Customer Response Time (Turnaround) */}
                    <td className="py-3 px-4 whitespace-nowrap text-gray-600">
                      {item.customer_response_time_minutes !== null && item.customer_response_time_minutes !== undefined ? (
                        <span className="inline-flex items-center gap-1 font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
                          {item.customer_response_time_minutes < 1
                            ? `${Math.round(item.customer_response_time_minutes * 60)}s`
                            : item.customer_response_time_minutes < 60
                            ? `${item.customer_response_time_minutes} min`
                            : `${Math.round(item.customer_response_time_minutes / 60 * 10) / 10} hrs`}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>

                    {/* Action */}
                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      {onOpenChat && (
                        <button
                          onClick={() => onOpenChat(item.customer_phone)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-md border border-gray-200 text-gray-700 hover:bg-gray-100 transition shadow-xs"
                          title="Open live conversation"
                        >
                          <span>Open Chat</span>
                          <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer info */}
        <div className="p-3 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between text-xs text-gray-500">
          <span>Showing {contactsList.length} of {analyticsData?.contacts?.length || 0} total inquiries</span>
          <span>Timezone: Local time</span>
        </div>
      </div>
    </div>
  );
}
