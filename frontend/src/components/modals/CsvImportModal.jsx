import React, { useState, useEffect } from "react";
import { Upload, ArrowRight, Check, X, FileText, Settings2, RefreshCw } from "lucide-react";

export default function CsvImportModal({
  isOpen,
  onClose,
  csvFile,
  setCsvFile,
  csvImporting,
  onSubmit
}) {
  const [headers, setHeaders] = useState([]);
  const [previewRows, setPreviewRows] = useState([]);
  const [step, setStep] = useState(1); // 1 = select file, 2 = map columns
  const [mappings, setMappings] = useState({
    phone: "",
    name: "",
    first_name: "",
    last_name: "",
    email: "",
    city: "",
    tags: "",
    total_orders: ""
  });

  // When a file is selected, parse header row and first few sample rows
  useEffect(() => {
    if (!csvFile) {
      setHeaders([]);
      setPreviewRows([]);
      setStep(1);
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target.result;
      const lines = text.split(/\r\n|\n/).filter((l) => l.trim().length > 0);
      if (lines.length > 0) {
        // Parse CSV line handling quoted values
        const parseLine = (line) => {
          const result = [];
          let cur = "";
          let inQuotes = false;
          for (let i = 0; i < line.length; i++) {
            const char = line[i];
            if (char === '"' || char === "'") {
              inQuotes = !inQuotes;
            } else if (char === "," && !inQuotes) {
              result.push(cur.trim());
              cur = "";
            } else {
              cur += char;
            }
          }
          result.push(cur.trim());
          return result;
        };

        const rawHeaders = parseLine(lines[0]).map((h) => h.replace(/^\uFEFF/, "").replace(/['"]/g, ""));
        setHeaders(rawHeaders);

        // Preview up to 3 sample rows
        const samples = lines.slice(1, 4).map((l) => parseLine(l));
        setPreviewRows(samples);

        // Auto-detect columns
        const detected = {
          phone: "",
          name: "",
          first_name: "",
          last_name: "",
          email: "",
          city: "",
          tags: "",
          total_orders: ""
        };

        rawHeaders.forEach((h) => {
          const lower = h.toLowerCase();
          if (!detected.phone && (lower.includes("phone") || lower.includes("mobile") || lower.includes("number") || lower.includes("contact"))) {
            detected.phone = h;
          } else if (!detected.first_name && (lower.includes("first") && lower.includes("name"))) {
            detected.first_name = h;
          } else if (!detected.last_name && (lower.includes("last") && lower.includes("name"))) {
            detected.last_name = h;
          } else if (!detected.name && (lower.includes("name") || lower.includes("customer"))) {
            detected.name = h;
          } else if (!detected.email && lower.includes("email")) {
            detected.email = h;
          } else if (!detected.city && (lower.includes("city") || lower.includes("state") || lower.includes("location"))) {
            detected.city = h;
          } else if (!detected.tags && (lower.includes("tag") || lower.includes("segment") || lower.includes("category"))) {
            detected.tags = h;
          } else if (!detected.total_orders && (lower.includes("order") || lower.includes("count"))) {
            detected.total_orders = h;
          }
        });

        setMappings(detected);
        setStep(2);
      }
    };
    reader.readAsText(csvFile);
  }, [csvFile]);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!mappings.phone) {
      alert("Please map the Phone Number column before importing.");
      return;
    }
    onSubmit(e, mappings);
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-gray-100 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Upload className="w-5 h-5 text-[#25D366]" />
            <div>
              <h3 className="font-bold text-base text-gray-900">Import Contacts (CSV)</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                {step === 1 ? "Select CSV file from your computer" : `Map columns for: ${csvFile?.name}`}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto mt-4 space-y-4">
          {step === 1 && (
            <div className="border-2 border-dashed border-gray-300 rounded-2xl p-8 text-center hover:border-[#25D366] transition bg-gray-50/50">
              <input
                type="file"
                accept=".csv"
                required
                id="csvFileInput"
                onChange={(e) => {
                  const selected = e.target.files[0];
                  if (selected && selected.size > 100 * 1024 * 1024) {
                    alert(`File is too large (${(selected.size / (1024 * 1024)).toFixed(2)}MB). Max upload limit is 100MB.`);
                    e.target.value = null;
                    setCsvFile(null);
                    return;
                  }
                  setCsvFile(selected);
                }}
                className="hidden"
              />
              <label htmlFor="csvFileInput" className="cursor-pointer flex flex-col items-center">
                <Upload className="w-10 h-10 text-gray-400 mb-3" />
                <span className="text-sm font-bold text-gray-800">
                  {csvFile ? csvFile.name : "Click to select a CSV file"}
                </span>
                <span className="text-xs text-gray-400 mt-1">Supports standard CSV files up to 100MB (100,000+ contacts)</span>
              </label>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-xs text-emerald-800">
                <span className="font-semibold">
                  Detected {headers.length} columns in file
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setCsvFile(null);
                    setStep(1);
                  }}
                  className="font-bold underline text-emerald-700 hover:text-emerald-900"
                >
                  Change File
                </button>
              </div>

              {/* Column Mapping Fields */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
                  <Settings2 className="w-3.5 h-3.5 text-gray-500" />
                  Map CSV Columns to System Fields
                </h4>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  {/* Phone (Required) */}
                  <div className="col-span-full bg-amber-50/60 p-3 rounded-xl border border-amber-200">
                    <label className="block font-bold text-amber-900 mb-1 flex items-center justify-between">
                      <span>Phone Number * (Required)</span>
                      <span className="text-[10px] text-amber-700 font-normal">Auto-formats to +91</span>
                    </label>
                    <select
                      value={mappings.phone}
                      onChange={(e) => setMappings({ ...mappings, phone: e.target.value })}
                      required
                      className="w-full bg-white border border-amber-300 rounded-lg px-2.5 py-1.5 text-xs font-medium text-gray-900 focus:outline-none focus:ring-2 focus:ring-amber-500"
                    >
                      <option value="">-- Select Phone Column --</option>
                      {headers.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Single Name */}
                  <div>
                    <label className="block font-semibold text-gray-700 mb-1">
                      Full Name (or leave blank if separate)
                    </label>
                    <select
                      value={mappings.name}
                      onChange={(e) => setMappings({ ...mappings, name: e.target.value })}
                      className="w-full bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-900 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                    >
                      <option value="">-- None / Use First+Last --</option>
                      {headers.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Email */}
                  <div>
                    <label className="block font-semibold text-gray-700 mb-1">
                      Email Address
                    </label>
                    <select
                      value={mappings.email}
                      onChange={(e) => setMappings({ ...mappings, email: e.target.value })}
                      className="w-full bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-900 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                    >
                      <option value="">-- None --</option>
                      {headers.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* First Name */}
                  <div>
                    <label className="block font-semibold text-gray-700 mb-1">
                      First Name
                    </label>
                    <select
                      value={mappings.first_name}
                      onChange={(e) => setMappings({ ...mappings, first_name: e.target.value })}
                      className="w-full bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-900 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                    >
                      <option value="">-- None --</option>
                      {headers.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Last Name */}
                  <div>
                    <label className="block font-semibold text-gray-700 mb-1">
                      Last Name
                    </label>
                    <select
                      value={mappings.last_name}
                      onChange={(e) => setMappings({ ...mappings, last_name: e.target.value })}
                      className="w-full bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-900 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                    >
                      <option value="">-- None --</option>
                      {headers.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* City */}
                  <div>
                    <label className="block font-semibold text-gray-700 mb-1">
                      City / Location
                    </label>
                    <select
                      value={mappings.city}
                      onChange={(e) => setMappings({ ...mappings, city: e.target.value })}
                      className="w-full bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-900 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                    >
                      <option value="">-- None --</option>
                      {headers.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Tags */}
                  <div>
                    <label className="block font-semibold text-gray-700 mb-1">
                      Tags / Segment
                    </label>
                    <select
                      value={mappings.tags}
                      onChange={(e) => setMappings({ ...mappings, tags: e.target.value })}
                      className="w-full bg-gray-50 border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-900 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                    >
                      <option value="">-- None --</option>
                      {headers.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Data Sample Preview */}
              {previewRows.length > 0 && (
                <div className="mt-3">
                  <span className="text-[11px] font-bold text-gray-500 uppercase block mb-1">
                    First Row Sample:
                  </span>
                  <div className="p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-[11px] font-mono text-gray-600 truncate">
                    {headers.map((h, idx) => (
                      <span key={h} className="mr-3">
                        <strong className="text-gray-900">{h}:</strong> {previewRows[0]?.[idx] || "-"}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Footer Actions */}
          <div className="pt-4 border-t border-gray-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={csvImporting}
              className="px-4 py-2 border border-gray-200 rounded-xl text-xs font-semibold text-gray-700 hover:bg-gray-50 transition"
            >
              Cancel
            </button>
            {step === 2 && (
              <button
                type="submit"
                disabled={csvImporting || !mappings.phone}
                className="flex items-center gap-1.5 bg-[#25D366] hover:bg-[#1EBE5D] disabled:opacity-50 text-white px-5 py-2 rounded-xl font-bold text-xs shadow-md shadow-emerald-500/20 transition"
              >
                {csvImporting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Importing Contacts...
                  </>
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    Confirm & Import
                  </>
                )}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}