import React from "react";
import {
  Plus,
  BookOpen,
  Trash2,
  RefreshCw
} from "lucide-react";

export default function TemplatesPage({
  templates = [],
  setIsTemplateModalOpen,
  handleDeleteTemplate,
  handleSyncMetaTemplates,
  loading = false,
  templateFilterLang = "ALL",
  setTemplateFilterLang,
  templatePage = 1,
  setTemplatePage,
  setEditMappingTemplate,
  setEditMappings
}) {

  return (
            <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-wrap gap-4">
                <div>
                  <h3 className="font-bold text-gray-900 text-base">WhatsApp Approved Template Catalog</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {templates.length > 0
                      ? `${templates.length} official template(s) synced with Meta WhatsApp Business Manager`
                      : "No templates registered in database"}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setIsTemplateModalOpen(true)}
                    className="flex items-center gap-1.5 bg-gray-100 hover:bg-gray-200 text-gray-800 border border-gray-300 px-3.5 py-1.5 rounded-lg text-xs font-bold shadow-xs transition"
                  >
                    <Plus className="w-3.5 h-3.5 text-gray-600" />
                    Create Template
                  </button>
                  <button
                    onClick={handleSyncMetaTemplates}
                    disabled={loading}
                    className="flex items-center gap-1.5 bg-gray-100 hover:bg-gray-200 text-gray-800 border border-gray-300 px-3.5 py-1.5 rounded-lg text-xs font-bold shadow-xs transition"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 text-gray-600 ${loading ? "animate-spin" : ""}`} />
                    Sync from Meta
                  </button>

                  {/* Language Filter */}
                  {templates.length > 0 && (
                    <div className="flex items-center gap-1.5 border-l border-gray-200 pl-3">
                      {["ALL", "en", "en_US", "gu", "hi"].map((lang) => {
                        const count = lang === "ALL" ? templates.length : templates.filter(t => t.language === lang).length;
                        if (lang !== "ALL" && count === 0) return null;
                        return (
                          <button
                            key={lang}
                            onClick={() => {
                              setTemplateFilterLang(lang);
                              setTemplatePage(1);
                            }}
                            className={`px-2.5 py-1 rounded-lg text-xs font-bold uppercase transition ${
                              templateFilterLang === lang
                                ? "bg-[#111827] text-[#F5A623]"
                                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                            }`}
                          >
                            {lang === "ALL" ? `All (${templates.length})` : lang}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {templates.length === 0 ? (
                <div className="py-16 text-center text-gray-400 space-y-3">
                  <BookOpen className="w-10 h-10 mx-auto text-gray-300 stroke-1" />
                  <p className="font-medium text-sm text-gray-600">No WhatsApp templates loaded yet</p>
                  <p className="text-xs text-gray-400 max-w-sm mx-auto">
                    Click the button below to fetch all approved templates directly from your WhatsApp Business Account.
                  </p>
                  <button
                    onClick={handleSyncMetaTemplates}
                    disabled={loading}
                    className="mt-2 inline-flex items-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-4 py-2 rounded-lg text-xs font-bold shadow-md transition"
                  >
                    <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                    Sync Templates from Meta Now
                  </button>
                </div>
              ) : (() => {
                const templatesPerPage = 10;
                const filteredTemplates = templates.filter(
                  (t) => templateFilterLang === "ALL" || t.language === templateFilterLang
                );
                const totalTemplatePages = Math.ceil(filteredTemplates.length / templatesPerPage) || 1;
                const currentTemplatePage = Math.min(templatePage, totalTemplatePages);
                const paginatedTemplates = filteredTemplates.slice(
                  (currentTemplatePage - 1) * templatesPerPage,
                  currentTemplatePage * templatesPerPage
                );

                return (
                  <>
                    <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                      {paginatedTemplates.map((t) => (
                        <div key={t.id}
                          className="border border-gray-200 rounded-xl p-4.5 bg-gray-50/50 flex flex-col justify-between hover:border-gray-300 transition"
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#111827] text-white uppercase tracking-wider">
                                {t.language}
                              </span>
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                                t.status === "APPROVED"
                                  ? "bg-green-50 text-emerald-700 border-green-200"
                                  : t.status === "REJECTED"
                                  ? "bg-red-50 text-red-700 border-red-200"
                                  : "bg-amber-50 text-amber-700 border-amber-200"
                              }`}>
                                {t.status}
                              </span>
                              {t.variable_mappings && Object.keys(t.variable_mappings).length > 0 ? (
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                  ✓ Mapped
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                                  ⚠ No Mapping
                                </span>
                              )}
                            </div>
                            <h4 className="font-bold text-sm text-gray-900 mt-2.5 font-mono">{t.template_name}</h4>
                            <p className="text-xs font-semibold text-[#D35400] mt-0.5">{t.header_text}</p>
                            <p className="text-xs text-gray-700 mt-3 bg-white p-3 rounded-lg border border-gray-200 leading-relaxed font-sans">
                              {t.body_text}
                            </p>
                            {/* Mapping Pills */}
                            {t.variable_mappings && Object.keys(t.variable_mappings).length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {Object.entries(t.variable_mappings).map(([idx, m]) => {
                                  const isApi = m.type === "external_api";
                                  const isEvent = m.type === "event_field";
                                  const pillStyle = isApi
                                    ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                    : isEvent
                                    ? "bg-purple-50 text-purple-800 border-purple-200"
                                    : "bg-blue-50 text-blue-700 border-blue-200";

                                  const displayVal = m.type === "contact_field"
                                    ? m.value
                                    : m.type === "static"
                                    ? `"${m.value}"`
                                    : isEvent
                                    ? `event.${m.value}`
                                    : isApi
                                    ? `api.${m.value}`
                                    : `${m.type}.${m.value}`;

                                  return (
                                    <span key={idx} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-semibold ${pillStyle}`}>
                                      <span className="font-mono font-bold">{`{{${idx}}}`}</span>
                                      <span className="opacity-60">→</span>
                                      <span>{displayVal}</span>
                                    </span>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                          <div className="mt-3 pt-2.5 border-t border-gray-200 flex items-center justify-between text-[11px] text-gray-400">
                            <span>Category: {t.category}</span>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-gray-500">{t.footer_text}</span>
                              <button
                                onClick={() => {
                                  setEditMappingTemplate(t);
                                  setEditMappings(t.variable_mappings || {});
                                }}
                                className="text-xs text-blue-600 hover:text-blue-800 font-semibold hover:underline flex items-center gap-1 transition"
                                title="Configure column mappings for this template"
                              >
                                🗂 Columns
                              </button>
                              <button
                                onClick={() => handleDeleteTemplate(t.id, t.template_name)}
                                className="text-xs text-red-500 hover:text-red-700 font-semibold hover:underline flex items-center gap-1 transition"
                                title={`Delete ${t.template_name}`}
                              >
                                <Trash2 className="w-3 h-3" /> Delete
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Pagination Controls */}
                    {totalTemplatePages > 1 && (
                      <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between bg-white flex-wrap gap-3">
                        <span className="text-xs text-gray-500">
                          Showing {(currentTemplatePage - 1) * templatesPerPage + 1} to{" "}
                          {Math.min(currentTemplatePage * templatesPerPage, filteredTemplates.length)} of {filteredTemplates.length} templates
                        </span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setTemplatePage((p) => Math.max(p - 1, 1))}
                            disabled={currentTemplatePage === 1}
                            className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition"
                          >
                            Previous
                          </button>
                          <div className="flex items-center gap-1">
                            {Array.from({ length: totalTemplatePages }, (_, i) => i + 1).map((num) => (
                              <button
                                key={num}
                                onClick={() => setTemplatePage(num)}
                                className={`w-7 h-7 text-xs font-bold rounded-lg transition ${
                                  currentTemplatePage === num
                                    ? "bg-[#111827] text-[#F5A623]"
                                    : "text-gray-600 hover:bg-gray-100 border border-transparent hover:border-gray-200"
                                }`}
                              >
                                {num}
                              </button>
                            ))}
                          </div>
                          <button
                            onClick={() => setTemplatePage((p) => Math.min(p + 1, totalTemplatePages))}
                            disabled={currentTemplatePage === totalTemplatePages}
                            className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition"
                          >
                            Next
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
  );
}
