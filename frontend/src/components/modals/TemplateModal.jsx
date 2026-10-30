import React, { useState, useEffect } from "react";
import {
  X,
  ChevronRight,
  ChevronLeft,
  Megaphone,
  Bell,
  KeyRound,
  FileText,
  Image as ImageIcon,
  Video,
  FileSpreadsheet,
  MapPin,
  Bold,
  Italic,
  Strikethrough,
  Code,
  Smile,
  Plus,
  Trash2,
  ExternalLink,
  Phone,
  Copy,
  Layers,
  ShoppingBag,
  HelpCircle,
  Smartphone,
  CheckCircle2,
  Info
} from "lucide-react";
import { TEMPLATE_FIELD_OPTIONS } from "../../constants/fieldOptions";

export default function TemplateModal({
  isOpen,
  onClose,
  newTemplate,
  setNewTemplate,
  onSubmit
}) {
  if (!isOpen) return null;

  // Wizard state: 1 = Set up template, 2 = Edit template, 3 = Review & Submit
  const [step, setStep] = useState(1);
  const [buttonDropdownOpen, setButtonDropdownOpen] = useState(false);

  // Initialize defaults if missing
  useEffect(() => {
    setNewTemplate((prev) => ({
      ...prev,
      category: prev.category || "MARKETING",
      sub_type: prev.sub_type || "DEFAULT",
      language: prev.language || "en",
      header_type: prev.header_type || "NONE",
      header_text: prev.header_text || "",
      body_text: prev.body_text || "Hello {{1}}, welcome to JWL!",
      footer_text: prev.footer_text || "",
      buttons: prev.buttons || [],
      sample_values: prev.sample_values || { body: ["Valued Customer"] },
      validity_period_minutes: prev.validity_period_minutes || null,
      auth_config: prev.auth_config || {
        delivery_method: "ZERO_TAP",
        package_name: "",
        app_signature_hash: "",
        add_security_recommendation: true,
        add_expiry_time: false
      },
      variable_type: prev.variable_type || "Number"
    }));
  }, []);

  const category = newTemplate.category || "MARKETING";
  const subType = newTemplate.sub_type || "DEFAULT";

  // Parse {{1}}, {{2}}... variables from body
  const bodyVariables = [
    ...new Set([...(newTemplate.body_text || "").matchAll(/\{\{([a-zA-Z0-9_-]+)\}\}/g)].map((m) => m[1]))
  ];

  // Helper to insert markdown or variables into body textarea
  const insertIntoBody = (textToInsert) => {
    const textarea = document.getElementById("template-body-textarea");
    if (!textarea) {
      setNewTemplate((prev) => ({ ...prev, body_text: (prev.body_text || "") + textToInsert }));
      return;
    }
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const current = newTemplate.body_text || "";
    const updated = current.substring(0, start) + textToInsert + current.substring(end);
    setNewTemplate((prev) => ({ ...prev, body_text: updated }));
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + textToInsert.length, start + textToInsert.length);
    }, 10);
  };

  const handleAddNextVariable = () => {
    const nextIndex = bodyVariables.length + 1;
    insertIntoBody(`{{${nextIndex}}}`);
  };

  // Button management
  const addButton = (type) => {
    const currentButtons = newTemplate.buttons || [];
    if (currentButtons.length >= 10) return;

    let newBtn = { type, text: "" };
    if (type === "QUICK_REPLY") {
      newBtn.text = `Option ${currentButtons.length + 1}`;
    } else if (type === "URL") {
      newBtn.text = "Visit Website";
      newBtn.url = "https://example.com";
    } else if (type === "PHONE_NUMBER") {
      newBtn.text = "Call Us";
      newBtn.phone_number = "+919876543210";
    } else if (type === "COPY_CODE") {
      newBtn.text = "Copy Offer Code";
      newBtn.example = "OFFER20";
    } else if (type === "FLOW") {
      newBtn.text = "View Flow";
      newBtn.navigate_screen = "START";
    }
    setNewTemplate((prev) => ({
      ...prev,
      buttons: [...currentButtons, newBtn]
    }));
    setButtonDropdownOpen(false);
  };

  const removeButton = (idx) => {
    setNewTemplate((prev) => ({
      ...prev,
      buttons: (prev.buttons || []).filter((_, i) => i !== idx)
    }));
  };

  const updateButton = (idx, field, val) => {
    setNewTemplate((prev) => {
      const copy = [...(prev.buttons || [])];
      copy[idx] = { ...copy[idx], [field]: val };
      return { ...prev, buttons: copy };
    });
  };

  // Replace {{1}}, {{2}} with samples in live preview
  const getRenderedPreviewBody = () => {
    let text = newTemplate.body_text || "Your template message text will appear here...";
    const samples = (newTemplate.sample_values && newTemplate.sample_values.body) || [];
    bodyVariables.forEach((v, idx) => {
      const sample = samples[idx] || (newTemplate.variable_mappings && newTemplate.variable_mappings[v]?.value) || `[${v}]`;
      text = text.replace(new RegExp(`\\{\\{${v}\\}\\}`, "g"), sample);
    });
    return text;
  };

  // Sub-type presets per category
  const getSubtypesForCategory = (cat) => {
    if (cat === "MARKETING") {
      return [
        { id: "DEFAULT", title: "Default", desc: "Send messages with media and customised buttons to engage your customers." },
        { id: "CATALOGUE", title: "Catalogue", desc: "Send messages that drive sales by connecting your product catalogue." },
        { id: "FLOWS", title: "Flows", desc: "Send a form to capture customer interests, appointment requests or run surveys." },
        { id: "ORDER_DETAILS", title: "Order details", desc: "Send messages through which customers can pay you." },
        { id: "CALLING_PERMISSION", title: "Calling permissions request", desc: "Ask customers if you can call them on WhatsApp." }
      ];
    }
    if (cat === "UTILITY") {
      return [
        { id: "DEFAULT", title: "Default", desc: "Send messages about an existing order or account." },
        { id: "FLOWS", title: "Flows", desc: "Send a form to collect feedback, send reminders or manage orders." },
        { id: "ORDER_STATUS", title: "Order status", desc: "Send messages to tell customers about the progress of their orders." },
        { id: "ORDER_DETAILS", title: "Order details", desc: "Send messages through which customers can pay you." },
        { id: "CALLING_PERMISSION", title: "Calling permissions request", desc: "Ask customers if you can call them on WhatsApp." }
      ];
    }
    if (cat === "AUTHENTICATION") {
      return [
        { id: "OTP", title: "One-time passcode", desc: "Send codes to verify a transaction or login." }
      ];
    }
    return [];
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6 z-50 animate-in fade-in duration-200">
      <div className="bg-[#F8FAFC] rounded-2xl w-full max-w-6xl shadow-2xl border border-gray-200 flex flex-col max-h-[92vh] overflow-hidden">
        
        {/* Modal Top Header */}
        <div className="px-6 py-4 bg-white border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-[#25D366] flex items-center justify-center font-black">
              <Megaphone className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 font-medium">WhatsApp Manager</span>
                <span className="text-xs text-gray-400">/</span>
                <h2 className="text-sm font-bold text-gray-900">Create Template</h2>
              </div>
              <p className="text-xs text-gray-400">Configure Meta Graph API compliant templates with live WhatsApp device preview</p>
            </div>
          </div>

          {/* Stepper Progress */}
          <div className="hidden md:flex items-center gap-4 text-xs">
            <button
              type="button"
              onClick={() => setStep(1)}
              className={`flex items-center gap-1.5 font-bold transition ${step === 1 ? "text-emerald-600" : "text-gray-400"}`}
            >
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${step === 1 ? "bg-emerald-600 text-white" : "bg-gray-200 text-gray-600"}`}>1</span>
              Set up template
            </button>
            <ChevronRight className="w-3.5 h-3.5 text-gray-300" />
            <button
              type="button"
              onClick={() => setStep(2)}
              className={`flex items-center gap-1.5 font-bold transition ${step === 2 ? "text-emerald-600" : "text-gray-400"}`}
            >
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${step === 2 ? "bg-emerald-600 text-white" : "bg-gray-200 text-gray-600"}`}>2</span>
              Edit template
            </button>
            <ChevronRight className="w-3.5 h-3.5 text-gray-300" />
            <button
              type="button"
              onClick={() => setStep(3)}
              className={`flex items-center gap-1.5 font-bold transition ${step === 3 ? "text-emerald-600" : "text-gray-400"}`}
            >
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${step === 3 ? "bg-emerald-600 text-white" : "bg-gray-200 text-gray-600"}`}>3</span>
              Submit for Review
            </button>
          </div>

          <button onClick={onClose} className="p-1 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Main Content Area (Form on Left, Live Phone on Right) */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden bg-white">
          
          {/* LEFT COLUMN: Controls & Wizard Steps (Col 7) */}
          <div className="lg:col-span-7 p-6 overflow-y-auto space-y-6 border-r border-gray-100 max-h-[calc(92vh-120px)]">
            
            {/* ═══════════════════════ STEP 1: SET UP TEMPLATE ═══════════════════════ */}
            {step === 1 && (
              <div className="space-y-6 animate-in fade-in">
                <div>
                  <h3 className="text-base font-bold text-gray-900">Set up your template</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Choose the category that best describes your message template. Then, select the type of message that you want to send.
                  </p>
                </div>

                {/* Category Tabs: Marketing | Utility | Authentication */}
                <div className="grid grid-cols-3 gap-2 p-1.5 bg-gray-100 rounded-xl">
                  {[
                    { id: "MARKETING", label: "Marketing", icon: Megaphone },
                    { id: "UTILITY", label: "Utility", icon: Bell },
                    { id: "AUTHENTICATION", label: "Authentication", icon: KeyRound }
                  ].map((tab) => {
                    const Icon = tab.icon;
                    const isSelected = category === tab.id;
                    return (
                      <button
                        key={tab.id}
                        type="button"
                        onClick={() => {
                          const newCat = tab.id;
                          const defaultSub = getSubtypesForCategory(newCat)[0]?.id || "DEFAULT";
                          setNewTemplate((prev) => ({
                            ...prev,
                            category: newCat,
                            sub_type: defaultSub,
                            header_type: newCat === "AUTHENTICATION" ? "NONE" : prev.header_type
                          }));
                        }}
                        className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-xs font-bold transition shadow-xs ${
                          isSelected
                            ? "bg-white text-gray-900 shadow-sm border border-gray-200"
                            : "text-gray-600 hover:text-gray-900"
                        }`}
                      >
                        <Icon className={`w-3.5 h-3.5 ${isSelected ? "text-emerald-600" : "text-gray-500"}`} />
                        {tab.label}
                      </button>
                    );
                  })}
                </div>

                {/* Sub-types radio cards */}
                <div className="space-y-2.5">
                  <label className="block text-xs font-bold uppercase text-gray-600">Select Template Sub-type</label>
                  {getSubtypesForCategory(category).map((st) => {
                    const isChecked = subType === st.id;
                    return (
                      <label
                        key={st.id}
                        onClick={() => setNewTemplate((prev) => ({ ...prev, sub_type: st.id }))}
                        className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition ${
                          isChecked
                            ? "border-emerald-500 bg-emerald-50/50 shadow-xs"
                            : "border-gray-200 hover:border-gray-300 bg-white"
                        }`}
                      >
                        <input
                          type="radio"
                          name="sub_type_radio"
                          checked={isChecked}
                          onChange={() => {}}
                          className="mt-0.5 text-emerald-600 focus:ring-emerald-500"
                        />
                        <div className="flex-1">
                          <p className="text-xs font-bold text-gray-900">{st.title}</p>
                          <p className="text-[11px] text-gray-500 mt-0.5">{st.desc}</p>
                        </div>
                      </label>
                    );
                  })}
                </div>

                {/* Helper notice */}
                <div className="p-3.5 bg-blue-50 border border-blue-100 rounded-xl flex items-start gap-2.5">
                  <Info className="w-4 h-4 text-blue-600 mt-0.5 shrink-0" />
                  <p className="text-[11px] text-blue-700 leading-relaxed">
                    Templates will be registered directly in Meta's Business Catalog and synchronized with JWL WhatsApp CRM. Meta review typically takes under 1 minute.
                  </p>
                </div>
              </div>
            )}

            {/* ═══════════════════════ STEP 2: EDIT TEMPLATE ═══════════════════════ */}
            {step === 2 && (
              <div className="space-y-6 animate-in fade-in">
                {/* Header Summary Pill */}
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-md bg-emerald-600 text-white flex items-center justify-center text-xs font-bold">
                      {category[0]}
                    </div>
                    <div>
                      <span className="text-xs font-bold text-gray-900">{newTemplate.template_name || "untitled_template"}</span>
                      <span className="text-[10px] text-gray-500 ml-2 font-mono">[{category} • {subType}]</span>
                    </div>
                  </div>
                  <span className="text-[10px] uppercase font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded">
                    {newTemplate.language}
                  </span>
                </div>

                {/* Name & Language */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-bold uppercase text-gray-700">Template Identifier</label>
                      <span className="text-[10px] text-gray-400 font-mono">{(newTemplate.template_name || "").length}/512</span>
                    </div>
                    <input
                      type="text"
                      placeholder="e.g. spring_collection_launch"
                      value={newTemplate.template_name || ""}
                      onChange={(e) =>
                        setNewTemplate({
                          ...newTemplate,
                          template_name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_")
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Select Language</label>
                    <select
                      value={newTemplate.language || "en"}
                      onChange={(e) => setNewTemplate({ ...newTemplate, language: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                    >
                      <option value="en">English (en)</option>
                      <option value="en_US">English (US)</option>
                      <option value="gu">ગુજરાતી (gu)</option>
                      <option value="hi">हिंदी (hi)</option>
                    </select>
                  </div>
                </div>

                {/* Variable Type selector */}
                {category !== "AUTHENTICATION" && (
                  <div className="p-3 bg-gray-50 border border-gray-200 rounded-xl flex items-center justify-between">
                    <div>
                      <p className="text-xs font-bold text-gray-800">Type of variable</p>
                      <p className="text-[11px] text-gray-500">Number ({`{{1}}`}, {`{{2}}`}) or descriptive text format</p>
                    </div>
                    <select
                      value={newTemplate.variable_type || "Number"}
                      onChange={(e) => setNewTemplate({ ...newTemplate, variable_type: e.target.value })}
                      className="px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-xs font-medium"
                    >
                      <option value="Number">Number (e.g. {"{{1}}"})</option>
                      <option value="Name">Name (e.g. {"{{name}}"})</option>
                    </select>
                  </div>
                )}

                {/* ── HEADER SECTION ── */}
                {category !== "AUTHENTICATION" && subType !== "ORDER_STATUS" && (
                  <div className="space-y-3 pt-2 border-t border-gray-200">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold uppercase text-gray-700">Header • Optional</label>
                      <div className="flex items-center gap-1">
                        {[
                          { id: "NONE", label: "None", icon: FileText },
                          { id: "TEXT", label: "Text", icon: FileText },
                          { id: "IMAGE", label: "Image", icon: ImageIcon },
                          { id: "VIDEO", label: "Video", icon: Video },
                          { id: "DOCUMENT", label: "Document", icon: FileSpreadsheet },
                          { id: "LOCATION", label: "Location", icon: MapPin }
                        ].map((fmt) => {
                          const Icon = fmt.icon;
                          const isSel = (newTemplate.header_type || "NONE") === fmt.id;
                          return (
                            <button
                              key={fmt.id}
                              type="button"
                              onClick={() => setNewTemplate({ ...newTemplate, header_type: fmt.id })}
                              className={`px-2 py-1 rounded text-[11px] font-bold flex items-center gap-1 transition ${
                                isSel ? "bg-emerald-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                              }`}
                            >
                              <Icon className="w-3 h-3" />
                              {fmt.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {newTemplate.header_type === "TEXT" && (
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[11px] text-gray-500">Header line</span>
                          <span className="text-[10px] text-gray-400 font-mono">{(newTemplate.header_text || "").length}/60</span>
                        </div>
                        <input
                          type="text"
                          maxLength={60}
                          placeholder="e.g. Special Festive Offer from JWL"
                          value={newTemplate.header_text || ""}
                          onChange={(e) => setNewTemplate({ ...newTemplate, header_text: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-[#25D366]"
                        />
                      </div>
                    )}

                    {["IMAGE", "VIDEO", "DOCUMENT"].includes(newTemplate.header_type) && (
                      <div className="p-4 border-2 border-dashed border-gray-300 rounded-xl bg-gray-50 text-center">
                        <ImageIcon className="w-6 h-6 text-gray-400 mx-auto mb-1" />
                        <p className="text-xs font-bold text-gray-700">Sample {newTemplate.header_type} Media Header</p>
                        <p className="text-[11px] text-gray-400 mt-0.5">Media will be sent dynamically when campaign or chat message triggers.</p>
                      </div>
                    )}
                  </div>
                )}

                {/* ── BODY SECTION ── */}
                <div className="space-y-2 pt-2 border-t border-gray-200">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold uppercase text-gray-700">
                      Message Body <span className="text-red-500">*</span>
                    </label>
                    <span className="text-[10px] text-gray-400 font-mono">{(newTemplate.body_text || "").length}/1024</span>
                  </div>

                  {/* Formatting Toolbar */}
                  <div className="flex items-center justify-between p-1.5 bg-gray-50 border border-gray-200 rounded-lg">
                    <div className="flex items-center gap-1 text-gray-600">
                      <button
                        type="button"
                        onClick={() => insertIntoBody("*bold*")}
                        title="Bold (*text*)"
                        className="p-1 rounded hover:bg-gray-200 text-xs font-bold"
                      >
                        <Bold className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => insertIntoBody("_italic_")}
                        title="Italic (_text_)"
                        className="p-1 rounded hover:bg-gray-200 text-xs"
                      >
                        <Italic className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => insertIntoBody("~strike~")}
                        title="Strikethrough (~text~)"
                        className="p-1 rounded hover:bg-gray-200 text-xs"
                      >
                        <Strikethrough className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => insertIntoBody("```code```")}
                        title="Monospace"
                        className="p-1 rounded hover:bg-gray-200 text-xs"
                      >
                        <Code className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={handleAddNextVariable}
                      className="flex items-center gap-1 bg-white hover:bg-gray-100 text-emerald-700 border border-emerald-300 px-2.5 py-1 rounded-md text-[11px] font-bold shadow-2xs"
                    >
                      <Plus className="w-3 h-3 text-emerald-600" />
                      Add variable ({`{{${bodyVariables.length + 1}}}`})
                    </button>
                  </div>

                  <textarea
                    id="template-body-textarea"
                    rows={5}
                    required
                    maxLength={1024}
                    placeholder="Hello {{1}}, explore our exclusive jewelry catalog with code {{2}}!"
                    value={newTemplate.body_text || ""}
                    onChange={(e) => setNewTemplate({ ...newTemplate, body_text: e.target.value })}
                    className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-[#25D366] font-sans leading-relaxed"
                  />
                </div>

                {/* ── FOOTER SECTION ── */}
                {category !== "AUTHENTICATION" && (
                  <div className="space-y-1.5 pt-2 border-t border-gray-200">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold uppercase text-gray-700">Footer Text • Optional</label>
                      <span className="text-[10px] text-gray-400 font-mono">{(newTemplate.footer_text || "").length}/60</span>
                    </div>
                    <input
                      type="text"
                      maxLength={60}
                      placeholder="e.g. Reply STOP to opt out • JWL Jewels"
                      value={newTemplate.footer_text || ""}
                      onChange={(e) => setNewTemplate({ ...newTemplate, footer_text: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-[#25D366]"
                    />
                  </div>
                )}

                {/* ── INTERACTIVE BUTTONS SECTION ── */}
                <div className="space-y-3 pt-2 border-t border-gray-200">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="text-xs font-bold uppercase text-gray-700">Buttons • Optional</label>
                      <p className="text-[10px] text-gray-400">Add up to 10 buttons (Quick Replies, URL, Calls, Flows)</p>
                    </div>

                    {/* Add button dropdown */}
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setButtonDropdownOpen(!buttonDropdownOpen)}
                        disabled={(newTemplate.buttons || []).length >= 10}
                        className="flex items-center gap-1.5 bg-gray-100 hover:bg-gray-200 border border-gray-300 text-gray-800 px-3 py-1.5 rounded-lg text-xs font-bold shadow-2xs transition disabled:opacity-50"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        Add Button
                      </button>

                      {buttonDropdownOpen && (
                        <div className="absolute right-0 mt-1 w-52 bg-white rounded-xl shadow-xl border border-gray-200 py-1.5 z-20 animate-in fade-in">
                          <button
                            type="button"
                            onClick={() => addButton("QUICK_REPLY")}
                            className="w-full text-left px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                          >
                            <Layers className="w-3.5 h-3.5 text-gray-500" />
                            Custom (Quick Reply)
                          </button>
                          <button
                            type="button"
                            onClick={() => addButton("URL")}
                            className="w-full text-left px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                          >
                            <ExternalLink className="w-3.5 h-3.5 text-blue-500" />
                            Visit website
                          </button>
                          <button
                            type="button"
                            onClick={() => addButton("PHONE_NUMBER")}
                            className="w-full text-left px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                          >
                            <Phone className="w-3.5 h-3.5 text-emerald-500" />
                            Call phone number
                          </button>
                          <button
                            type="button"
                            onClick={() => addButton("COPY_CODE")}
                            className="w-full text-left px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                          >
                            <Copy className="w-3.5 h-3.5 text-amber-500" />
                            Copy offer code
                          </button>
                          <button
                            type="button"
                            onClick={() => addButton("FLOW")}
                            className="w-full text-left px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                          >
                            <FileText className="w-3.5 h-3.5 text-purple-500" />
                            Complete flow
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Button list */}
                  {(newTemplate.buttons || []).map((btn, idx) => (
                    <div key={idx} className="p-3 bg-gray-50 border border-gray-200 rounded-xl space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500 bg-white px-2 py-0.5 rounded border border-gray-200">
                          Button #{idx + 1} • {btn.type}
                        </span>
                        <button
                          type="button"
                          onClick={() => removeButton(idx)}
                          className="text-red-500 hover:text-red-700 text-xs p-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <input
                          type="text"
                          maxLength={25}
                          placeholder="Button label (e.g. Shop Now)"
                          value={btn.text || ""}
                          onChange={(e) => updateButton(idx, "text", e.target.value)}
                          className="px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs bg-white"
                        />
                        {btn.type === "URL" && (
                          <input
                            type="url"
                            placeholder="https://example.com/item"
                            value={btn.url || ""}
                            onChange={(e) => updateButton(idx, "url", e.target.value)}
                            className="px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs bg-white"
                          />
                        )}
                        {btn.type === "PHONE_NUMBER" && (
                          <input
                            type="tel"
                            placeholder="+919876543210"
                            value={btn.phone_number || ""}
                            onChange={(e) => updateButton(idx, "phone_number", e.target.value)}
                            className="px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs bg-white"
                          />
                        )}
                        {btn.type === "COPY_CODE" && (
                          <input
                            type="text"
                            placeholder="Discount code (e.g. SAVE20)"
                            value={btn.example || ""}
                            onChange={(e) => updateButton(idx, "example", e.target.value)}
                            className="px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs bg-white"
                          />
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* ── MESSAGE VALIDITY PERIOD (Utility / Auth) ── */}
                {["UTILITY", "AUTHENTICATION"].includes(category) && (
                  <div className="p-3.5 bg-gray-50 border border-gray-200 rounded-xl space-y-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs font-bold text-gray-800">Message validity period</p>
                        <p className="text-[11px] text-gray-500">Custom expiration time for delivery</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={Boolean(newTemplate.validity_period_minutes)}
                        onChange={(e) =>
                          setNewTemplate({
                            ...newTemplate,
                            validity_period_minutes: e.target.checked ? 10 : null
                          })
                        }
                        className="rounded text-emerald-600 focus:ring-emerald-500 w-4 h-4"
                      />
                    </div>
                    {Boolean(newTemplate.validity_period_minutes) && (
                      <div className="flex items-center gap-2 pt-2">
                        <span className="text-xs text-gray-600">Validity:</span>
                        <select
                          value={newTemplate.validity_period_minutes || 10}
                          onChange={(e) =>
                            setNewTemplate({ ...newTemplate, validity_period_minutes: parseInt(e.target.value) })
                          }
                          className="px-2.5 py-1 bg-white border border-gray-300 rounded-md text-xs font-bold"
                        >
                          <option value={10}>10 minutes (Standard)</option>
                          <option value={30}>30 minutes</option>
                          <option value={60}>1 hour</option>
                          <option value={1440}>24 hours</option>
                        </select>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ═══════════════════════ STEP 3: REVIEW & VARIABLE MAPPING ═══════════════════════ */}
            {step === 3 && (
              <div className="space-y-6 animate-in fade-in">
                <div>
                  <h3 className="text-base font-bold text-gray-900">Review Samples & Variable Mappings</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Meta requires sample values for every placeholder to test approval. You can also bind variables to your CRM fields.
                  </p>
                </div>

                {bodyVariables.length === 0 ? (
                  <div className="p-6 bg-gray-50 rounded-xl border border-gray-200 text-center text-gray-500 text-xs">
                    This template contains no variable placeholders ({`{{1}}`}). It is ready for direct submission!
                  </div>
                ) : (
                  <div className="space-y-3">
                    {bodyVariables.map((param, idx) => {
                      const sampleVal = (newTemplate.sample_values?.body || [])[idx] || "";
                      const cm = (newTemplate.variable_mappings || {})[param] || {};
                      const cv = cm.type ? `${cm.type}|${cm.value || ""}` : "";

                      return (
                        <div key={param} className="p-3.5 bg-gray-50 rounded-xl border border-gray-200 space-y-2.5">
                          <div className="flex items-center justify-between">
                            <span className="font-mono font-bold text-emerald-800 bg-emerald-100 px-2.5 py-1 rounded-md text-xs">
                              {`{{${param}}}`}
                            </span>
                            <span className="text-[10px] text-gray-400 uppercase font-semibold">Meta Sample & CRM Map</span>
                          </div>

                          {/* Meta review sample value */}
                          <div>
                            <label className="block text-[11px] font-bold text-gray-700 mb-1">
                              Meta Sample Text (Mandatory for Review)
                            </label>
                            <input
                              type="text"
                              placeholder={`Sample value for {{${param}}} (e.g. Ramesh)`}
                              value={sampleVal}
                              onChange={(e) => {
                                const newSamples = [...(newTemplate.sample_values?.body || [])];
                                newSamples[idx] = e.target.value;
                                setNewTemplate((prev) => ({
                                  ...prev,
                                  sample_values: { ...(prev.sample_values || {}), body: newSamples }
                                }));
                              }}
                              className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-xs bg-white focus:ring-2 focus:ring-[#25D366]"
                            />
                          </div>

                          {/* Platform CRM Auto-Mapping */}
                          <div>
                            <label className="block text-[11px] font-bold text-blue-700 mb-1">
                              Auto-Map to JWL CRM Field
                            </label>
                            <select
                              value={cv}
                              onChange={(e) => {
                                const [type, ...rest] = e.target.value.split("|");
                                const valPart = rest.join("|");
                                setNewTemplate((prev) => ({
                                  ...prev,
                                  variable_mappings: {
                                    ...(prev.variable_mappings || {}),
                                    [param]: { type, value: valPart }
                                  }
                                }));
                              }}
                              className="w-full px-3 py-1.5 border border-blue-200 rounded-lg text-xs bg-white text-gray-800 focus:ring-2 focus:ring-blue-400"
                            >
                              <option value="">— choose CRM contact field —</option>
                              {TEMPLATE_FIELD_OPTIONS.map((g) => (
                                <optgroup key={g.group} label={g.group}>
                                  {g.options.map((opt) => (
                                    <option key={opt.value} value={opt.value}>
                                      {opt.label}
                                    </option>
                                  ))}
                                </optgroup>
                              ))}
                            </select>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* RIGHT COLUMN: Realistic Live WhatsApp Device Preview (Col 5) */}
          <div className="lg:col-span-5 bg-[#E5DDD5] p-6 flex flex-col justify-between items-center relative overflow-hidden border-t lg:border-t-0">
            <div className="w-full max-w-sm">
              <div className="flex items-center justify-between mb-3 text-xs text-gray-600 font-bold uppercase tracking-wider">
                <span>WhatsApp Device Preview</span>
                <span className="flex items-center gap-1 text-[11px] text-emerald-700 font-normal">
                  <span className="w-2 h-2 rounded-full bg-[#25D366] inline-block animate-pulse"></span> Live
                </span>
              </div>

              {/* Chat Bubble Container */}
              <div className="bg-white rounded-2xl shadow-lg border border-black/5 overflow-hidden text-gray-900 transition-all">
                
                {/* Header preview (Media or Text) */}
                {newTemplate.header_type === "TEXT" && newTemplate.header_text && (
                  <div className="px-4 pt-3.5 pb-1 font-bold text-sm text-gray-900 border-b border-gray-100">
                    {newTemplate.header_text}
                  </div>
                )}

                {["IMAGE", "VIDEO"].includes(newTemplate.header_type) && (
                  <div className="w-full h-36 bg-gray-200 flex flex-col items-center justify-center text-gray-500 gap-1 border-b border-gray-100">
                    <ImageIcon className="w-8 h-8 text-gray-400" />
                    <span className="text-[11px] font-semibold">[{newTemplate.header_type} Media Header]</span>
                  </div>
                )}

                {newTemplate.header_type === "DOCUMENT" && (
                  <div className="p-3 bg-gray-50 flex items-center gap-2.5 border-b border-gray-200">
                    <FileSpreadsheet className="w-6 h-6 text-red-500" />
                    <div>
                      <p className="text-xs font-bold text-gray-800">Attachment.pdf</p>
                      <p className="text-[10px] text-gray-400">PDF Document • 1.2 MB</p>
                    </div>
                  </div>
                )}

                {subType === "ORDER_STATUS" && (
                  <div className="p-2.5 bg-gray-100 border-b border-gray-200 text-xs font-mono font-bold text-gray-700">
                    Status: {"{{Order Status}}"}
                  </div>
                )}

                {/* Message Body */}
                <div className="p-4 text-xs leading-relaxed text-gray-800 whitespace-pre-wrap break-words">
                  {getRenderedPreviewBody()}
                  <div className="flex justify-end items-center gap-1 mt-2 text-[10px] text-gray-400">
                    <span>11:59 AM</span>
                    <span className="text-[#53bdeb]">✓✓</span>
                  </div>
                </div>

                {/* Message Footer */}
                {newTemplate.footer_text && (
                  <div className="px-4 pb-2 text-[10px] text-gray-400 border-t border-gray-50">
                    {newTemplate.footer_text}
                  </div>
                )}

                {/* Action Buttons Mockup */}
                {(newTemplate.buttons || []).length > 0 && (
                  <div className="border-t border-gray-100 divide-y divide-gray-100 bg-[#FAFAFA]">
                    {newTemplate.buttons.map((btn, i) => (
                      <div
                        key={i}
                        className="py-2.5 px-3 text-center text-xs font-bold text-[#00A884] flex items-center justify-center gap-1.5 hover:bg-gray-100 cursor-default"
                      >
                        {btn.type === "URL" && <ExternalLink className="w-3.5 h-3.5" />}
                        {btn.type === "PHONE_NUMBER" && <Phone className="w-3.5 h-3.5" />}
                        {btn.type === "COPY_CODE" && <Copy className="w-3.5 h-3.5" />}
                        {btn.text || "Action"}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="text-[11px] text-gray-500 text-center mt-4">
              JWL WhatsApp Business Verified Account
            </div>
          </div>
        </div>

        {/* Modal Bottom Footer / Navigation */}
        <div className="px-6 py-3.5 bg-white border-t border-gray-200 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50 transition"
          >
            Cancel
          </button>

          <div className="flex items-center gap-2">
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep(step - 1)}
                className="flex items-center gap-1 px-4 py-2 border border-gray-300 rounded-lg text-xs font-bold text-gray-700 hover:bg-gray-50 transition"
              >
                <ChevronLeft className="w-4 h-4" />
                Previous
              </button>
            )}

            {step < 3 ? (
              <button
                type="button"
                onClick={() => {
                  if (step === 1 && !newTemplate.template_name) {
                    setNewTemplate((prev) => ({ ...prev, template_name: "custom_template_" + Date.now().toString().slice(-4) }));
                  }
                  setStep(step + 1);
                }}
                className="flex items-center gap-1.5 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-5 py-2 rounded-lg text-xs font-bold shadow-md transition"
              >
                Next
                <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={onSubmit}
                className="flex items-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-6 py-2 rounded-lg text-xs font-bold shadow-md transition"
              >
                <CheckCircle2 className="w-4 h-4" />
                Submit to Meta & Save
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
