import React from "react";
import { Trash2 } from "lucide-react";
import { formatToIST } from "../utils/dateUtils";

export default function OptOutPage({ optOuts = [], handleRemoveOptOut }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h3 className="font-bold text-gray-900 text-base">Opt-Out & Do Not Disturb (DND) Registry</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Customers who texted STOP / બંધ કરો / रोको. Never messaged automatically.
          </p>
        </div>
        <span className="px-3 py-1 text-xs font-bold rounded-full bg-red-50 text-red-600 border border-red-200">
          {optOuts.length} Numbers Blocked
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-gray-600">
          <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
            <tr>
              <th className="px-6 py-3">Phone Number</th>
              <th className="px-6 py-3">Reason / Text Trigger</th>
              <th className="px-6 py-3">Unsubscribed At</th>
              <th className="px-6 py-3">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {optOuts.map((opt) => (
              <tr key={opt.id} className="hover:bg-gray-50/80 transition">
                <td className="px-6 py-4 font-mono font-bold text-gray-900">{opt.phone}</td>
                <td className="px-6 py-4 text-xs font-mono text-red-600 bg-red-50/50 rounded inline-block my-2 px-2 py-1">
                  {opt.reason}
                </td>
                <td className="px-6 py-4 text-xs font-mono text-gray-500">
                  {formatToIST(opt.created_at)}
                </td>
                <td className="px-6 py-4">
                  <button
                    onClick={() => handleRemoveOptOut(opt.phone)}
                    className="text-xs text-gray-400 hover:text-red-600 transition flex items-center gap-1"
                    title="Unblock customer"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
