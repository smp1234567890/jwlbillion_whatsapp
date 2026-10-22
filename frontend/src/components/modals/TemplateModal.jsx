import React from "react";
import { TEMPLATE_FIELD_OPTIONS } from "../../constants/fieldOptions";

export default function TemplateModal({
  isOpen,
  onClose,
  newTemplate,
  setNewTemplate,
  onSubmit
}) {
  if (!isOpen) return null;

  const params = [...new Set([...(newTemplate.body_text || "").matchAll(/\{\{([a-zA-Z0-9_-]+)\}\}/g)].map((m) => m[1]))];

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-gray-200 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div>
            <h3 className="font-bold text-base text-gray-900">Create & Submit WhatsApp Template</h3>
            <p className="text-xs text-gray-500">Submits to Meta Graph API & saves to your local catalog</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 font-bold text-xl">✕</button>
        </div>

        <form onSubmit={onSubmit} className="mt-4 space-y-3.5">
          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Template Identifier (lowercase, underscores)</label>
            <input
              type="text"
              required
              placeholder="e.g. holi_special_namkeen"
              value={newTemplate.template_name}
              onChange={(e) => setNewTemplate({ ...newTemplate, template_name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })}
              className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Category</label>
              <select
                value={newTemplate.category}
                onChange={(e) => setNewTemplate({ ...newTemplate, category: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              >
                <option value="MARKETING">MARKETING</option>
                <option value="UTILITY">UTILITY</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Language</label>
              <select
                value={newTemplate.language}
                onChange={(e) => setNewTemplate({ ...newTemplate, language: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              >
                <option value="en">English (en)</option>
                <option value="gu">ગુજરાતી (gu)</option>
                <option value="hi">हिंदी (hi)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Header Title (Optional)</label>
            <input
              type="text"
              placeholder="e.g. JWL"
              value={newTemplate.header_text || ""}
              onChange={(e) => setNewTemplate({ ...newTemplate, header_text: e.target.value })}
              className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Message Body</label>
            <textarea
              rows={4}
              required
              placeholder="Hello {{1}}, enjoy fresh jewelry collection with {{2}}% discount! Reply STOP to opt out."
              value={newTemplate.body_text}
              onChange={(e) => setNewTemplate({ ...newTemplate, body_text: e.target.value })}
              className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366] leading-relaxed"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Footer Text</label>
            <input
              type="text"
              placeholder="e.g. JWL • Ahmedabad"
              value={newTemplate.footer_text || ""}
              onChange={(e) => setNewTemplate({ ...newTemplate, footer_text: e.target.value })}
              className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
          </div>

          {/* ── Auto-Detected Column Mapping ── */}
          {params.length > 0 && (
            <div className="border border-blue-200 bg-blue-50 rounded-xl p-3.5 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase text-blue-800">📌 Column Mapping</span>
                <span className="text-[10px] text-blue-600 ml-1">Configure once → auto-used everywhere</span>
              </div>
              {params.map((param) => {
                const cm = (newTemplate.variable_mappings || {})[param] || {};
                const isCustomEvent = cm.type === "event_field" && !["first_name", "products_summary", "amount", "delivery_address"].includes(cm.value);
                const isCustomApi = cm.type === "external_api" && !["delivery_address", "tracking_number", "order_status", "estimated_delivery", "support_contact"].includes(cm.value);

                const cv = cm.type ? (
                  isCustomEvent ? "event_field|custom" :
                  isCustomApi ? "external_api|custom" :
                  (cm.type + "|" + (cm.value || ""))
                ) : "";

                return (
                  <div key={param} className="space-y-1.5 p-2.5 rounded-lg bg-white border border-blue-200">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-blue-800 bg-blue-100 px-2 py-1 rounded border border-blue-200 text-xs w-14 text-center">{"{{"}{param}{"}}"}</span>
                      <span className="text-blue-500 font-bold">→</span>
                      <select
                        value={cv}
                        onChange={(e) => {
                          const [type, ...rest] = e.target.value.split("|");
                          const valPart = rest.join("|");
                          const finalVal = valPart === "custom" ? (cm.value || "") : valPart;
                          setNewTemplate((prev) => ({
                            ...prev,
                            variable_mappings: { ...(prev.variable_mappings || {}), [param]: { type, value: finalVal } }
                          }));
                        }}
                        className="flex-1 px-2.5 py-1.5 border border-blue-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
                      >
                        <option value="">— choose field —</option>
                        {TEMPLATE_FIELD_OPTIONS.map((g) => (
                          <optgroup key={g.group} label={g.group}>
                            {g.options.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                          </optgroup>
                        ))}
                      </select>
                    </div>

                    {cm.type === "static" && (
                      <div className="pl-16">
                        <input
                          type="text"
                          placeholder="Enter fixed text"
                          value={cm.value || ""}
                          onChange={(e) => setNewTemplate((prev) => ({
                            ...prev,
                            variable_mappings: { ...(prev.variable_mappings || {}), [param]: { type: "static", value: e.target.value } }
                          }))}
                          className="w-full px-2.5 py-1.5 border border-blue-200 rounded-lg text-xs"
                        />
                      </div>
                    )}

                    {cm.type === "event_field" && isCustomEvent && (
                      <div className="pl-16 flex items-center gap-1.5">
                        <span className="text-[10px] text-gray-500 font-semibold">Key:</span>
                        <input
                          type="text"
                          placeholder="e.g. shipping_address"
                          value={cm.value || ""}
                          onChange={(e) => setNewTemplate((prev) => ({
                            ...prev,
                            variable_mappings: { ...(prev.variable_mappings || {}), [param]: { type: "event_field", value: e.target.value } }
                          }))}
                          className="w-full px-2.5 py-1.5 border border-purple-300 rounded-lg text-xs font-mono"
                        />
                      </div>
                    )}

                    {cm.type === "external_api" && isCustomApi && (
                      <div className="pl-16 flex items-center gap-1.5">
                        <span className="text-[10px] text-gray-500 font-semibold">Key:</span>
                        <input
                          type="text"
                          placeholder="e.g. tracking_code"
                          value={cm.value || ""}
                          onChange={(e) => setNewTemplate((prev) => ({
                            ...prev,
                            variable_mappings: { ...(prev.variable_mappings || {}), [param]: { type: "external_api", value: e.target.value } }
                          }))}
                          className="w-full px-2.5 py-1.5 border border-emerald-300 rounded-lg text-xs font-mono"
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
              type="submit"
              className="bg-[#25D366] hover:bg-[#1EBE5D] text-white px-5 py-2 rounded-lg font-semibold text-sm shadow-md"
            >
              Submit Template
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
