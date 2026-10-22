import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  X,
  RefreshCw,
  Search,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Send,
  Eye,
  CheckCheck,
  User,
  Phone,
  Calendar,
  Layers,
  FileText
} from "lucide-react";
import { formatToIST } from "../../utils/dateUtils";

export default function CampaignReportModal({
  isOpen,
  onClose,
  campaign,
  token
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  useEffect(() => {
    if (isOpen && campaign) {
      fetchReport();
    } else {
      setData(null);
      setErrorMsg("");
      setSearch("");
      setStatusFilter("ALL");
    }
  }, [isOpen, campaign]);

  const fetchReport = async () => {
    if (!campaign?.id) return;
    setLoading(true);
    setErrorMsg("");
    try {
      const res = await axios.get(`/api/campaigns/${campaign.id}/logs`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      setData(res.data);
    } catch (err) {
      console.error("Failed to load campaign logs:", err);
      setErrorMsg(err.response?.data?.detail || err.message || "Could not fetch campaign logs");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen || !campaign) return null;

  const recipients = data?.recipients || [];
  const summary = data?.summary || {
    total_recipients: campaign.total_recipients || 0,
    successful_sends: campaign.successful_sends || 0,
    sent: 0,
    delivered: 0,
    read: 0,
    failed: campaign.failed_sends || 0
  };

  const filteredRecipients = recipients.filter((r) => {
    const matchesSearch =
      r.phone.toLowerCase().includes(search.toLowerCase()) ||
      (r.name && r.name.toLowerCase().includes(search.toLowerCase())) ||
      (r.meta_message_id && r.meta_message_id.toLowerCase().includes(search.toLowerCase()));

    if (!matchesSearch) return false;

    if (statusFilter === "ALL") return true;
    const st = (r.status || "").toUpperCase();
    if (statusFilter === "FAILED") return st === "FAILED" || st.startsWith("BLOCKED");
    if (statusFilter === "SENT") return st === "SENT" || st === "SENT_SIMULATED";
    return st === statusFilter;
  });

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn">
      <div className="bg-white rounded-2xl max-w-4xl w-full shadow-2xl border border-gray-200 flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/70">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-gray-500 bg-gray-200/80 px-2 py-0.5 rounded">
                #{campaign.id}
              </span>
              <h3 className="font-bold text-lg text-gray-900">{campaign.title}</h3>
              <span
                className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                  campaign.status === "COMPLETED"
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : campaign.status === "FAILED"
                    ? "bg-red-50 text-red-700 border border-red-200"
                    : "bg-blue-50 text-blue-700 border border-blue-200"
                }`}
              >
                {campaign.status}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1 flex items-center gap-2">
              <span>Template: <strong className="text-gray-700 font-mono">{campaign.template_name}</strong></span>
              <span>•</span>
              <span>Language: <strong className="text-gray-700 uppercase">{campaign.language}</strong></span>
              <span>•</span>
              <span>Target: <strong className="text-gray-700">{campaign.target_filter}</strong></span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchReport}
              disabled={loading}
              className="p-2 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition"
              title="Refresh Report"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-emerald-600" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Analytics Summary Badges */}
        <div className="px-6 py-4 bg-white border-b border-gray-100 grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="bg-gray-50 rounded-xl p-3 border border-gray-200">
            <div className="text-[11px] font-semibold uppercase text-gray-500">Recipients</div>
            <div className="text-xl font-bold text-gray-900 mt-0.5">{summary.total_recipients}</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 border border-gray-200">
            <div className="text-[11px] font-semibold uppercase text-gray-500">Dispatched (Sent)</div>
            <div className="text-xl font-bold text-gray-900 mt-0.5">{summary.sent}</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 border border-gray-200">
            <div className="text-[11px] font-semibold uppercase text-gray-500">Delivered</div>
            <div className="text-xl font-bold text-gray-900 mt-0.5">{summary.delivered}</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 border border-gray-200">
            <div className="text-[11px] font-semibold uppercase text-gray-500">Read / Opened</div>
            <div className="text-xl font-bold text-gray-900 mt-0.5">{summary.read}</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 border border-gray-200">
            <div className="text-[11px] font-semibold uppercase text-gray-500">Failed / Blocked</div>
            <div className="text-xl font-bold text-gray-900 mt-0.5">{summary.failed}</div>
          </div>
        </div>

        {/* Filter / Search Bar */}
        <div className="px-6 py-3 bg-gray-50/50 border-b border-gray-100 flex flex-col sm:flex-row gap-3 items-center justify-between">
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
            <input
              type="text"
              placeholder="Search by phone or name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
          </div>
          <div className="flex items-center gap-1.5 self-end sm:self-auto">
            {["ALL", "SENT", "DELIVERED", "READ", "FAILED"].map((tab) => (
              <button
                key={tab}
                onClick={() => setStatusFilter(tab)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                  statusFilter === tab
                    ? "bg-gray-800 text-white"
                    : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-100"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        {/* Recipient List Table */}
        <div className="flex-1 overflow-y-auto">
          {errorMsg && (
            <div className="p-4 m-4 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 text-red-600" />
              <span>{errorMsg}</span>
            </div>
          )}
          {loading ? (
            <div className="py-16 text-center text-gray-400 flex flex-col items-center justify-center gap-2">
              <RefreshCw className="w-6 h-6 animate-spin text-emerald-600" />
              <span className="text-xs">Loading contact delivery records...</span>
            </div>
          ) : filteredRecipients.length === 0 ? (
            <div className="py-16 text-center text-gray-400">
              <FileText className="w-10 h-10 mx-auto text-gray-300 mb-2" />
              <p className="text-sm font-medium text-gray-600">No contact logs found</p>
              <p className="text-xs text-gray-400 mt-1">
                {search ? "No records match your search filter." : "Delivery logs will populate as messages are dispatched."}
              </p>
            </div>
          ) : (
            <table className="w-full text-left text-xs text-gray-600">
              <thead className="bg-gray-50 text-[11px] uppercase font-semibold text-gray-500 border-b border-gray-200 sticky top-0">
                <tr>
                  <th className="px-6 py-3">Contact</th>
                  <th className="px-6 py-3">Phone Number</th>
                  <th className="px-6 py-3">Dispatch Time (IST)</th>
                  <th className="px-6 py-3">Delivery Status</th>
                  <th className="px-6 py-3">Meta ID / Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredRecipients.map((rec) => {
                  const st = (rec.status || "UNKNOWN").toUpperCase();
                  return (
                    <tr key={rec.id} className="hover:bg-gray-50/80 transition">
                      <td className="px-6 py-3.5">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center font-bold text-gray-700 text-[11px]">
                            {rec.name ? rec.name.charAt(0).toUpperCase() : "C"}
                          </div>
                          <div>
                            <div className="font-semibold text-gray-900">{rec.name || "Customer"}</div>
                            {rec.city && rec.city !== "-" && (
                              <div className="text-[10px] text-gray-400">{rec.city}</div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-3.5 font-mono text-gray-800 font-medium">
                        {rec.phone}
                      </td>
                      <td className="px-6 py-3.5 font-mono text-gray-500 text-[11px]">
                        {formatToIST(rec.created_at)}
                      </td>
                      <td className="px-6 py-3.5">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full font-semibold text-[11px] ${
                            st === "DELIVERED"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : st === "READ"
                              ? "bg-purple-50 text-purple-700 border border-purple-200"
                              : st === "SENT" || st === "SENT_SIMULATED"
                              ? "bg-blue-50 text-blue-700 border border-blue-200"
                              : "bg-red-50 text-red-700 border border-red-200"
                          }`}
                        >
                          {st === "READ" && <Eye className="w-3 h-3" />}
                          {st === "DELIVERED" && <CheckCheck className="w-3 h-3" />}
                          {(st === "SENT" || st === "SENT_SIMULATED") && <Send className="w-3 h-3" />}
                          {(st === "FAILED" || st.startsWith("BLOCKED")) && <AlertTriangle className="w-3 h-3" />}
                          {st}
                        </span>
                      </td>
                      <td className="px-6 py-3.5 font-mono text-[11px]">
                        {rec.error_message ? (
                          <span className="text-red-600 line-clamp-1" title={rec.error_message}>
                            {rec.error_message}
                          </span>
                        ) : rec.meta_message_id ? (
                          <span className="text-gray-400 truncate max-w-[160px] inline-block" title={rec.meta_message_id}>
                            {rec.meta_message_id}
                          </span>
                        ) : (
                          <span className="text-gray-300">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between text-xs text-gray-500">
          <div>
            Showing <strong>{filteredRecipients.length}</strong> of <strong>{recipients.length}</strong> recipients
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-gray-800 hover:bg-gray-900 text-white rounded-lg font-semibold transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
