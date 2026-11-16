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
  Tag
} from "lucide-react";
import { formatToISTDate, formatToISTTime } from "../utils/dateUtils";

export default function LeadInterestReportPage({ token, onOpenChat }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reportData, setReportData] = useState({ summary: {}, records: [] });

  // Filters
  const [interestFilter, setInterestFilter] = useState("ALL"); // ALL, HIGHLY_INTERESTED, INTERESTED, CLIENT_LEADS
  const [calledFilter, setCalledFilter] = useState("ALL"); // ALL, YES, NO
  const [searchQuery, setSearchQuery] = useState("");
  const [callingPhone, setCallingPhone] = useState(null);

  // Sorting
  const [sortField, setSortField] = useState("interest_score");
  const [sortOrder, setSortOrder] = useState("desc");

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
      await axios.post(
        `/api/contacts/${record.contact_id}/toggle-called`,
        {},
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      // Update local state without full reload
      setReportData((prev) => {
        const nextRecords = prev.records.map((r) => {
          if (r.phone === record.phone) {
            const nextCalled = !r.is_called;
            return {
              ...r,
              is_called: nextCalled,
              called_by: nextCalled ? "You" : null,
              called_at: nextCalled ? new Date().toISOString() : null
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

  const { summary } = reportData;

  return (
    <div className="space-y-5">
      {/* ── Top Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-5 rounded-xl border border-gray-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-gray-900">Lead Interest & Calling Report</h1>
            <span className="bg-rose-50 text-rose-700 text-xs font-bold px-2 py-0.5 rounded-full border border-rose-200 flex items-center gap-1">
              <Flame className="w-3.5 h-3.5 text-rose-600 fill-current" />
              Live Analysis
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            All customer chats organized by interest level, inbound lead signals, and team calling status.
          </p>
        </div>
        <button
          onClick={fetchReport}
          disabled={loading}
          className="flex items-center gap-2 bg-gray-900 hover:bg-black text-white px-3.5 py-2 rounded-lg text-xs font-semibold shadow-xs transition cursor-pointer self-start sm:self-auto disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Report</span>
        </button>
      </div>

      {/* ── Metric KPI Cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-xs">
          <div className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">Total Leads</div>
          <div className="text-xl font-black text-gray-900 mt-1">{summary?.total_leads || 0}</div>
          <div className="text-[10px] text-gray-400 mt-0.5">All customer threads</div>
        </div>

        <div className="bg-rose-50/70 p-3.5 rounded-xl border border-rose-200 shadow-xs">
          <div className="text-[11px] font-bold text-rose-800 uppercase tracking-wider flex items-center gap-1">
            <Flame className="w-3 h-3 text-rose-600 fill-current" />
            Highly Interested
          </div>
          <div className="text-xl font-black text-rose-900 mt-1">{summary?.total_highly_interested || 0}</div>
          <div className="text-[10px] text-rose-600 mt-0.5">High buyer intent</div>
        </div>

        <div className="bg-amber-50/70 p-3.5 rounded-xl border border-amber-200 shadow-xs">
          <div className="text-[11px] font-bold text-amber-800 uppercase tracking-wider flex items-center gap-1">
            <Star className="w-3 h-3 text-amber-600 fill-current" />
            Interested
          </div>
          <div className="text-xl font-black text-amber-900 mt-1">{summary?.total_interested || 0}</div>
          <div className="text-[10px] text-amber-600 mt-0.5">Active inquiries</div>
        </div>

        <div className="bg-blue-50/70 p-3.5 rounded-xl border border-blue-200 shadow-xs">
          <div className="text-[11px] font-bold text-blue-800 uppercase tracking-wider">Lead Initiated</div>
          <div className="text-xl font-black text-blue-900 mt-1">{summary?.total_client_initiated || 0}</div>
          <div className="text-[10px] text-blue-600 mt-0.5">Client messaged first</div>
        </div>

        <div className="bg-emerald-50/70 p-3.5 rounded-xl border border-emerald-200 shadow-xs">
          <div className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Called
          </div>
          <div className="text-xl font-black text-emerald-900 mt-1">{summary?.total_called || 0}</div>
          <div className="text-[10px] text-emerald-700 mt-0.5">Contacted by team</div>
        </div>

        <div className="bg-gray-50 p-3.5 rounded-xl border border-gray-200 shadow-xs">
          <div className="text-[11px] font-bold text-gray-600 uppercase tracking-wider flex items-center gap-1">
            <Clock className="w-3 h-3 text-gray-500" />
            Pending Call
          </div>
          <div className="text-xl font-black text-gray-800 mt-1">{summary?.total_uncalled || 0}</div>
          <div className="text-[10px] text-gray-500 mt-0.5">Needs follow-up</div>
        </div>
      </div>

      {/* ── Filters & Search Bar ── */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
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

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Interest Tabs */}
          <div className="flex items-center gap-1 bg-gray-100 p-0.5 rounded-lg text-xs">
            <button
              onClick={() => setInterestFilter("ALL")}
              className={`px-2.5 py-1 rounded-md font-medium transition cursor-pointer ${
                interestFilter === "ALL" ? "bg-white text-gray-900 font-bold shadow-xs" : "text-gray-600 hover:text-gray-900"
              }`}
            >
              All Intents
            </button>
            <button
              onClick={() => setInterestFilter("HIGHLY_INTERESTED")}
              className={`px-2.5 py-1 rounded-md font-medium transition flex items-center gap-1 cursor-pointer ${
                interestFilter === "HIGHLY_INTERESTED" ? "bg-rose-600 text-white font-bold shadow-xs" : "text-rose-700 hover:bg-rose-50"
              }`}
            >
              <Flame className="w-3 h-3 fill-current" />
              Highly Interested
            </button>
            <button
              onClick={() => setInterestFilter("INTERESTED")}
              className={`px-2.5 py-1 rounded-md font-medium transition flex items-center gap-1 cursor-pointer ${
                interestFilter === "INTERESTED" ? "bg-amber-600 text-white font-bold shadow-xs" : "text-amber-700 hover:bg-amber-50"
              }`}
            >
              <Star className="w-3 h-3 fill-current" />
              Interested
            </button>
            <button
              onClick={() => setInterestFilter("CLIENT_LEADS")}
              className={`px-2.5 py-1 rounded-md font-medium transition cursor-pointer ${
                interestFilter === "CLIENT_LEADS" ? "bg-blue-600 text-white font-bold shadow-xs" : "text-blue-700 hover:bg-blue-50"
              }`}
            >
              Lead-Initiated
            </button>
          </div>

          {/* Called Filter */}
          <select
            value={calledFilter}
            onChange={(e) => setCalledFilter(e.target.value)}
            className="bg-gray-50 border border-gray-200 text-gray-700 text-xs font-semibold rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
          >
            <option value="ALL">All Call Status</option>
            <option value="YES">📞 Called (Yes)</option>
            <option value="NO">⏳ Not Called (No)</option>
          </select>
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
                  className="px-5 py-3 cursor-pointer hover:bg-gray-100 transition select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Interest Level</span>
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("name")}
                  className="px-5 py-3 cursor-pointer hover:bg-gray-100 transition select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Lead Name</span>
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("phone")}
                  className="px-5 py-3 cursor-pointer hover:bg-gray-100 transition select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Phone Number</span>
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("city")}
                  className="px-5 py-3 cursor-pointer hover:bg-gray-100 transition select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Location</span>
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </div>
                </th>
                <th className="px-5 py-3">Inbound Origin</th>
                <th className="px-5 py-3 text-center">Called Status</th>
                <th
                  onClick={() => handleSort("last_message_time")}
                  className="px-5 py-3 cursor-pointer hover:bg-gray-100 transition select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Last Interaction</span>
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </div>
                </th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center text-gray-400 text-xs font-medium">
                    <div className="flex items-center justify-center gap-2">
                      <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
                      <span>Analyzing lead conversations across database...</span>
                    </div>
                  </td>
                </tr>
              ) : sortedRecords.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center text-gray-400 text-xs font-medium">
                    No leads found matching the selected filters.
                  </td>
                </tr>
              ) : (
                sortedRecords.map((r) => {
                  const isUpdating = callingPhone === r.phone;

                  return (
                    <tr key={r.phone} className="hover:bg-gray-50/80 transition">
                      {/* Interest Badge */}
                      <td className="px-5 py-3.5">
                        {r.interest_level === "HIGHLY_INTERESTED" ? (
                          <div className="inline-flex items-center gap-1 px-2.5 py-1 bg-rose-50 text-rose-700 font-bold rounded-md border border-rose-200 text-xs shadow-2xs">
                            <Flame className="w-3.5 h-3.5 fill-current text-rose-600" />
                            <span>Highly Interested ({r.interest_score}%)</span>
                          </div>
                        ) : r.interest_level === "INTERESTED" ? (
                          <div className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-50 text-amber-700 font-semibold rounded-md border border-amber-200 text-xs">
                            <Star className="w-3.5 h-3.5 fill-current text-amber-600" />
                            <span>Interested ({r.interest_score}%)</span>
                          </div>
                        ) : (
                          <div className="inline-flex items-center gap-1 px-2.5 py-1 bg-gray-100 text-gray-600 font-medium rounded-md text-xs">
                            <span>General Inquiry ({r.interest_score}%)</span>
                          </div>
                        )}
                        {r.detected_signals && r.detected_signals.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {r.detected_signals.map((sig, idx) => (
                              <span
                                key={idx}
                                className="text-[9px] bg-gray-100 text-gray-600 px-1.5 py-0.2 rounded font-medium"
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

                      {/* Inbound Origin */}
                      <td className="px-5 py-3.5 text-xs">
                        {r.is_client_initiated ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                            Client Started Chat
                          </span>
                        ) : (
                          <span className="text-[11px] text-gray-400">Outbound Template</span>
                        )}
                        <span className="block text-[10px] text-gray-400 mt-0.5">
                          {r.inbound_count} client message{r.inbound_count !== 1 ? "s" : ""}
                        </span>
                      </td>

                      {/* Called Yes/No Toggle */}
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
                              ? "bg-emerald-100 hover:bg-emerald-200 text-emerald-800 border border-emerald-300"
                              : "bg-gray-100 hover:bg-gray-200 text-gray-600 border border-gray-300"
                          } ${isUpdating ? "opacity-50 cursor-wait" : ""}`}
                        >
                          {r.is_called ? (
                            <>
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
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
                          <span className="block text-[9px] text-gray-400 mt-0.5 truncate max-w-[100px] mx-auto">
                            by {r.called_by}
                          </span>
                        )}
                      </td>

                      {/* Last Message Preview & Time */}
                      <td className="px-5 py-3.5 text-xs text-gray-500 max-w-[220px]">
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

                      {/* Action: Redirect to Chat */}
                      <td className="px-5 py-3.5 text-right">
                        <button
                          type="button"
                          onClick={() => onOpenChat && onOpenChat(r.phone)}
                          className="inline-flex items-center gap-1 bg-[#25D366] hover:bg-[#20ba59] text-black font-bold text-xs px-3 py-1.5 rounded-lg shadow-xs transition cursor-pointer"
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
      </div>
    </div>
  );
}
