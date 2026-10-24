import React, { useState } from "react";
import {
  Upload,
  RefreshCw,
  Search,
  Filter,
  ArrowUpDown,
  Tag,
  IndianRupee,
  Clock,
  Trash2,
  ChevronLeft,
  ChevronRight,
  UserPlus,
  Calendar,
  Edit2,
  Link2,
  Copy,
  Check,
  Code2,
  ExternalLink,
  ShieldCheck,
  X
} from "lucide-react";
import { formatToISTDate } from "../utils/dateUtils";

export default function ContactsPage({
  contacts = [],
  contactsPerPage,
  setContactsPerPage,
  setContactsPage,
  contactsPage,
  searchTerm,
  setSearchTerm,
  contactFilterCity,
  setContactFilterCity,
  contactFilterTag,
  setContactFilterTag,
  contactFilterVip,
  setContactFilterVip,
  contactFilterOrders,
  setContactFilterOrders,
  contactSortField,
  setContactSortField,
  contactSortOrder,
  setContactSortOrder,
  handleDeleteContact,
  handleOpenAddContact,
  handleOpenEditContact,
  setIsCsvModalOpen
}) {
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);
  const [copiedKey, setCopiedKey] = useState("");

  const handleCopy = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(""), 2500);
  };

  return (
    <>
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-wrap gap-3">
                <div>
                  <h3 className="font-bold text-gray-900 text-base">Customer Contacts Directory</h3>
                  <p className="text-xs text-gray-500 mt-0.5">Customer list with tags, order milestones, and CSV import</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-xs text-gray-500 font-medium bg-gray-50 px-2.5 py-1 rounded-lg border border-gray-200">
                    <span>Show:</span>
                    <select
                      value={contactsPerPage}
                      onChange={(e) => {
                        setContactsPerPage(Number(e.target.value));
                        setContactsPage(1);
                      }}
                      className="bg-transparent font-bold text-gray-800 focus:outline-none cursor-pointer"
                    >
                      <option value={20}>20 / page</option>
                      <option value={50}>50 / page</option>
                      <option value={100}>100 / page</option>
                      <option value={200}>200 / page</option>
                      <option value={500}>500 / page</option>
                    </select>
                  </div>
                  <div className="relative w-56">
                    <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                    <input
                      type="text"
                      placeholder="Search phone, name, city..."
                      value={searchTerm}
                      onChange={(e) => {
                        setSearchTerm(e.target.value);
                        setContactsPage(1);
                      }}
                      className="w-full pl-9 pr-3.5 py-1.5 border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                    />
                  </div>
                  <button
                    onClick={handleOpenAddContact}
                    className="flex items-center gap-1.5 bg-gray-100 hover:bg-gray-200 text-gray-800 border border-gray-300 px-3.5 py-1.5 rounded-lg font-bold text-xs shadow-xs transition"
                  >
                    <UserPlus className="w-3.5 h-3.5 text-gray-600" />
                    Add Contact
                  </button>
                  <button
                    onClick={() => setIsCsvModalOpen(true)}
                    className="flex items-center gap-1.5 bg-gray-100 hover:bg-gray-200 text-gray-800 border border-gray-300 px-3.5 py-1.5 rounded-lg font-bold text-xs shadow-xs transition"
                  >
                    <Upload className="w-3.5 h-3.5 text-gray-600" />
                    Import CSV
                  </button>
                  <button
                    onClick={() => setIsSyncModalOpen(true)}
                    className="flex items-center gap-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-300 px-3.5 py-1.5 rounded-lg font-bold text-xs shadow-xs transition"
                    title="Get webhook endpoint link and API credentials to sync contacts from other software"
                  >
                    <Link2 className="w-3.5 h-3.5 text-emerald-600" />
                    API / Webhook Sync
                  </button>
                </div>
              </div>
              {(() => {
                // Unique cities and tags for filter dropdowns
                const uniqueCities = Array.from(new Set(contacts.map((c) => c.city).filter(Boolean))).sort();
                const uniqueTags = Array.from(
                  new Set(
                    contacts
                      .flatMap((c) => (c.tags ? c.tags.split(",").map((t) => t.trim()) : []))
                      .filter(Boolean)
                  )
                ).sort();

                const filteredContacts = contacts.filter((c) => {
                  const orders = Number(c.total_orders) || 0;
                  const matchesSearch =
                    !searchTerm ||
                    c.phone.includes(searchTerm) ||
                    (c.name && c.name.toLowerCase().includes(searchTerm.toLowerCase())) ||
                    (c.city && c.city.toLowerCase().includes(searchTerm.toLowerCase())) ||
                    (c.tags && c.tags.toLowerCase().includes(searchTerm.toLowerCase()));

                  const matchesCity = contactFilterCity === "ALL" || c.city === contactFilterCity;

                  const matchesTag =
                    contactFilterTag === "ALL" ||
                    (c.tags && c.tags.toLowerCase().includes(contactFilterTag.toLowerCase()));

                  const matchesVip =
                    contactFilterVip === "ALL" ||
                    (contactFilterVip === "SUPER_VIP" && orders >= 10) ||
                    (contactFilterVip === "VIP" && orders >= 5 && orders < 10) ||
                    (contactFilterVip === "REGULAR" && orders < 5);

                  const matchesOrders =
                    contactFilterOrders === "ALL" ||
                    (contactFilterOrders === "0" && orders === 0) ||
                    (contactFilterOrders === "1_4" && orders >= 1 && orders <= 4) ||
                    (contactFilterOrders === "5_9" && orders >= 5 && orders <= 9) ||
                    (contactFilterOrders === "10_PLUS" && orders >= 10);

                  return matchesSearch && matchesCity && matchesTag && matchesVip && matchesOrders;
                });

                // Sorting
                filteredContacts.sort((a, b) => {
                  let valA = a[contactSortField];
                  let valB = b[contactSortField];

                  if (contactSortField === "name") {
                    valA = (a.name || "").toLowerCase();
                    valB = (b.name || "").toLowerCase();
                  } else if (contactSortField === "phone") {
                    valA = a.phone || "";
                    valB = b.phone || "";
                  } else if (contactSortField === "city") {
                    valA = (a.city || "").toLowerCase();
                    valB = (b.city || "").toLowerCase();
                  } else if (contactSortField === "total_orders") {
                    valA = Number(a.total_orders) || 0;
                    valB = Number(b.total_orders) || 0;
                  } else if (contactSortField === "last_order_date") {
                    valA = a.last_order_date ? new Date(a.last_order_date).getTime() : 0;
                    valB = b.last_order_date ? new Date(b.last_order_date).getTime() : 0;
                  } else if (contactSortField === "id") {
                    valA = Number(a.id) || 0;
                    valB = Number(b.id) || 0;
                  }

                  if (valA < valB) return contactSortOrder === "asc" ? -1 : 1;
                  if (valA > valB) return contactSortOrder === "asc" ? 1 : -1;
                  return 0;
                });

                const totalContacts = filteredContacts.length;
                const totalPages = Math.max(1, Math.ceil(totalContacts / contactsPerPage));
                const currentPage = Math.min(contactsPage, totalPages);
                const startIndex = (currentPage - 1) * contactsPerPage;
                const paginatedContacts = filteredContacts.slice(startIndex, startIndex + contactsPerPage);

                const handleSort = (field) => {
                  if (contactSortField === field) {
                    setContactSortOrder(contactSortOrder === "asc" ? "desc" : "asc");
                  } else {
                    setContactSortField(field);
                    setContactSortOrder(field === "name" || field === "city" ? "asc" : "desc");
                  }
                  setContactsPage(1);
                };

                const hasActiveFilters =
                  searchTerm ||
                  contactFilterCity !== "ALL" ||
                  contactFilterTag !== "ALL" ||
                  contactFilterVip !== "ALL" ||
                  contactFilterOrders !== "ALL";

                return (
                  <>
                    {/* Filter Toolbar */}
                    <div className="bg-gray-50/70 border-b border-gray-200 px-6 py-2.5 flex items-center justify-between flex-wrap gap-2.5 text-xs">
                      <div className="flex items-center gap-2 flex-wrap">
                        <div className="flex items-center gap-1 font-semibold text-gray-700 mr-1">
                          <Filter className="w-3.5 h-3.5 text-gray-500" />
                          <span>Filters:</span>
                        </div>

                        {/* City Filter */}
                        <select
                          value={contactFilterCity}
                          onChange={(e) => {
                            setContactFilterCity(e.target.value);
                            setContactsPage(1);
                          }}
                          className="bg-white border border-gray-200 rounded-lg px-2.5 py-1 text-xs text-gray-700 font-medium focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                        >
                          <option value="ALL">All Cities ({uniqueCities.length})</option>
                          {uniqueCities.map((city) => (
                            <option key={city} value={city}>{city}</option>
                          ))}
                        </select>

                        {/* Tag Filter */}
                        <select
                          value={contactFilterTag}
                          onChange={(e) => {
                            setContactFilterTag(e.target.value);
                            setContactsPage(1);
                          }}
                          className="bg-white border border-gray-200 rounded-lg px-2.5 py-1 text-xs text-gray-700 font-medium focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                        >
                          <option value="ALL">All Tags ({uniqueTags.length})</option>
                          {uniqueTags.map((tag) => (
                            <option key={tag} value={tag}>{tag}</option>
                          ))}
                        </select>

                        {/* VIP Status Filter */}
                        <select
                          value={contactFilterVip}
                          onChange={(e) => {
                            setContactFilterVip(e.target.value);
                            setContactsPage(1);
                          }}
                          className="bg-white border border-gray-200 rounded-lg px-2.5 py-1 text-xs text-gray-700 font-medium focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                        >
                          <option value="ALL">All VIP Tiers</option>
                          <option value="SUPER_VIP">⭐ Super VIP (10+ Orders)</option>
                          <option value="VIP">🌟 VIP Buyer (5-9 Orders)</option>
                          <option value="REGULAR">Regular (&lt; 5 Orders)</option>
                        </select>

                        {/* Order Volume Filter */}
                        <select
                          value={contactFilterOrders}
                          onChange={(e) => {
                            setContactFilterOrders(e.target.value);
                            setContactsPage(1);
                          }}
                          className="bg-white border border-gray-200 rounded-lg px-2.5 py-1 text-xs text-gray-700 font-medium focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                        >
                          <option value="ALL">All Order Counts</option>
                          <option value="0">0 Orders (New Lead)</option>
                          <option value="1_4">1 - 4 Orders</option>
                          <option value="5_9">5 - 9 Orders</option>
                          <option value="10_PLUS">10+ Orders</option>
                        </select>

                        {hasActiveFilters && (
                          <button
                            onClick={() => {
                              setSearchTerm("");
                              setContactFilterCity("ALL");
                              setContactFilterTag("ALL");
                              setContactFilterVip("ALL");
                              setContactFilterOrders("ALL");
                              setContactsPage(1);
                            }}
                            className="text-xs text-red-600 hover:text-red-700 font-bold ml-1 transition cursor-pointer"
                          >
                            Clear All
                          </button>
                        )}
                      </div>

                      <div className="text-[11px] text-gray-500 font-medium">
                        Found <strong className="text-gray-900">{totalContacts}</strong> match{totalContacts === 1 ? "" : "es"}
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-sm text-gray-600">
                        <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
                          <tr>
                            <th
                              onClick={() => handleSort("name")}
                              className="px-6 py-3 cursor-pointer hover:bg-gray-100/80 transition select-none"
                            >
                              <div className="flex items-center gap-1.5">
                                <span>Customer Name</span>
                                <ArrowUpDown className={`w-3 h-3 ${contactSortField === "name" ? "text-emerald-600 font-bold" : "text-gray-400"}`} />
                              </div>
                            </th>
                            <th
                              onClick={() => handleSort("phone")}
                              className="px-6 py-3 cursor-pointer hover:bg-gray-100/80 transition select-none"
                            >
                              <div className="flex items-center gap-1.5">
                                <span>Phone Number</span>
                                <ArrowUpDown className={`w-3 h-3 ${contactSortField === "phone" ? "text-emerald-600 font-bold" : "text-gray-400"}`} />
                              </div>
                            </th>
                            <th
                              onClick={() => handleSort("city")}
                              className="px-6 py-3 cursor-pointer hover:bg-gray-100/80 transition select-none"
                            >
                              <div className="flex items-center gap-1.5">
                                <span>City / Tags</span>
                                <ArrowUpDown className={`w-3 h-3 ${contactSortField === "city" ? "text-emerald-600 font-bold" : "text-gray-400"}`} />
                              </div>
                            </th>
                            <th
                              onClick={() => handleSort("total_orders")}
                              className="px-6 py-3 cursor-pointer hover:bg-gray-100/80 transition select-none"
                            >
                              <div className="flex items-center gap-1.5">
                                <span>Total Orders</span>
                                <ArrowUpDown className={`w-3 h-3 ${contactSortField === "total_orders" ? "text-emerald-600 font-bold" : "text-gray-400"}`} />
                              </div>
                            </th>
                            <th
                              onClick={() => handleSort("last_order_date")}
                              className="px-6 py-3 cursor-pointer hover:bg-gray-100/80 transition select-none"
                            >
                              <div className="flex items-center gap-1.5">
                                <span>Last Order Date</span>
                                <ArrowUpDown className={`w-3 h-3 ${contactSortField === "last_order_date" ? "text-emerald-600 font-bold" : "text-gray-400"}`} />
                              </div>
                            </th>
                            <th className="px-6 py-3">VIP Status</th>
                            <th className="px-6 py-3 text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {paginatedContacts.length === 0 ? (
                            <tr>
                              <td colSpan={7} className="px-6 py-10 text-center text-gray-400 text-xs font-medium">
                                No contacts found matching the active filters or search.
                              </td>
                            </tr>
                          ) : (
                            paginatedContacts.map((c) => {
                              const orders = Number(c.total_orders) || 0;
                              return (
                                <tr key={c.id} className="hover:bg-gray-50/80 transition">
                                  <td className="px-6 py-4 font-semibold text-gray-900">
                                    {c.name || "Customer"}
                                    {c.email && <div className="text-xs text-gray-400 font-normal">{c.email}</div>}
                                  </td>
                                  <td className="px-6 py-4 font-mono font-medium text-gray-900">{c.phone}</td>
                                  <td className="px-6 py-4 text-xs text-gray-700">
                                    {c.city && <span className="font-semibold text-gray-900 block">{c.city}</span>}
                                    {c.tags ? (
                                      <span className="inline-block bg-amber-50 text-[#D35400] text-[10px] font-bold px-2 py-0.5 rounded mt-0.5 border border-amber-200">
                                        {c.tags}
                                      </span>
                                    ) : !c.city ? "—" : null}
                                    {c.custom_attributes && Object.keys(c.custom_attributes).length > 0 && (
                                      <div className="flex flex-wrap gap-1 mt-1.5">
                                        {Object.entries(c.custom_attributes).slice(0, 2).map(([k, v]) => (
                                          <span
                                            key={k}
                                            className="inline-flex items-center text-[9px] bg-blue-50 text-blue-800 border border-blue-200 px-1.5 py-0.2 rounded font-medium"
                                            title={`${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`}
                                          >
                                            {k}: {String(v).length > 10 ? String(v).slice(0, 10) + "…" : String(v)}
                                          </span>
                                        ))}
                                        {Object.keys(c.custom_attributes).length > 2 && (
                                          <span
                                            className="text-[9px] text-gray-400 font-semibold cursor-help"
                                            title={Object.entries(c.custom_attributes).map(([k, v]) => `${k}: ${String(v)}`).join("\n")}
                                          >
                                            +{Object.keys(c.custom_attributes).length - 2} more
                                          </span>
                                        )}
                                      </div>
                                    )}
                                  </td>
                                  <td className="px-6 py-4 font-bold text-gray-900">
                                    {orders}
                                    {orders >= 5 && (
                                      <span className="ml-2 text-[10px] bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded font-bold border border-purple-200">
                                        #{orders} Milestone
                                      </span>
                                    )}
                                  </td>
                                  <td className="px-6 py-4 text-xs font-medium text-gray-600 whitespace-nowrap">
                                    {c.last_order_date ? (
                                      <div>
                                        <div className="flex items-center gap-1.5">
                                          <Calendar className="w-3.5 h-3.5 text-gray-400" />
                                          <span>
                                            {formatToISTDate(c.last_order_date)}
                                          </span>
                                        </div>
                                        {c.custom_attributes?.last_order && (
                                          <div
                                            className="text-[10px] text-amber-800 font-medium mt-1 flex items-center gap-1 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 max-w-[200px] truncate cursor-help"
                                            title={`Order: #${c.custom_attributes.last_order.order_number || c.custom_attributes.last_order.order_id}\nTotal: ${c.custom_attributes.last_order.currency || 'INR'} ${c.custom_attributes.last_order.total_price}\nItems:\n${(c.custom_attributes.last_order.items || []).map(i => `• ${i.quantity}x ${i.title} (₹${i.price})`).join('\n') || c.custom_attributes.last_order.items_summary}`}
                                          >
                                            <span className="font-bold text-amber-900 shrink-0">Items:</span>
                                            <span className="truncate">{c.custom_attributes.last_order.items_summary}</span>
                                          </div>
                                        )}
                                      </div>
                                    ) : (
                                      <span className="text-gray-400">—</span>
                                    )}
                                  </td>
                                  <td className="px-6 py-4">
                                    {orders >= 10 ? (
                                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300">
                                        ⭐ Super VIP
                                      </span>
                                    ) : orders >= 5 ? (
                                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-50 text-purple-700 border border-purple-200">
                                        🌟 VIP Buyer
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                                        Regular
                                      </span>
                                    )}
                                  </td>
                                  <td className="px-6 py-4 text-right">
                                    <div className="flex items-center justify-end gap-2">
                                      <button
                                        onClick={() => handleOpenEditContact(c)}
                                        className="p-1.5 text-gray-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition"
                                        title="Edit Contact"
                                      >
                                        <Edit2 className="w-4 h-4" />
                                      </button>
                                      <button
                                        onClick={() => handleDeleteContact(c)}
                                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                                        title="Delete Contact"
                                      >
                                        <Trash2 className="w-4 h-4" />
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              );
                            })
                          )}
                        </tbody>
                      </table>
                    </div>

                    {/* Pagination Bar */}
                    <div className="px-6 py-3.5 bg-gray-50 border-t border-gray-200 flex items-center justify-between flex-wrap gap-3">
                      <div className="text-xs text-gray-500 font-medium">
                        Showing <strong className="text-gray-900">{totalContacts === 0 ? 0 : startIndex + 1}</strong> to{" "}
                        <strong className="text-gray-900">{Math.min(startIndex + contactsPerPage, totalContacts)}</strong> of{" "}
                        <strong className="text-gray-900">{totalContacts}</strong> contacts
                        {hasActiveFilters && <span className="ml-1 text-amber-600 font-semibold">(filtered)</span>}
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setContactsPage((prev) => Math.max(1, prev - 1))}
                          disabled={currentPage <= 1}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700 hover:bg-gray-100 disabled:opacity-40 disabled:hover:bg-white transition cursor-pointer disabled:cursor-not-allowed"
                        >
                          <ChevronLeft className="w-3.5 h-3.5" />
                          Prev
                        </button>

                        <div className="text-xs font-semibold text-gray-700 px-2">
                          Page <span className="font-bold text-gray-900">{currentPage}</span> of{" "}
                          <span className="font-bold text-gray-900">{totalPages}</span>
                        </div>

                        <button
                          onClick={() => setContactsPage((prev) => Math.min(totalPages, prev + 1))}
                          disabled={currentPage >= totalPages}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700 hover:bg-gray-100 disabled:opacity-40 disabled:hover:bg-white transition cursor-pointer disabled:cursor-not-allowed"
                        >
                          Next
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </>
                );
              })()}
            </div>

            {/* Inbound Customer Sync Webhook & API Modal */}
            {isSyncModalOpen && (
              <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50 overflow-y-auto">
                <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl border border-gray-200 my-8">
                  <div className="flex items-start justify-between pb-4 border-b border-gray-100">
                    <div className="flex items-center gap-2.5">
                      <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
                        <Link2 className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-bold text-base text-gray-900">Inbound Customer Sync API & Webhook</h3>
                          <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded-full">Live</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">
                          Connect other software (Shopify, WooCommerce, ERP, CRM, POS) to auto-sync contacts in real time
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => setIsSyncModalOpen(false)}
                      className="text-gray-400 hover:text-gray-600 font-bold p-1 rounded-lg hover:bg-gray-100 transition"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>

                  <div className="mt-4 space-y-4 text-xs">
                    {/* Overview Banner */}
                    <div className="p-3 bg-emerald-50/60 rounded-xl border border-emerald-200 text-emerald-900 leading-relaxed">
                      <strong>How it works:</strong> Provide this endpoint link and API Key to your external platform. Whenever a new customer is registered or an order is placed, it will automatically export the customer to your WhatsApp contact directory. All custom columns and attributes are dynamically preserved!
                    </div>

                    {/* Endpoint 1: Webhook */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="font-bold text-gray-800 flex items-center gap-1.5">
                          <span className="px-1.5 py-0.5 bg-purple-100 text-purple-800 rounded text-[10px] font-mono">POST</span>
                          Webhook URL (Recommended for E-com & Form builders)
                        </label>
                        <button
                          onClick={() => handleCopy("https://jwl-whatsapp-crm.onrender.com/api/webhooks/customer-created", "webhook_url")}
                          className="flex items-center gap-1 text-[11px] text-emerald-600 hover:text-emerald-700 font-bold"
                        >
                          {copiedKey === "webhook_url" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                          {copiedKey === "webhook_url" ? "Copied URL!" : "Copy URL"}
                        </button>
                      </div>
                      <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-200 font-mono text-[11px] text-gray-800 break-all select-all">
                        https://jwl-whatsapp-crm.onrender.com/api/webhooks/customer-created
                      </div>
                    </div>

                    {/* Authentication */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <label className="font-bold text-gray-800 flex items-center gap-1">
                            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                            Header Authentication
                          </label>
                          <button
                            onClick={() => handleCopy("crm_webhook_secret_key_987654", "secret_header")}
                            className="flex items-center gap-1 text-[11px] text-emerald-600 hover:text-emerald-700 font-bold"
                          >
                            {copiedKey === "secret_header" ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                            {copiedKey === "secret_header" ? "Copied!" : "Copy"}
                          </button>
                        </div>
                        <div className="p-2 bg-gray-50 rounded-lg border border-gray-200 font-mono text-[11px] text-gray-700 truncate">
                          X-API-Key: crm_webhook_secret_key_987654
                        </div>
                      </div>

                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <label className="font-bold text-gray-800 flex items-center gap-1">
                            <ExternalLink className="w-3.5 h-3.5 text-blue-600" />
                            Query Param (if headers unsupported)
                          </label>
                          <button
                            onClick={() => handleCopy("?api_key=crm_webhook_secret_key_987654", "query_key")}
                            className="flex items-center gap-1 text-[11px] text-emerald-600 hover:text-emerald-700 font-bold"
                          >
                            {copiedKey === "query_key" ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                            {copiedKey === "query_key" ? "Copied!" : "Copy"}
                          </button>
                        </div>
                        <div className="p-2 bg-gray-50 rounded-lg border border-gray-200 font-mono text-[11px] text-gray-700 truncate">
                          ?api_key=crm_webhook_secret_key_987654
                        </div>
                      </div>
                    </div>

                    {/* Sample JSON payload with Custom Columns */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="font-bold text-gray-800 flex items-center gap-1.5">
                          <Code2 className="w-3.5 h-3.5 text-indigo-600" />
                          Payload JSON (Standard fields + Any Custom Columns)
                        </label>
                        <button
                          onClick={() => handleCopy(JSON.stringify({
                            phone: "+919876543210",
                            name: "Arjun Patel",
                            email: "arjun@example.com",
                            city: "Surat",
                            tags: "Wholesale, VIP",
                            company_name: "Patel Farsan Mart",
                            gstin: "24ABCDE1234F1Z5",
                            loyalty_tier: "Gold"
                          }, null, 2), "sample_json")}
                          className="flex items-center gap-1 text-[11px] text-emerald-600 hover:text-emerald-700 font-bold"
                        >
                          {copiedKey === "sample_json" ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                          {copiedKey === "sample_json" ? "Copied JSON!" : "Copy JSON"}
                        </button>
                      </div>
                      <pre className="p-3 bg-gray-900 text-emerald-400 rounded-xl font-mono text-[11px] overflow-x-auto leading-tight">
{`{
  "phone": "+919876543210",          // Required: international or standard phone
  "name": "Arjun Patel",             // Optional: customer name
  "email": "arjun@example.com",      // Optional: customer email
  "city": "Surat",                   // Optional: city
  "tags": "Wholesale, VIP",          // Optional: tags (comma-separated or array)
  // ✨ ANY EXTRA COLUMNS ARE AUTOMATICALLY SAVED IN CUSTOM ATTRIBUTES:
  "company_name": "Patel Farsan Mart",
  "gstin": "24ABCDE1234F1Z5",
  "loyalty_tier": "Gold"
}`}
                      </pre>
                    </div>

                    {/* Ready cURL Command */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="font-bold text-gray-800">Quick Test Command (cURL)</label>
                        <button
                          onClick={() => handleCopy(`curl -X POST https://jwl-whatsapp-crm.onrender.com/api/webhooks/customer-created \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: crm_webhook_secret_key_987654" \\
  -d '{"phone": "+919876543210", "name": "Arjun Patel", "city": "Surat", "tags": "VIP", "company_name": "Patel Farsan Mart", "gstin": "24ABCDE1234F1Z5"}'`, "curl_cmd")}
                          className="flex items-center gap-1 text-[11px] text-emerald-600 hover:text-emerald-700 font-bold"
                        >
                          {copiedKey === "curl_cmd" ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                          {copiedKey === "curl_cmd" ? "Copied cURL!" : "Copy cURL"}
                        </button>
                      </div>
                      <pre className="p-2.5 bg-gray-900 text-gray-200 rounded-xl font-mono text-[10px] overflow-x-auto leading-relaxed">
{`curl -X POST https://jwl-whatsapp-crm.onrender.com/api/webhooks/customer-created \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: crm_webhook_secret_key_987654" \\
  -d '{"phone": "+919876543210", "name": "Arjun Patel", "city": "Surat", "tags": "VIP", "company_name": "Patel Farsan Mart", "gstin": "24ABCDE1234F1Z5"}'`}
                      </pre>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-gray-100 flex items-center justify-end mt-4">
                    <button
                      type="button"
                      onClick={() => setIsSyncModalOpen(false)}
                      className="px-5 py-2 bg-gray-900 hover:bg-black text-white rounded-lg text-xs font-bold transition"
                    >
                      Done
                    </button>
                  </div>
                </div>
              </div>
            )}
    </>
  );
}
