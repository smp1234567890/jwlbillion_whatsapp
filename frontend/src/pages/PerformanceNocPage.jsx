import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  Activity,
  Cpu,
  HardDrive,
  Database,
  Clock,
  Radio,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Sliders,
  Layers,
  ArrowUpRight,
  Server,
  Trash2,
  Image as ImageIcon,
  FileText,
  Video,
  ExternalLink,
  Search,
  CheckSquare,
  Square,
  Calendar,
  Filter
} from "lucide-react";

export default function PerformanceNocPage({ token, handleTabChange }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  // Storage files state
  const [storageData, setStorageData] = useState({ total_files: 0, total_mb: 0, files: [] });
  const [storageLoading, setStorageLoading] = useState(false);
  const [storageSearch, setStorageSearch] = useState("");
  const [dateFilter, setDateFilter] = useState("all"); // "all", "7d", "30d", "older30d", "older7d"
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [deletingFile, setDeletingFile] = useState(null);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [deleteMsg, setDeleteMsg] = useState("");

  const fetchStorageFiles = async () => {
    setStorageLoading(true);
    try {
      const res = await axios.get("/api/analytics/storage/files?limit=500", {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      setStorageData(res.data);
      // Clean up selections that no longer exist
      setSelectedFiles((prev) => prev.filter((name) => res.data.files.some((f) => f.name === name)));
    } catch (err) {
      console.error("Failed to load storage files:", err);
    } finally {
      setStorageLoading(false);
    }
  };

  const handleDeleteFile = async (filename) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}"? This will free server disk space permanently.`)) {
      return;
    }
    setDeletingFile(filename);
    setDeleteMsg("");
    try {
      await axios.delete(`/api/analytics/storage/files/${encodeURIComponent(filename)}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      setDeleteMsg(`Deleted ${filename} successfully`);
      setTimeout(() => setDeleteMsg(""), 4000);
      setSelectedFiles((prev) => prev.filter((f) => f !== filename));
      await fetchStorageFiles();
    } catch (err) {
      alert("Failed to delete file: " + (err.response?.data?.detail || err.message));
    } finally {
      setDeletingFile(null);
    }
  };

  const handleBulkDeleteSelected = async () => {
    if (selectedFiles.length === 0) return;
    if (!window.confirm(`Are you sure you want to delete ${selectedFiles.length} selected files? This cannot be undone.`)) {
      return;
    }
    setIsBulkDeleting(true);
    setDeleteMsg("");
    try {
      const res = await axios.post(
        "/api/analytics/storage/files/bulk-delete",
        { filenames: selectedFiles },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      setDeleteMsg(`Successfully deleted ${res.data.deleted_count} files (${res.data.freed_mb} MB freed)`);
      setTimeout(() => setDeleteMsg(""), 4500);
      setSelectedFiles([]);
      await fetchStorageFiles();
    } catch (err) {
      alert("Failed to delete selected files: " + (err.response?.data?.detail || err.message));
    } finally {
      setIsBulkDeleting(false);
    }
  };

  const handleDeleteOlderThan = async (days, label) => {
    if (!window.confirm(`Are you sure you want to delete ALL uploaded files older than ${label}? This cannot be undone.`)) {
      return;
    }
    setIsBulkDeleting(true);
    setDeleteMsg("");
    try {
      const res = await axios.post(
        "/api/analytics/storage/files/bulk-delete",
        { older_than_days: days },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      setDeleteMsg(`Purged ${res.data.deleted_count} files older than ${label} (${res.data.freed_mb} MB freed)`);
      setTimeout(() => setDeleteMsg(""), 4500);
      setSelectedFiles([]);
      await fetchStorageFiles();
    } catch (err) {
      alert("Failed to purge older files: " + (err.response?.data?.detail || err.message));
    } finally {
      setIsBulkDeleting(false);
    }
  };

  const fetchPerformance = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await axios.get("/api/analytics/system-performance", {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      setData(res.data);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      console.error("Failed to load platform performance:", err);
      setError(err.response?.data?.detail || err.message || "Failed to load system metrics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPerformance();
    fetchStorageFiles();
    const interval = setInterval(fetchPerformance, 15000); // 15s auto-refresh
    return () => clearInterval(interval);
  }, [token]);

  const server = data?.server || {};
  const database = data?.database || {};
  const scheduler = data?.scheduler || {};
  const campaigns = data?.campaigns_pipeline || {};
  const automations = data?.automations_pipeline || {};

  const getStatusBadge = (status) => {
    if (status === "HEALTHY" || status === "RUNNING") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
          {status}
        </span>
      );
    }
    if (status === "DEGRADED") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
          {status}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-red-50 text-red-700 border border-red-200">
        <AlertCircle className="w-3.5 h-3.5 text-red-600" />
        {status || "UNKNOWN"}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Top NOC Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-gray-900 text-[#25D366] flex items-center justify-center flex-shrink-0 shadow-xs">
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-gray-900 text-lg">System Performance & NOC Live Center</h3>
              {data?.overall_status && getStatusBadge(data.overall_status)}
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              Live server capacity, CPU load, memory, disk, campaign queue telemetry, and automation pipeline health
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 self-stretch md:self-auto justify-between md:justify-end">
          {lastUpdated && (
            <span className="text-xs text-gray-400 font-mono">
              Auto-updating (15s) • {lastUpdated}
            </span>
          )}
          <a
            href="#noc"
            onClick={(e) => {
              e.preventDefault();
              fetchPerformance();
            }}
            className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 underline flex items-center gap-1"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh Telemetry
          </a>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs font-semibold flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {/* 4 Infrastructure Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
        {/* CPU Load Card */}
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">CPU Load</span>
            <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center">
              <Cpu className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black text-gray-900">
                {server.load_capacity_pct ?? 0}%
              </span>
              <span className="text-xs text-gray-500">
                ({server.cores || 1} Cores)
              </span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2 mt-2 overflow-hidden">
              <div
                className={`h-2 rounded-full transition-all ${
                  (server.load_capacity_pct || 0) > 85
                    ? "bg-red-500"
                    : (server.load_capacity_pct || 0) > 65
                    ? "bg-amber-500"
                    : "bg-emerald-500"
                }`}
                style={{ width: `${Math.min(100, server.load_capacity_pct || 0)}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-gray-500 mt-2 font-mono">
              <span>1m: {server.load_1m ?? "—"}</span>
              <span>5m: {server.load_5m ?? "—"}</span>
              <span>15m: {server.load_15m ?? "—"}</span>
            </div>
          </div>
        </div>

        {/* Memory Usage Card */}
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Process Memory (RSS)</span>
            <div className="w-9 h-9 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center">
              <Server className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-black text-gray-900">
              {server.memory_resident_mb ?? "—"} MB
            </span>
            <p className="text-xs text-gray-500 mt-1">Backend App Memory Footprint</p>
            <div className="flex items-center gap-1.5 text-xs text-emerald-700 font-semibold mt-3">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Optimal memory envelope</span>
            </div>
          </div>
        </div>

        {/* Disk Capacity Card */}
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Disk Capacity</span>
            <div className="w-9 h-9 rounded-lg bg-purple-50 text-purple-700 flex items-center justify-center">
              <HardDrive className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black text-gray-900">
                {server.disk_used_pct ?? 0}%
              </span>
              <span className="text-xs text-gray-500">
                {server.disk_free_gb ?? 0} GB Free
              </span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2 mt-2 overflow-hidden">
              <div
                className={`h-2 rounded-full transition-all ${
                  (server.disk_used_pct || 0) > 90 ? "bg-red-500" : "bg-purple-500"
                }`}
                style={{ width: `${Math.min(100, server.disk_used_pct || 0)}%` }}
              />
            </div>
            <p className="text-[11px] text-gray-500 mt-2 font-mono">
              Used {server.disk_used_gb ?? 0} GB / {server.disk_total_gb ?? 0} GB
            </p>
          </div>
        </div>

        {/* Database & Scheduler Health */}
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Core Engine</span>
            <div className="w-9 h-9 rounded-lg bg-amber-50 text-amber-700 flex items-center justify-center">
              <Database className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500 font-medium">PostgreSQL Latency</span>
              <span className="font-mono font-bold text-gray-900">
                {database.latency_ms ?? 0} ms
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500 font-medium">Scheduler Heartbeat</span>
              <span className="font-semibold text-gray-900">
                {scheduler.status || "—"} ({scheduler.active_jobs_count || 0} jobs)
              </span>
            </div>
            <div className="pt-2 border-t border-gray-100 flex items-center justify-between">
              <span className="text-[11px] text-gray-400">Database Status</span>
              {getStatusBadge(database.status)}
            </div>
          </div>
        </div>
      </div>

      {/* Pipeline Status: Campaigns & Automations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Campaign Broadcast Pipeline & Stuck Detection */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50/50">
            <div>
              <h4 className="font-bold text-gray-900 text-sm flex items-center gap-2">
                <span>Campaign Pipeline & Stuck Inspection</span>
                {campaigns.stuck_count > 0 ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-700 border border-red-200">
                    {campaigns.stuck_count} Stuck / Failed
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                    Smooth Flow
                  </span>
                )}
              </h4>
              <p className="text-xs text-gray-500 mt-0.5">
                Active: {campaigns.active_count || 0} broadcasts running
              </p>
            </div>
            {handleTabChange && (
              <a
                href="#campaigns"
                onClick={(e) => {
                  e.preventDefault();
                  handleTabChange("campaigns");
                }}
                className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 underline flex items-center gap-1"
              >
                <span>View Campaigns</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </a>
            )}
          </div>

          <div className="p-6">
            {campaigns.stuck_items && campaigns.stuck_items.length > 0 ? (
              <div className="space-y-3">
                {campaigns.stuck_items.map((item) => (
                  <div
                    key={item.id}
                    className="p-3.5 rounded-lg border border-red-200 bg-red-50/40 flex flex-col gap-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0" />
                        <span className="font-bold text-xs text-gray-900">{item.title}</span>
                        <span className="font-mono text-[10px] text-gray-400">#{item.id}</span>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-red-100 text-red-800">
                        {item.status}
                      </span>
                    </div>
                    <div className="text-xs text-red-700 font-medium">
                      ⚠️ Reason: {item.stuck_reason}
                    </div>
                    <div className="flex items-center gap-4 text-[11px] text-gray-500 pt-1 border-t border-red-100">
                      <span>Progress: <strong>{item.progress}</strong></span>
                      <span>Attempts: <strong>{item.attempt_count}</strong></span>
                      <span>Template: <strong className="font-mono">{item.template_name}</strong></span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-gray-400">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-80" />
                <p className="text-xs font-bold text-gray-800">No Stuck Campaigns</p>
                <p className="text-[11px] text-gray-500 mt-0.5">
                  All broadcast queues are processing within lease windows and normal delivery limits.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Workflow Automations Pipeline & Delayed Sessions */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50/50">
            <div>
              <h4 className="font-bold text-gray-900 text-sm flex items-center gap-2">
                <span>Automation Engine & Session Health</span>
                {automations.stuck_sessions_count > 0 ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                    {automations.stuck_sessions_count} Delayed
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                    Engine Healthy
                  </span>
                )}
              </h4>
              <p className="text-xs text-gray-500 mt-0.5">
                Active Enrolled Sessions: {automations.active_sessions_count || 0}
              </p>
            </div>
            {handleTabChange && (
              <a
                href="#automations"
                onClick={(e) => {
                  e.preventDefault();
                  handleTabChange("automations");
                }}
                className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 underline flex items-center gap-1"
              >
                <span>View Automations</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </a>
            )}
          </div>

          <div className="p-6">
            {automations.stuck_items && automations.stuck_items.length > 0 ? (
              <div className="space-y-3">
                {automations.stuck_items.map((s) => (
                  <div
                    key={s.session_id}
                    className="p-3.5 rounded-lg border border-amber-200 bg-amber-50/40 flex flex-col gap-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-amber-600 flex-shrink-0" />
                        <span className="font-bold text-xs text-gray-900">
                          Session #{s.session_id} • Flow #{s.flow_id}
                        </span>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-amber-100 text-amber-800">
                        {s.status}
                      </span>
                    </div>
                    <div className="text-xs text-amber-800">
                      ⏱ Overdue by <strong>{s.overdue_by_mins} minutes</strong> (Waiting at step <code className="bg-amber-100 px-1 rounded">{s.current_node_id || "start"}</code>)
                    </div>
                    <div className="text-[11px] text-gray-500 font-mono">
                      Customer: {s.customer_phone} • Attempts: {s.attempt_count}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-gray-400">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-80" />
                <p className="text-xs font-bold text-gray-800">Automations Running Normally</p>
                <p className="text-[11px] text-gray-500 mt-0.5">
                  Workflow conditions, delays, and triggers are evaluating on schedule without backpressure.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Uploaded Media Storage & File Manager */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-gray-50/60">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center flex-shrink-0">
              <HardDrive className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="font-bold text-gray-900 text-sm">Media Storage & Uploaded Files</h4>
                <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-gray-100 text-gray-700 border border-gray-200">
                  {storageData.total_files} files ({storageData.total_mb} MB)
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                Browse, preview, and delete uploaded template images and media to reclaim server disk space
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search file name..."
                value={storageSearch}
                onChange={(e) => setStorageSearch(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-500 w-44"
              />
            </div>
            <button
              onClick={fetchStorageFiles}
              disabled={storageLoading}
              className="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50 flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${storageLoading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>

        {deleteMsg && (
          <div className="mx-6 mt-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-lg flex items-center justify-between">
            <span>✓ {deleteMsg}</span>
          </div>
        )}

        {/* Action & Filter Toolbar */}
        <div className="px-6 py-3 border-b border-gray-100 bg-gray-50/30 flex flex-wrap items-center justify-between gap-3 text-xs">
          {/* Left: Date Filters & Select All */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => {
                const visible = storageData.files.filter((f) => {
                  if (storageSearch && !f.name.toLowerCase().includes(storageSearch.toLowerCase())) return false;
                  if (dateFilter === "all") return true;
                  const daysOld = (Date.now() - new Date(f.modified_at).getTime()) / (1000 * 60 * 60 * 24);
                  if (dateFilter === "7d") return daysOld <= 7;
                  if (dateFilter === "older7d") return daysOld > 7;
                  if (dateFilter === "older30d") return daysOld > 30;
                  return true;
                });
                const visibleNames = visible.map((f) => f.name);
                const allSelected = visibleNames.length > 0 && visibleNames.every((n) => selectedFiles.includes(n));
                if (allSelected) {
                  setSelectedFiles((prev) => prev.filter((n) => !visibleNames.includes(n)));
                } else {
                  setSelectedFiles((prev) => Array.from(new Set([...prev, ...visibleNames])));
                }
              }}
              className="px-2.5 py-1.5 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 font-semibold flex items-center gap-1.5 transition-colors"
            >
              {selectedFiles.length > 0 ? (
                <CheckSquare className="w-3.5 h-3.5 text-emerald-600" />
              ) : (
                <Square className="w-3.5 h-3.5 text-gray-400" />
              )}
              <span>{selectedFiles.length > 0 ? `Selected (${selectedFiles.length})` : "Select All"}</span>
            </button>

            {/* Date Filter Pills */}
            <div className="flex items-center gap-1 bg-gray-100 p-0.5 rounded-lg border border-gray-200 text-[11px]">
              <span className="px-2 text-gray-400 font-medium flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                Date:
              </span>
              <button
                onClick={() => setDateFilter("all")}
                className={`px-2 py-1 rounded-md font-medium transition-colors ${
                  dateFilter === "all" ? "bg-white text-gray-900 shadow-2xs" : "text-gray-600 hover:text-gray-900"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setDateFilter("7d")}
                className={`px-2 py-1 rounded-md font-medium transition-colors ${
                  dateFilter === "7d" ? "bg-white text-gray-900 shadow-2xs" : "text-gray-600 hover:text-gray-900"
                }`}
              >
                Last 7 Days
              </button>
              <button
                onClick={() => setDateFilter("older7d")}
                className={`px-2 py-1 rounded-md font-medium transition-colors ${
                  dateFilter === "older7d" ? "bg-white text-gray-900 shadow-2xs" : "text-gray-600 hover:text-gray-900"
                }`}
              >
                Older than 7d
              </button>
              <button
                onClick={() => setDateFilter("older30d")}
                className={`px-2 py-1 rounded-md font-medium transition-colors ${
                  dateFilter === "older30d" ? "bg-white text-gray-900 shadow-2xs" : "text-gray-600 hover:text-gray-900"
                }`}
              >
                Older than 30d
              </button>
            </div>
          </div>

          {/* Right: Bulk Delete Actions */}
          <div className="flex items-center gap-2">
            {selectedFiles.length > 0 && (
              <button
                onClick={handleBulkDeleteSelected}
                disabled={isBulkDeleting}
                className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold flex items-center gap-1.5 shadow-2xs transition-colors disabled:opacity-50"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>{isBulkDeleting ? "Deleting..." : `Delete Selected (${selectedFiles.length})`}</span>
              </button>
            )}

            {/* Quick Purge by Date */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => handleDeleteOlderThan(7, "7 days")}
                disabled={isBulkDeleting}
                className="px-2.5 py-1.5 rounded-lg border border-red-200 text-red-700 bg-red-50 hover:bg-red-100 font-semibold text-[11px] flex items-center gap-1 transition-colors disabled:opacity-50"
                title="Delete all media files uploaded more than 7 days ago"
              >
                <Trash2 className="w-3 h-3 text-red-500" />
                <span>Delete &gt; 7 Days</span>
              </button>
              <button
                onClick={() => handleDeleteOlderThan(30, "30 days")}
                disabled={isBulkDeleting}
                className="px-2.5 py-1.5 rounded-lg border border-red-200 text-red-700 bg-red-50 hover:bg-red-100 font-semibold text-[11px] flex items-center gap-1 transition-colors disabled:opacity-50"
                title="Delete all media files uploaded more than 30 days ago"
              >
                <Trash2 className="w-3 h-3 text-red-500" />
                <span>Delete &gt; 30 Days</span>
              </button>
            </div>
          </div>
        </div>

        <div className="p-6">
          {storageLoading && storageData.files.length === 0 ? (
            <div className="py-12 text-center text-gray-400">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-emerald-600" />
              <p className="text-xs">Loading storage files...</p>
            </div>
          ) : storageData.files.length === 0 ? (
            <div className="py-12 text-center text-gray-400">
              <ImageIcon className="w-10 h-10 text-gray-300 mx-auto mb-2" />
              <p className="text-xs font-bold text-gray-700">No uploaded files in storage</p>
              <p className="text-[11px] text-gray-400 mt-0.5">Uploads directory is completely empty.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {storageData.files
                .filter((f) => {
                  if (storageSearch && !f.name.toLowerCase().includes(storageSearch.toLowerCase())) {
                    return false;
                  }
                  if (dateFilter === "all") return true;
                  const daysOld = (Date.now() - new Date(f.modified_at).getTime()) / (1000 * 60 * 60 * 24);
                  if (dateFilter === "7d") return daysOld <= 7;
                  if (dateFilter === "older7d") return daysOld > 7;
                  if (dateFilter === "older30d") return daysOld > 30;
                  return true;
                })
                .map((file) => {
                  const mediaUrl = `${axios.defaults.baseURL || "https://130-210-23-25.sslip.io"}${file.url}`;
                  const isDel = deletingFile === file.name;
                  const isSelected = selectedFiles.includes(file.name);

                  return (
                    <div
                      key={file.name}
                      onClick={() => {
                        setSelectedFiles((prev) =>
                          isSelected ? prev.filter((n) => n !== file.name) : [...prev, file.name]
                        );
                      }}
                      className={`border rounded-lg p-3 transition-all bg-white flex flex-col justify-between gap-2.5 shadow-2xs group cursor-pointer ${
                        isSelected
                          ? "border-emerald-500 bg-emerald-50/20 ring-1 ring-emerald-500"
                          : "border-gray-200 hover:border-gray-300"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        {/* Checkbox */}
                        <div
                          className="pt-1 flex-shrink-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedFiles((prev) =>
                              isSelected ? prev.filter((n) => n !== file.name) : [...prev, file.name]
                            );
                          }}
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-emerald-600" />
                          ) : (
                            <Square className="w-4 h-4 text-gray-300 group-hover:text-gray-400" />
                          )}
                        </div>

                        {/* Thumbnail / Icon */}
                        <div className="w-14 h-14 rounded-md bg-gray-100 border border-gray-200 flex-shrink-0 overflow-hidden flex items-center justify-center">
                          {file.is_image ? (
                            <img
                              src={mediaUrl}
                              alt={file.name}
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                e.target.style.display = "none";
                              }}
                            />
                          ) : file.is_video ? (
                            <Video className="w-6 h-6 text-indigo-500" />
                          ) : (
                            <FileText className="w-6 h-6 text-gray-400" />
                          )}
                        </div>

                        {/* File Details */}
                        <div className="flex-1 min-w-0">
                          <p
                            className="text-xs font-semibold text-gray-900 truncate group-hover:text-emerald-700 transition-colors"
                            title={file.name}
                          >
                            {file.name}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[11px] font-mono text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">
                              {file.size_formatted}
                            </span>
                            <span className="text-[10px] text-gray-400">
                              {new Date(file.modified_at).toLocaleDateString([], {
                                month: "short",
                                day: "numeric"
                              })}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Action buttons */}
                      <div
                        className="flex items-center justify-between pt-2 border-t border-gray-100 text-xs"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <a
                          href={mediaUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[11px] font-semibold text-gray-600 hover:text-emerald-700 flex items-center gap-1 transition-colors"
                        >
                          <ExternalLink className="w-3 h-3" />
                          <span>View Full</span>
                        </a>

                        <button
                          onClick={() => handleDeleteFile(file.name)}
                          disabled={isDel || isBulkDeleting}
                          className="px-2 py-1 rounded text-[11px] font-semibold text-red-600 hover:bg-red-50 hover:text-red-700 border border-transparent hover:border-red-200 flex items-center gap-1 transition-all disabled:opacity-50"
                        >
                          <Trash2 className="w-3 h-3" />
                          <span>{isDel ? "Deleting..." : "Delete"}</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
