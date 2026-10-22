import React from "react";
import { TEMPLATE_FIELD_OPTIONS } from "../../constants/fieldOptions";

export default function TemplateMappingModal({
  editMappingTemplate,
  editMappings,
  setEditMappings,
  onClose,
  onSave
}) {
  if (!editMappingTemplate) return null;

  const params = [...new Set([...(editMappingTemplate.body_text || "").matchAll(/\{\{([a-zA-Z0-9_-]+)\}\}/g)].map((m) => m[1]))];

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-gray-200 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div>
            <h3 className="font-bold text-base text-gray-900">Configure Column Mappings</h3>
            <p className="text-xs text-gray-500 mt-0.5 font-mono">{editMappingTemplate.template_name}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 font-bold text-xl">✕</button>
        </div>

        <div className="mt-4 space-y-4">
          <p className="text-xs text-gray-600 bg-blue-50 border border-blue-200 rounded-lg p-3">
            📌 Map each <span className="font-mono font-bold">{"{{N}}"}</span> placeholder to a contact/cart/coupon field. This config will automatically apply to all automations and campaigns using this template — no per-flow setup needed.
          </p>

          {/* Template body preview */}
          <div className="bg-gray-50 rounded-xl p-3 border border-gray-200 text-xs text-gray-700 leading-relaxed font-sans">
            {editMappingTemplate.body_text}
          </div>

          {params.length === 0 ? (
            <p className="text-xs text-center text-gray-400 py-4">No placeholders found in this template body text.</p>
          ) : (
            <div className="space-y-3">
              {params.map((param) => {
                const cm = (editMappings || {})[param] || {};
                const isCustomEvent = cm.type === "event_field" && !["first_name", "products_summary", "amount", "delivery_address"].includes(cm.value);
                const isCustomApi = cm.type === "external_api" && !["delivery_address", "tracking_number", "order_status", "estimated_delivery", "support_contact"].includes(cm.value);

                const cv = cm.type ? (
                  isCustomEvent ? "event_field|custom" :
                  isCustomApi ? "external_api|custom" :
                  (cm.type + "|" + (cm.value || ""))
                ) : "";

                return (
                  <div key={param} className="space-y-1.5 p-2.5 rounded-xl bg-gray-50 border border-gray-200">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-blue-800 bg-blue-100 px-2.5 py-1 rounded border border-blue-200 text-xs w-16 text-center">{"{{"}{param}{"}}"}</span>
                      <span className="text-blue-400 font-bold">→</span>
                      <select
                        value={cv}
                        onChange={(e) => {
                          const [type, ...rest] = e.target.value.split("|");
                          const valPart = rest.join("|");
                          const finalVal = valPart === "custom" ? (cm.value || "") : valPart;
                          setEditMappings((prev) => ({ ...prev, [param]: { type, value: finalVal } }));
                        }}
                        className="flex-1 px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
                      >
                        <option value="">— choose field —</option>
                        {TEMPLATE_FIELD_OPTIONS.map((g) => (
                          <optgroup key={g.group} label={g.group}>
                            {g.options.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                          </optgroup>
                        ))}
                      </select>
                    </div>

                    {/* Secondary input for custom keys or static text */}
                    {cm.type === "static" && (
                      <div className="flex items-center gap-2 pl-20">
                        <input
                          type="text"
                          placeholder="Enter fixed text (e.g. Ahmedabad)"
                          value={cm.value || ""}
                          onChange={(e) => setEditMappings((prev) => ({ ...prev, [param]: { type: "static", value: e.target.value } }))}
                          className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 bg-white"
                        />
                      </div>
                    )}

                    {cm.type === "event_field" && isCustomEvent && (
                      <div className="flex items-center gap-2 pl-20">
                        <span className="text-[10px] text-gray-500 font-semibold">JSON Key:</span>
                        <input
                          type="text"
                          placeholder="e.g. shipping_address or customer_pincode"
                          value={cm.value || ""}
                          onChange={(e) => setEditMappings((prev) => ({ ...prev, [param]: { type: "event_field", value: e.target.value } }))}
                          className="w-full px-2.5 py-1.5 border border-purple-300 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 focus:ring-purple-300 bg-white"
                        />
                      </div>
                    )}

                    {cm.type === "external_api" && isCustomApi && (
                      <div className="flex items-center gap-2 pl-20">
                        <span className="text-[10px] text-gray-500 font-semibold">API JSON Key:</span>
                        <input
                          type="text"
                          placeholder="e.g. invoice_url or package_weight"
                          value={cm.value || ""}
                          onChange={(e) => setEditMappings((prev) => ({ ...prev, [param]: { type: "external_api", value: e.target.value } }))}
                          className="w-full px-2.5 py-1.5 border border-emerald-300 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 focus:ring-emerald-300 bg-white"
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onSave}
              className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg font-semibold text-sm shadow-md"
            >
              Save Mappings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
