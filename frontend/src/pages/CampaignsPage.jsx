import React, { useState } from "react";
import {
  Plus,
  Clock,
  Trash2,
  Calendar,
  Zap,
  CheckCircle2,
  AlertTriangle,
  BarChart2,
  Eye
} from "lucide-react";
import { formatToIST, formatScheduleDisplay } from "../utils/dateUtils";
import CampaignReportModal from "../components/modals/CampaignReportModal";

export default function CampaignsPage({
  campaigns = [],
  handleOpenCampaignModal,
  handleCancelScheduledCampaign,
  token
}) {
  const [selectedCampaignForReport, setSelectedCampaignForReport] = useState(null);

  return (
    <>
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h3 className="font-bold text-gray-900 text-base">Campaign Manager</h3>
            <p className="text-xs text-gray-500 mt-0.5">Manage and trigger promotional WhatsApp broadcasts</p>
          </div>
          <button
            onClick={handleOpenCampaignModal}
            className="flex items-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-3.5 py-1.5 rounded-lg font-semibold text-xs shadow-sm transition"
          >
            <Plus className="w-3.5 h-3.5" />
            New Broadcast
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600">
            <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
              <tr>
                <th className="px-5 py-3">ID</th>
                <th className="px-5 py-3">Campaign Title</th>
                <th className="px-5 py-3">Template</th>
                <th className="px-5 py-3">Language</th>
                <th className="px-5 py-3">Target</th>
                <th className="px-5 py-3">Schedule / Trigger Time</th>
                <th className="px-5 py-3">Delivered / Total</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {campaigns.map((c) => {
                const sch = c.scheduled_for ? formatScheduleDisplay(c.scheduled_for) : null;
                return (
                  <tr key={c.id} className="hover:bg-gray-50/80 transition">
                    <td className="px-5 py-4 font-mono text-xs text-gray-400">#{c.id}</td>
                    <td className="px-5 py-4 font-semibold text-gray-900">
                      <button
                        onClick={() => setSelectedCampaignForReport(c)}
                        className="text-left font-semibold text-gray-900 hover:text-emerald-600 transition flex items-center gap-1.5 group"
                        title="Click to view recipient analytics"
                      >
                        <span>{c.title}</span>
                        <Eye className="w-3.5 h-3.5 text-gray-400 opacity-0 group-hover:opacity-100 transition" />
                      </button>
                    </td>
                    <td className="px-5 py-4 font-mono text-xs">{c.template_name}</td>
                    <td className="px-5 py-4 uppercase font-semibold text-xs">{c.language}</td>
                    <td className="px-5 py-4 text-xs">{c.target_filter}</td>
                    <td className="px-5 py-4">
                      {c.scheduled_for ? (
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5 font-semibold text-gray-900 text-xs">
                            <Calendar className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />
                            <span>{sch ? sch.formattedDate : c.scheduled_for}</span>
                          </div>
                          {c.status === "SCHEDULED" && sch?.countdown && (
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                              <Clock className="w-2.5 h-2.5 text-amber-600 animate-pulse" />
                              {sch.countdown}
                            </span>
                          )}
                        </div>
                      ) : (
                        <div className="space-y-0.5">
                          <div className="inline-flex items-center gap-1 text-xs font-semibold text-gray-700 bg-gray-100 px-2 py-0.5 rounded border border-gray-200">
                            <Zap className="w-3 h-3 text-amber-500" />
                            Immediate
                          </div>
                          {c.created_at && (
                            <div className="text-[10px] text-gray-400">
                              {formatToIST(c.created_at)}
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-4 font-bold text-gray-900">
                      <button
                        onClick={() => setSelectedCampaignForReport(c)}
                        className="text-left group cursor-pointer"
                        title="Click to view contact breakdown"
                      >
                        <div className="group-hover:text-emerald-600 transition flex items-center gap-1">
                          <span>{c.successful_sends} / {c.total_recipients}</span>
                          <span className="text-[10px] text-emerald-600 font-normal opacity-0 group-hover:opacity-100 transition">View</span>
                        </div>
                        {c.per_day_limit && (
                          <span className="text-[10px] font-medium text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded border border-purple-200">
                            Limit: {c.per_day_limit}
                          </span>
                        )}
                      </button>
                    </td>
                    <td className="px-5 py-4">
                      {c.status === "SCHEDULED" && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 shadow-xs">
                          <Clock className="w-3.5 h-3.5 text-amber-600 animate-pulse" />
                          SCHEDULED
                        </span>
                      )}
                      {c.status === "IN_PROGRESS" && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 shadow-xs">
                          <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
                          SENDING...
                        </span>
                      )}
                      {c.status === "COMPLETED" && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          COMPLETED
                        </span>
                      )}
                      {c.status === "CANCELLED" && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-600 border border-gray-300">
                          CANCELLED
                        </span>
                      )}
                      {c.status === "FAILED" && (
                        <div>
                          <span
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200 cursor-help"
                            title={c.error_message || "Campaign failed during execution"}
                          >
                            <AlertTriangle className="w-3.5 h-3.5 text-red-600" />
                            FAILED
                          </span>
                          {c.error_message && (
                            <p className="text-[10px] text-red-600 font-mono mt-1 max-w-[220px] line-clamp-2" title={c.error_message}>
                              {c.error_message}
                            </p>
                          )}
                        </div>
                      )}
                      {!["SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "FAILED"].includes(c.status) && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-200">
                          {c.status}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <div className="inline-flex items-center gap-2 justify-end">
                        <button
                          onClick={() => setSelectedCampaignForReport(c)}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold text-gray-700 hover:text-emerald-700 bg-gray-100 hover:bg-emerald-50 border border-gray-200 hover:border-emerald-300 rounded-lg transition"
                          title="View detailed recipient contacts & delivery report"
                        >
                          <BarChart2 className="w-3.5 h-3.5 text-emerald-600" />
                          <span>View Report</span>
                        </button>
                        {c.status === "SCHEDULED" && (
                          <button
                            onClick={() => handleCancelScheduledCampaign(c.id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-red-600 hover:text-red-800 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg transition"
                            title="Cancel this scheduled broadcast"
                          >
                            <Trash2 className="w-3 h-3" />
                            Cancel
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Campaign Recipient & Delivery Analytics Modal */}
      <CampaignReportModal
        isOpen={Boolean(selectedCampaignForReport)}
        onClose={() => setSelectedCampaignForReport(null)}
        campaign={selectedCampaignForReport}
        token={token}
      />
    </>
  );
}
