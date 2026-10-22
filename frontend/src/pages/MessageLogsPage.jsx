import React, { useState } from "react";
import {
  Search, Download, Trash2, AlertTriangle, RefreshCw, CheckCircle2,
  FileSpreadsheet, FileCode, Filter, Clock, ShieldAlert, X
} from "lucide-react";
import { formatToIST } from "../utils/dateUtils";
import axios from "../api";

export default function MessageLogsPage({
  messageLogs = [],
  onRefresh,
  token,
  onShowToast
}) {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [downloading, setDownloading] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteOption, setDeleteOption] = useState("90"); // "90" | "120" | "175" | "all"
  const [customDays, setCustomDays] = useState("");
  const [deleteSuccess, setDeleteSuccess] = useState("");
  const [deleteError, setDeleteError] = useState("");

  // Filter logs by search (phone, template, meta ID, user) & status
  const filteredLogs = messageLogs.filter((log) => {
    if (statusFilter !== "ALL" && log.status !== statusFilter) return false;
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      (log.recipient_phone || "").toLowerCase().includes(term) ||
      (log.template_name || "").toLowerCase().includes(term) ||
      (log.meta_message_id || "").toLowerCase().includes(term) ||
      (log.sender_user || "").toLowerCase().includes(term) ||
      (log.error_message || "").toLowerCase().includes(term)
    );
  });

  // Handle Download (CSV or JSON)
  const handleDownloadLogs = async (format = "csv") => {
    try {
      setDownloading(true);
      const res = await axios.get(`/api/message-logs/download?format=${format}`, {
        responseType: "blob",
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      const blob = new Blob([res.data], {
        type: format === "json" ? "application/json" : "text/csv;charset=utf-8;"
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      const dateStr = new Date().toISOString().split("T")[0];
      link.href = url;
      link.setAttribute("download", `whatsapp_message_logs_${dateStr}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
      if (onShowToast) onShowToast(`📥 Downloaded logs as ${format.toUpperCase()}`);
    } catch (err) {
      alert("Failed to download logs: " + (err.response?.data?.detail || err.message));
    } finally {
      setDownloading(false);
    }
  };

  // Handle Delete Logs (Older than 90, 120, 175 days, or All)
  const handleConfirmDelete = async () => {
    setDeleteLoading(true);
    setDeleteError("");
    setDeleteSuccess("");
    try {
      let url = "/api/message-logs";
      let daysParam = null;

      if (deleteOption === "90") daysParam = 90;
      else if (deleteOption === "120") daysParam = 120;
      else if (deleteOption === "175") daysParam = 175;
      else if (deleteOption === "custom") {
        const parsed = parseInt(customDays, 10);
        if (isNaN(parsed) || parsed < 1) {
          setDeleteError("Please enter a valid number of days (at least 1 day).");
          setDeleteLoading(false);
          return;
        }
        daysParam = parsed;
      }

      if (daysParam !== null) {
        url += `?older_than_days=${daysParam}`;
      }

      const res = await axios.delete(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });

      setDeleteSuccess(res.data?.message || "Logs purged successfully.");
      if (onRefresh) onRefresh();
      if (onShowToast) onShowToast(`🗑️ ${res.data?.message || "Logs deleted"}`);

      setTimeout(() => {
        setIsDeleteModalOpen(false);
        setDeleteSuccess("");
      }, 1400);
    } catch (err) {
      setDeleteError(err.response?.data?.detail || err.message || "Failed to delete logs.");
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Main Table Card */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        {/* Header & Controls */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-wrap gap-3">
          <div>
            <h3 className="font-bold text-gray-900 text-base">Complete WhatsApp Audit Trail</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Full delivery logs with user tracking, Meta message IDs, and retention management
            </p>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Search Input */}
            <div className="relative w-56">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search phone, user, template..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3.5 py-1.5 border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-1 bg-gray-50 p-1 rounded-lg border border-gray-200 text-xs">
              {["ALL", "SENT", "DELIVERED", "READ", "FAILED"].map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold transition cursor-pointer ${
                    statusFilter === s
                      ? "bg-gray-900 text-white shadow-2xs"
                      : "text-gray-500 hover:text-gray-900"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            {/* Download Dropdown / Buttons */}
            <button
              type="button"
              disabled={downloading || messageLogs.length === 0}
              onClick={() => handleDownloadLogs("csv")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 transition shadow-2xs disabled:opacity-50 cursor-pointer"
              title="Download Logs as CSV"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
              <span>Export CSV</span>
            </button>

            <button
              type="button"
              disabled={downloading || messageLogs.length === 0}
              onClick={() => handleDownloadLogs("json")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 transition shadow-2xs disabled:opacity-50 cursor-pointer"
              title="Download Logs as JSON"
            >
              <FileCode className="w-3.5 h-3.5 text-indigo-600" />
              <span>JSON</span>
            </button>

            {/* Delete Logs Button */}
            <button
              type="button"
              onClick={() => {
                setDeleteError("");
                setDeleteSuccess("");
                setIsDeleteModalOpen(true);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 transition shadow-2xs cursor-pointer"
              title="Purge logs by retention period or wipe all"
            >
              <Trash2 className="w-3.5 h-3.5 text-rose-600" />
              <span>Delete Logs</span>
            </button>
          </div>
        </div>

        {/* Audit Trail Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600">
            <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
              <tr>
                <th className="px-5 py-3 whitespace-nowrap">Recipient Phone</th>
                <th className="px-5 py-3 whitespace-nowrap">Initiated By / User</th>
                <th className="px-5 py-3 whitespace-nowrap">Template</th>
                <th className="px-5 py-3 whitespace-nowrap">Meta Message ID</th>
                <th className="px-5 py-3 whitespace-nowrap">Timestamp</th>
                <th className="px-5 py-3 whitespace-nowrap">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-gray-400 text-xs">
                    No message logs found matching your filters.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50/80 transition">
                    <td className="px-5 py-4 font-semibold text-gray-900 font-mono">
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#25D366] shrink-0" />
                        {log.recipient_phone}
                      </div>
                    </td>

                    {/* Initiated By / User Column */}
                    <td className="px-5 py-4">
                      {(() => {
                        const sender = log.sender_user || "System";
                        const isApi = sender.toLowerCase().includes("admin") || sender.toLowerCase().includes("api");
                        const isJourney = sender.toLowerCase().includes("journey");
                        const isCampaign = sender.toLowerCase().includes("campaign");
                        const isRule = sender.toLowerCase().includes("rule");

                        let badgeStyle = "bg-gray-100 text-gray-700 border-gray-200";
                        if (isApi) badgeStyle = "bg-amber-50 text-amber-800 border-amber-300";
                        else if (isJourney) badgeStyle = "bg-blue-50 text-blue-700 border-blue-200";
                        else if (isCampaign) badgeStyle = "bg-purple-50 text-purple-700 border-purple-200";
                        else if (isRule) badgeStyle = "bg-emerald-50 text-emerald-700 border-emerald-200";

                        return (
                          <span className={`inline-flex items-center gap-1 text-[11px] font-mono font-semibold px-2 py-0.5 rounded border ${badgeStyle}`}>
                            {isApi && <span className="text-[10px]">🔑</span>}
                            {sender}
                          </span>
                        );
                      })()}
                    </td>

                    <td className="px-5 py-4 font-mono text-xs text-gray-800">
                      {log.template_name}
                    </td>

                    <td className="px-5 py-4 font-mono text-xs text-gray-400 max-w-xs truncate" title={log.meta_message_id}>
                      {log.meta_message_id || "-"}
                    </td>

                    <td className="px-5 py-4 text-xs font-mono text-gray-500 whitespace-nowrap">
                      {formatToIST(log.created_at)}
                    </td>

                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          log.status === "FAILED"
                            ? "bg-red-50 text-red-700 border border-red-200"
                            : log.status.startsWith("BLOCKED")
                            ? "bg-purple-50 text-purple-700 border border-purple-200"
                            : log.status === "SENT_SIMULATED"
                            ? "bg-amber-50 text-amber-700 border border-amber-200"
                            : log.status === "READ"
                            ? "bg-teal-50 text-teal-700 border border-teal-200"
                            : log.status === "DELIVERED"
                            ? "bg-blue-50 text-blue-700 border border-blue-200"
                            : "bg-emerald-50 text-[#10B981] border border-emerald-200"
                        }`}
                      >
                        {log.status}
                      </span>
                      {log.error_message && (
                        <p
                          className="text-[10px] text-red-600 font-mono mt-1 max-w-xs truncate"
                          title={log.error_message}
                        >
                          {log.error_message}
                        </p>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Retention / Delete Logs Modal */}
      {isDeleteModalOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-2 text-rose-700">
                <Trash2 className="w-5 h-5" />
                <h3 className="font-bold text-gray-900 text-base">Purge Audit Logs</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsDeleteModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs text-gray-600">
              <p className="text-gray-600 leading-relaxed">
                Choose a retention cleanup option to remove older WhatsApp delivery audit trails, or clear all records.
              </p>

              {deleteError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs font-semibold flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{deleteError}</span>
                </div>
              )}

              {deleteSuccess && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-semibold flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>{deleteSuccess}</span>
                </div>
              )}

              {/* Retention Choices */}
              <div className="space-y-2">
                <label
                  className={`flex items-center justify-between p-3 rounded-xl border transition cursor-pointer ${
                    deleteOption === "90"
                      ? "border-rose-500 bg-rose-50/50 text-rose-950 font-bold"
                      : "border-gray-200 bg-white hover:bg-gray-50"
                  }`}
                  onClick={() => setDeleteOption("90")}
                >
                  <div className="flex items-center gap-2.5">
                    <input
                      type="radio"
                      name="retention"
                      checked={deleteOption === "90"}
                      onChange={() => setDeleteOption("90")}
                      className="text-rose-600 focus:ring-rose-500"
                    />
                    <div>
                      <div className="text-xs font-bold text-gray-900">Delete logs older than 90 days</div>
                      <div className="text-[10px] text-gray-500">Keep recent 3 months of logs</div>
                    </div>
                  </div>
                  <span className="text-[11px] font-mono text-gray-500">&gt; 90d</span>
                </label>

                <label
                  className={`flex items-center justify-between p-3 rounded-xl border transition cursor-pointer ${
                    deleteOption === "120"
                      ? "border-rose-500 bg-rose-50/50 text-rose-950 font-bold"
                      : "border-gray-200 bg-white hover:bg-gray-50"
                  }`}
                  onClick={() => setDeleteOption("120")}
                >
                  <div className="flex items-center gap-2.5">
                    <input
                      type="radio"
                      name="retention"
                      checked={deleteOption === "120"}
                      onChange={() => setDeleteOption("120")}
                      className="text-rose-600 focus:ring-rose-500"
                    />
                    <div>
                      <div className="text-xs font-bold text-gray-900">Delete logs older than 120 days</div>
                      <div className="text-[10px] text-gray-500">Keep recent 4 months of logs</div>
                    </div>
                  </div>
                  <span className="text-[11px] font-mono text-gray-500">&gt; 120d</span>
                </label>

                <label
                  className={`flex items-center justify-between p-3 rounded-xl border transition cursor-pointer ${
                    deleteOption === "175"
                      ? "border-rose-500 bg-rose-50/50 text-rose-950 font-bold"
                      : "border-gray-200 bg-white hover:bg-gray-50"
                  }`}
                  onClick={() => setDeleteOption("175")}
                >
                  <div className="flex items-center gap-2.5">
                    <input
                      type="radio"
                      name="retention"
                      checked={deleteOption === "175"}
                      onChange={() => setDeleteOption("175")}
                      className="text-rose-600 focus:ring-rose-500"
                    />
                    <div>
                      <div className="text-xs font-bold text-gray-900">Delete logs older than 175 days</div>
                      <div className="text-[10px] text-gray-500">Keep recent ~6 months of logs</div>
                    </div>
                  </div>
                  <span className="text-[11px] font-mono text-gray-500">&gt; 175d</span>
                </label>

                <label
                  className={`flex items-center justify-between p-3 rounded-xl border transition cursor-pointer ${
                    deleteOption === "custom"
                      ? "border-rose-500 bg-rose-50/50 text-rose-950 font-bold"
                      : "border-gray-200 bg-white hover:bg-gray-50"
                  }`}
                  onClick={() => setDeleteOption("custom")}
                >
                  <div className="flex items-center gap-2.5">
                    <input
                      type="radio"
                      name="retention"
                      checked={deleteOption === "custom"}
                      onChange={() => setDeleteOption("custom")}
                      className="text-rose-600 focus:ring-rose-500"
                    />
                    <div>
                      <div className="text-xs font-bold text-gray-900">Custom Days Threshold</div>
                      <div className="text-[10px] text-gray-500">Specify any custom retention period</div>
                    </div>
                  </div>
                </label>

                {deleteOption === "custom" && (
                  <div className="pl-6 pt-1">
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min="1"
                        placeholder="e.g. 60"
                        value={customDays}
                        onChange={(e) => setCustomDays(e.target.value)}
                        className="w-24 px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-bold focus:outline-none focus:ring-2 focus:ring-rose-500"
                      />
                      <span className="text-xs text-gray-500">days</span>
                    </div>
                  </div>
                )}

                <label
                  className={`flex items-center justify-between p-3 rounded-xl border transition cursor-pointer ${
                    deleteOption === "all"
                      ? "border-red-600 bg-red-50 text-red-950 font-bold"
                      : "border-gray-200 bg-white hover:bg-gray-50"
                  }`}
                  onClick={() => setDeleteOption("all")}
                >
                  <div className="flex items-center gap-2.5">
                    <input
                      type="radio"
                      name="retention"
                      checked={deleteOption === "all"}
                      onChange={() => setDeleteOption("all")}
                      className="text-red-600 focus:ring-red-500"
                    />
                    <div>
                      <div className="text-xs font-bold text-red-700">Clear All Logs</div>
                      <div className="text-[10px] text-gray-500">Permanently wipe all message logs</div>
                    </div>
                  </div>
                  <span className="text-[10px] font-bold text-red-700 uppercase bg-red-100 px-2 py-0.5 rounded">
                    Danger
                  </span>
                </label>
              </div>
            </div>

            <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex items-center justify-end gap-2.5">
              <button
                type="button"
                disabled={deleteLoading}
                onClick={() => setIsDeleteModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-gray-700 bg-white border border-gray-300 hover:bg-gray-100 transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleteLoading}
                onClick={handleConfirmDelete}
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 transition disabled:opacity-50 inline-flex items-center gap-1.5 cursor-pointer shadow-xs"
              >
                {deleteLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <span>
                  {deleteOption === "all"
                    ? "Confirm Clear All Logs"
                    : `Purge Logs (> ${deleteOption === "custom" ? customDays || "X" : deleteOption}d)`}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
