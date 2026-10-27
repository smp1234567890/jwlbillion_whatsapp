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
  Server
} from "lucide-react";

export default function PerformanceNocPage({ token, handleTabChange }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

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
    </div>
  );
}
