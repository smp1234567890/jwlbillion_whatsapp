import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  Flame,
  Star,
  Search,
  Filter,
  RefreshCw,
  PhoneCall,
  CheckCircle2,
  XCircle,
  MessageSquare,
  ArrowUpDown,
  Calendar,
  Clock,
  MapPin,
  TrendingUp,
  UserCheck,
  Tag,
  ChevronLeft,
  ChevronRight
} from "lucide-react";
import { formatToISTDate, formatToISTTime } from "../utils/dateUtils";

export default function LeadInterestReportPage({ token, onOpenChat }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reportData, setReportData] = useState({ summary: {}, records: [] });

  // Filters
  const [interestFilter, setInterestFilter] = useState("ALL"); // ALL, HIGHLY_INTERESTED, INTERESTED
  const [calledFilter, setCalledFilter] = useState("ALL"); // ALL, YES, NO
  const [searchQuery, setSearchQuery] = useState("");
  const [callingPhone, setCallingPhone] = useState(null);

  // Sorting
  const [sortField, setSortField] = useState("interest_score");
  const [sortOrder, setSortOrder] = useState("desc");

  // Pagination (10 per page default, selectable 10, 50, 100)
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const fetchReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get("/api/chat/lead-interest-report", {
        params: {
          interest: interestFilter !== "ALL" ? interestFilter : undefined,
          called: calledFilter !== "ALL" ? calledFilter : undefined,
          search: searchQuery.trim() || undefined
        },
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      setReportData(res.data || { summary: {}, records: [] });
      setCurrentPage(1);
    } catch (err) {
      console.error("Failed to load lead interest report:", err);
      setError(err.response?.data?.detail || "Failed to load report data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [interestFilter, calledFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchReport();
  };

  const handleToggleCalled = async (record) => {
    if (!record.contact_id) return;
    try {
      setCallingPhone(record.phone);
      const res = await axios.post(
        `/api/contacts/${record.contact_id}/toggle-called`,
        {},
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      const nextCalled = Boolean(res.data?.called_status?.called);
      const nextCalledBy = res.data?.called_status?.called_by || "Agent";
      const nextCalledAt = res.data?.called_status?.called_at || new Date().toISOString();

      setReportData((prev) => {
        const nextRecords = prev.records.map((r) => {
          if (r.phone === record.phone) {
            return {
              ...r,
              is_called: nextCalled,
              called_by: nextCalled ? nextCalledBy : null,
              called_at: nextCalled ? nextCalledAt : null
            };
          }
          return r;
        });
        const totalCalled = nextRecords.filter((r) => r.is_called).length;
        return {
          ...prev,
          summary: {
            ...prev.summary,
            total_called: totalCalled,
            total_uncalled: Math.max(0, nextRecords.length - totalCalled)
          },
          records: nextRecords
        };
      });
    } catch (err) {
      console.error("Failed to toggle called status:", err);
    } finally {
      setCallingPhone(null);
    }
  };

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
    setCurrentPage(1);
  };

  const sortedRecords = [...(reportData.records || [])].sort((a, b) => {
    let valA = a[sortField];
    let valB = b[sortField];

    if (sortField === "interest_score" || sortField === "total_orders") {
      valA = Number(valA) || 0;
      valB = Number(valB) || 0;
    } else if (sortField === "last_message_time" || sortField === "contact_created_at") {
      valA = valA ? new Date(valA).getTime() : 0;
      valB = valB ? new Date(valB).getTime() : 0;
    } else {
      valA = (valA || "").toString().toLowerCase();
      valB = (valB || "").toString().toLowerCase();
    }

    if (valA < valB) return sortOrder === "asc" ? -1 : 1;
    if (valA > valB) return sortOrder === "asc" ? 1 : -1;
    return 0;
  });

  // Pagination calculation
  const totalCount = sortedRecords.length;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const validCurrentPage = Math.min(currentPage, totalPages);
  const startIndex = (validCurrentPage - 1) * pageSize;
  const paginatedRecords = sortedRecords.slice(startIndex, startIndex + pageSize);

  const { summary } = reportData;

  return (
    <div className="space-y-5">
      {/* ── Top Header ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center flex-shrink-0">
            <Flame className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-gray-900">Lead Interest & Calling Report</h1>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Live Database Analysis
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              Organized lead interest levels, detected intent topics, and team calling follow-ups.
            </p>
          </div>
        </div>

        <button
          onClick={fetchReport}
          disabled={loading}
          className="flex items-center gap-2 bg-gray-900 hover:bg-black text-white px-4 py-2 rounded-lg text-xs font-semibold shadow-xs transition cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Report</span>
        </button>
      </div>

      {/* ── Metric KPI Cards (Platform Native Theme with Dedicated Distinct Badges) ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-4">
        {/* Total Leads */}
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between hover:border-gray-300 transition">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Total Leads</span>
            <div className="w-7 h-7 rounded-lg bg-gray-100 text-gray-600 flex items-center justify-center">
              <UserCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-black text-gray-900">{summary?.total_leads || 0}</span>
            <span className="block text-[11px] text-gray-400 mt-0.5">All customer threads</span>
          </div>
        </div>

        {/* Highly Interested */}
        <div className="bg-white p-4 rounded-xl border border-rose-200 shadow-xs flex flex-col justify-between hover:border-rose-300 transition">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-rose-700 uppercase tracking-wider">Highly Interested</span>
            <div className="w-7 h-7 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center">
              <Flame className="w-4 h-4 fill-current" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-black text-rose-700">{summary?.total_highly_interested || 0}</span>
            <span className="block text-[11px] text-rose-600/80 font-medium mt-0.5">High buyer intent</span>
          </div>
        </div>

        {/* Interested */}
        <div className="bg-white p-4 rounded-xl border border-amber-200 shadow-xs flex flex-col justify-between hover:border-amber-300 transition">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-amber-700 uppercase tracking-wider">Interested</span>
            <div className="w-7 h-7 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <Star className="w-4 h-4 fill-current" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-black text-amber-700">{summary?.total_interested || 0}</span>
            <span className="block text-[11px] text-amber-600/80 font-medium mt-0.5">Active inquiries</span>
          </div>
        </div>

        {/* Called */}
        <div className="bg-white p-4 rounded-xl border border-emerald-200 shadow-xs flex flex-col justify-between hover:border-emerald-300 transition">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-emerald-700 uppercase tracking-wider">Called</span>
            <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-black text-emerald-700">{summary?.total_called || 0}</span>
            <span className="block text-[11px] text-emerald-600 font-medium mt-0.5">Contacted by team</span>
          </div>
        </div>

        {/* Pending Call */}
        <div className="bg-white p-4 rounded-xl border border-blue-200 shadow-xs flex flex-col justify-between hover:border-blue-300 transition">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-blue-700 uppercase tracking-wider">Pending Call</span>
            <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <Clock className="w-4 h-4 animate-pulse" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-black text-blue-700">{summary?.total_uncalled || 0}</span>
            <span className="block text-[11px] text-blue-600 font-medium mt-0.5">Needs follow-up</span>
          </div>
        </div>
      </div>

      {/* ── Filters & Search Controls ── */}
      <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Search */}
        <form onSubmit={handleSearchSubmit} className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search name, phone, city, or keywords..."
            className="w-full pl-9 pr-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />
        </form>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Interest Tabs with Theme Colors */}
          <div className="flex items-center gap-1 bg-gray-50 p-1 rounded-xl border border-gray-200 text-xs">
            <button
              onClick={() => setInterestFilter("ALL")}
              className={`px-3 py-1 rounded-lg font-bold transition cursor-pointer ${
                interestFilter === "ALL"
                  ? "bg-white text-gray-900 shadow-xs border border-gray-200"
                  : "text-gray-500 hover:text-gray-800"
              }`}
            >
              All Intents ({summary?.total_leads || 0})
            </button>
            <button
              onClick={() => setInterestFilter("HIGHLY_INTERESTED")}
              className={`px-3 py-1 rounded-lg font-bold transition flex items-center gap-1 cursor-pointer ${
                interestFilter === "HIGHLY_INTERESTED"
                  ? "bg-rose-50 text-rose-700 shadow-xs border border-rose-200"
                  : "text-gray-500 hover:text-rose-600"
              }`}
            >
              <Flame className="w-3.5 h-3.5 text-rose-600 fill-current" />
              Highly Interested ({summary?.total_highly_interested || 0})
            </button>
            <button
              onClick={() => setInterestFilter("INTERESTED")}
              className={`px-3 py-1 rounded-lg font-bold transition flex items-center gap-1 cursor-pointer ${
                interestFilter === "INTERESTED"
                  ? "bg-amber-50 text-amber-700 shadow-xs border border-amber-200"
                  : "text-gray-500 hover:text-amber-600"
              }`}
            >
              <Star className="w-3.5 h-3.5 text-amber-600 fill-current" />
              Interested ({summary?.total_interested || 0})
            </button>
          </div>

          {/* Called Filter */}
          <select
            value={calledFilter}
            onChange={(e) => setCalledFilter(e.target.value)}
            className="bg-white border border-gray-200 text-gray-700 text-xs font-semibold rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer shadow-xs"
          >
            <option value="ALL">All Call Status</option>
            <option value="YES">Called (Yes)</option>
            <option value="NO">Pending Call (No)</option>
          </select>

          {/* Rows Per Page (10, 50, 100) */}
          <div className="flex items-center gap-1.5 text-xs text-gray-500 font-semibold pl-1">
            <span>Show:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setCurrentPage(1);
              }}
              className="bg-white border border-gray-200 text-gray-800 text-xs font-bold rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer shadow-xs"
            >
              <option value={10}>10</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        </div>
      </div>

      {/* ── Main Report Table ── */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600">
            <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
              <tr>
                <th
                  onClick={() => handleSort("interest_score")}
                  className="px-5 py-3.5 cursor-pointer hover:bg-gray-100 transition select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Interest Level</span>
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("name")}
                  className="px-5 py-3.5 cursor-pointer hover:bg-gray-100 transition select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Lead Name</span>
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("phone")}
                  className="px-5 py-3.5 cursor-pointer hover:bg-gray-100 transition select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Phone Number</span>
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("city")}
                  className="px-5 py-3.5 cursor-pointer hover:bg-gray-100 transition select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Location</span>
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </div>
                </th>
                <th className="px-5 py-3.5 text-center">Called Status</th>
                <th
                  onClick={() => handleSort("last_message_time")}
                  className="px-5 py-3.5 cursor-pointer hover:bg-gray-100 transition select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Last Interaction</span>
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </div>
                </th>
                <th className="px-5 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-400 text-xs font-medium">
                    <div className="flex items-center justify-center gap-2">
                      <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
                      <span>Analyzing lead conversations across database...</span>
                    </div>
                  </td>
                </tr>
              ) : paginatedRecords.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-400 text-xs font-medium">
                    No leads found matching the selected filters.
                  </td>
                </tr>
              ) : (
                paginatedRecords.map((r) => {
                  const isUpdating = callingPhone === r.phone;

                  return (
                    <tr key={r.phone} className="hover:bg-gray-50/80 transition">
                      {/* Interest Badge (Theme Styled: Rose for High, Amber for Interested) */}
                      <td className="px-5 py-3.5">
                        {r.interest_level === "HIGHLY_INTERESTED" ? (
                          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-rose-50 text-rose-700 font-bold rounded-md border border-rose-200 text-xs shadow-2xs">
                            <Flame className="w-3.5 h-3.5 fill-current text-rose-600" />
                            <span>Highly Interested ({r.interest_score}%)</span>
                          </div>
                        ) : r.interest_level === "INTERESTED" ? (
                          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 text-amber-700 font-semibold rounded-md border border-amber-200 text-xs">
                            <Star className="w-3.5 h-3.5 fill-current text-amber-600" />
                            <span>Interested ({r.interest_score}%)</span>
                          </div>
                        ) : (
                          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-gray-100 text-gray-600 font-medium rounded-md border border-gray-200 text-xs">
                            <span>General ({r.interest_score}%)</span>
                          </div>
                        )}
                        {r.detected_signals && r.detected_signals.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {r.detected_signals.map((sig, idx) => (
                              <span
                                key={idx}
                                className="text-[9px] bg-gray-100 text-gray-600 border border-gray-200 px-1.5 py-0.2 rounded font-medium"
                              >
                                {sig}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>

                      {/* Name */}
                      <td className="px-5 py-3.5 font-bold text-gray-900">
                        {r.name || "Customer"}
                        {r.total_orders > 0 && (
                          <span className="block text-[10px] text-emerald-600 font-semibold mt-0.5">
                            {r.total_orders} past order{r.total_orders > 1 ? "s" : ""}
                          </span>
                        )}
                      </td>

                      {/* Phone */}
                      <td className="px-5 py-3.5 font-mono text-xs font-semibold text-gray-900">
                        {r.phone}
                      </td>

                      {/* Location */}
                      <td className="px-5 py-3.5 text-xs text-gray-600">
                        {r.city ? (
                          <span className="flex items-center gap-1">
                            <MapPin className="w-3 h-3 text-gray-400" />
                            <span>{r.city}</span>
                          </span>
                        ) : (
                          <span className="text-gray-400 italic">—</span>
                        )}
                      </td>

                      {/* Called Yes/No Interactive Button */}
                      <td className="px-5 py-3.5 text-center">
                        <button
                          type="button"
                          disabled={isUpdating || !r.contact_id}
                          onClick={() => handleToggleCalled(r)}
                          title={
                            r.is_called
                              ? `Called by ${r.called_by || "Agent"} on ${r.called_at ? formatToISTDate(r.called_at) : "recently"}. Tap to toggle No.`
                              : "Tap to mark as Called"
                          }
                          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold transition shadow-xs cursor-pointer ${
                            r.is_called
                              ? "bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200"
                              : "bg-gray-100 hover:bg-gray-200 text-gray-600 border border-gray-300"
                          } ${isUpdating ? "opacity-50 cursor-wait" : ""}`}
                        >
                          {r.is_called ? (
                            <>
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                              <span>Yes</span>
                            </>
                          ) : (
                            <>
                              <XCircle className="w-3.5 h-3.5 text-gray-400" />
                              <span>No</span>
                            </>
                          )}
                        </button>
                        {r.is_called && r.called_by && (
                          <span className="block text-[10px] text-emerald-700/80 font-medium mt-0.5 truncate max-w-[110px] mx-auto">
                            by {r.called_by}
                          </span>
                        )}
                      </td>

                      {/* Last Message Preview & Time */}
                      <td className="px-5 py-3.5 text-xs text-gray-500 max-w-[240px]">
                        <p className="truncate text-gray-800">
                          {r.last_sender === "AGENT" && <span className="text-emerald-600 font-semibold mr-1">You:</span>}
                          {r.last_message_text || "No text"}
                        </p>
                        {r.last_message_time && (
                          <span className="text-[10px] text-gray-400 font-mono block mt-0.5">
                            {formatToISTDate(r.last_message_time)} {formatToISTTime(r.last_message_time)}
                          </span>
                        )}
                      </td>

                      {/* Action: Redirect to Chat (WhatsApp Brand Green) */}
                      <td className="px-5 py-3.5 text-right">
                        <button
                          type="button"
                          onClick={() => onOpenChat && onOpenChat(r.phone)}
                          className="inline-flex items-center gap-1.5 bg-[#25D366] hover:bg-[#20ba59] text-black font-bold text-xs px-3.5 py-1.5 rounded-lg shadow-xs transition cursor-pointer"
                          title="Open Live Chat for this Lead"
                        >
                          <MessageSquare className="w-3.5 h-3.5" />
                          <span>Chat</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* ── Pagination Footer ── */}
        <div className="px-5 py-3.5 bg-gray-50 border-t border-gray-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-600">
          <div>
            Showing <strong className="text-gray-900">{totalCount > 0 ? startIndex + 1 : 0}</strong> to{" "}
            <strong className="text-gray-900">{Math.min(startIndex + pageSize, totalCount)}</strong> of{" "}
            <strong className="text-gray-900">{totalCount}</strong> leads
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={validCurrentPage <= 1}
              className="p-1.5 rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition cursor-pointer"
              title="Previous Page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <span className="px-2 font-medium">
              Page <strong className="text-gray-900">{validCurrentPage}</strong> of{" "}
              <strong className="text-gray-900">{totalPages}</strong>
            </span>

            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={validCurrentPage >= totalPages}
              className="p-1.5 rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition cursor-pointer"
              title="Next Page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
