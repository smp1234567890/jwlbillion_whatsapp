import React from "react";
import { Upload } from "lucide-react";

export default function CsvImportModal({
  isOpen,
  onClose,
  csvFile,
  setCsvFile,
  csvImporting,
  onSubmit
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-200">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Upload className="w-5 h-5 text-[#25D366]" />
            <h3 className="font-bold text-base text-gray-900">Bulk Import Contacts (CSV)</h3>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 font-bold text-xl">✕</button>
        </div>

        <form onSubmit={onSubmit} className="mt-5 space-y-4">
          <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center hover:border-[#25D366] transition">
            <input
              type="file"
              accept=".csv"
              required
              id="csvFileInput"
              onChange={(e) => {
                const selected = e.target.files[0];
                if (selected && selected.size > 5 * 1024 * 1024) {
                  alert(`File is too large (${(selected.size / (1024 * 1024)).toFixed(2)}MB). Max upload limit is 5MB.`);
                  e.target.value = null;
                  setCsvFile(null);
                  return;
                }
                setCsvFile(selected);
              }}
              className="hidden"
            />
            <label htmlFor="csvFileInput" className="cursor-pointer flex flex-col items-center">
              <Upload className="w-8 h-8 text-gray-400 mb-2" />
              <span className="text-xs font-bold text-gray-700">
                {csvFile ? csvFile.name : "Click to select a CSV file"}
              </span>
              <span className="text-[11px] text-gray-400 mt-1">Max 5MB • UTF-8 format recommended</span>
            </label>
          </div>

          <div className="bg-gray-50 p-3 rounded-lg border border-gray-200 text-xs text-gray-600 space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-gray-900">Expected CSV Columns:</span>
              <span className="text-[10px] bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded border border-emerald-200">Max 5MB</span>
            </div>
            <code className="text-[11px] font-mono text-[#D35400] block">phone, name, email, city, tags, total_orders, last_order_date</code>
            <div className="text-[11px] text-gray-400">Example phone: +919876543210 • Date: YYYY-MM-DD</div>
          </div>

          <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={csvImporting || !csvFile}
              className="bg-[#25D366] hover:bg-[#1EBE5D] disabled:opacity-50 text-white px-5 py-2 rounded-lg font-semibold text-sm shadow-md"
            >
              {csvImporting ? "Importing..." : "Upload & Process"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
