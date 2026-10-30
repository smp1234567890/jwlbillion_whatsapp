import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import {
  ShoppingBag,
  Search,
  ExternalLink,
  RefreshCw,
  Tag,
  Store,
  Layers,
  ArrowUpDown,
  Filter,
  CheckCircle2,
  XCircle,
  Copy,
  Check
} from "lucide-react";

export default function ShopifyProductsPage() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedType, setSelectedType] = useState("ALL");
  const [sortBy, setSortBy] = useState("newest"); // newest, price_asc, price_desc, title
  const [storeDomain, setStoreDomain] = useState("");
  const [copiedId, setCopiedId] = useState(null);

  const fetchProducts = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      const res = await axios.get("/api/shopify/products?limit=250", {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (res.data?.status === "success") {
        setProducts(res.data.products || []);
        setStoreDomain(res.data.store_domain || "");
      } else {
        setError(res.data?.error || "Failed to fetch products from Shopify.");
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to connect to Shopify API.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, []);

  // Compute unique product types for filtering
  const productTypes = useMemo(() => {
    const set = new Set();
    products.forEach((p) => {
      if (p.product_type) set.add(p.product_type);
    });
    return ["ALL", ...Array.from(set).sort()];
  }, [products]);

  // Filtered & Sorted Products
  const filteredProducts = useMemo(() => {
    return products
      .filter((p) => {
        const matchesSearch =
          !searchTerm ||
          p.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
          p.vendor?.toLowerCase().includes(searchTerm.toLowerCase()) ||
          (p.tags && p.tags.some((t) => t.toLowerCase().includes(searchTerm.toLowerCase())));

        const matchesType =
          selectedType === "ALL" || p.product_type === selectedType;

        return matchesSearch && matchesType;
      })
      .sort((a, b) => {
        if (sortBy === "price_asc") {
          return parseFloat(a.price || 0) - parseFloat(b.price || 0);
        }
        if (sortBy === "price_desc") {
          return parseFloat(b.price || 0) - parseFloat(a.price || 0);
        }
        if (sortBy === "title") {
          return (a.title || "").localeCompare(b.title || "");
        }
        // newest
        return new Date(b.created_at || 0) - new Date(a.created_at || 0);
      });
  }, [products, searchTerm, selectedType, sortBy]);

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white flex items-center justify-center shadow-sm">
              <ShoppingBag className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-gray-900">Shopify Live Catalog</h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  Live Sync
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                Real-time products fetched directly from{" "}
                <span className="font-semibold text-gray-700">{storeDomain || "Shopify Store"}</span>.
                Zero local database storage.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchProducts}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-xl transition cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-emerald-600" : ""}`} />
            <span>Refresh Catalog</span>
          </button>
          {storeDomain && (
            <a
              href={`https://${storeDomain}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl transition shadow-xs"
            >
              <Store className="w-4 h-4" />
              <span>Visit Online Store</span>
              <ExternalLink className="w-3.5 h-3.5 ml-0.5 opacity-80" />
            </a>
          )}
        </div>
      </div>

      {/* Filters and Search Bar */}
      <div className="bg-white rounded-2xl p-4 border border-gray-100 shadow-xs flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search products by title, vendor, or tag..."
            className="w-full pl-10 pr-4 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:border-emerald-500 focus:bg-white transition"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          {/* Category Filter */}
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <Filter className="w-3.5 h-3.5" />
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="bg-gray-50 border border-gray-200 text-gray-700 rounded-lg px-2.5 py-1.5 text-xs font-medium focus:outline-none focus:border-emerald-500"
            >
              {productTypes.map((type) => (
                <option key={type} value={type}>
                  {type === "ALL" ? "All Categories" : type}
                </option>
              ))}
            </select>
          </div>

          {/* Sort By */}
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <ArrowUpDown className="w-3.5 h-3.5" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-gray-50 border border-gray-200 text-gray-700 rounded-lg px-2.5 py-1.5 text-xs font-medium focus:outline-none focus:border-emerald-500"
            >
              <option value="newest">Newest First</option>
              <option value="price_asc">Price: Low to High</option>
              <option value="price_desc">Price: High to Low</option>
              <option value="title">Alphabetical (A-Z)</option>
            </select>
          </div>

          <span className="text-xs text-gray-400 pl-2 border-l border-gray-200">
            {filteredProducts.length} items
          </span>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-sm flex items-center gap-3">
          <XCircle className="w-5 h-5 text-rose-600 shrink-0" />
          <div>
            <p className="font-semibold">Unable to load Shopify products</p>
            <p className="text-xs text-rose-700 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Loading Skeleton Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {Array.from({ length: 8 }).map((_, idx) => (
            <div key={idx} className="bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-xs animate-pulse">
              <div className="w-full h-52 bg-gray-200" />
              <div className="p-4 space-y-3">
                <div className="h-4 bg-gray-200 rounded w-3/4" />
                <div className="h-3 bg-gray-100 rounded w-1/2" />
                <div className="h-5 bg-gray-200 rounded w-1/3 pt-2" />
              </div>
            </div>
          ))}
        </div>
      ) : filteredProducts.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center shadow-xs">
          <div className="w-16 h-16 rounded-full bg-gray-100 text-gray-400 flex items-center justify-center mx-auto mb-3">
            <ShoppingBag className="w-8 h-8" />
          </div>
          <h3 className="text-base font-bold text-gray-800">No products match your criteria</h3>
          <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
            Try adjusting your search keywords or clearing the category filter.
          </p>
        </div>
      ) : (
        /* Products Grid */
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {filteredProducts.map((p) => {
            const isCopied = copiedId === p.id;
            return (
              <div
                key={p.id}
                className="group bg-white rounded-2xl border border-gray-100 hover:border-emerald-200 hover:shadow-md transition-all duration-200 overflow-hidden flex flex-col justify-between"
              >
                <div>
                  {/* Product Image */}
                  <div className="relative w-full h-56 bg-gray-50 overflow-hidden">
                    {p.image_url ? (
                      <img
                        src={p.image_url}
                        alt={p.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        loading="lazy"
                      />
                    ) : (
                      <div className="w-full h-full flex flex-col items-center justify-center text-gray-300">
                        <ShoppingBag className="w-12 h-12 stroke-[1.5]" />
                        <span className="text-[11px] mt-1 text-gray-400">No Image</span>
                      </div>
                    )}

                    {/* Badge: Category / Type */}
                    {p.product_type && (
                      <span className="absolute top-3 left-3 bg-white/90 backdrop-blur-xs text-gray-700 font-semibold text-[10px] px-2.5 py-1 rounded-full shadow-xs border border-gray-200/50">
                        {p.product_type}
                      </span>
                    )}

                    {/* Stock status indicator */}
                    <span
                      className={`absolute top-3 right-3 text-[10px] font-bold px-2 py-0.5 rounded-full shadow-xs flex items-center gap-1 ${
                        p.available
                          ? "bg-emerald-500 text-white"
                          : "bg-gray-700 text-white"
                      }`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-white"></span>
                      {p.available ? "In Stock" : "Sold Out"}
                    </span>
                  </div>

                  {/* Details */}
                  <div className="p-4">
                    <p className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider mb-1">
                      {p.vendor || "JWL Billion"}
                    </p>
                    <h3
                      className="text-sm font-bold text-gray-900 line-clamp-2 leading-snug group-hover:text-emerald-700 transition"
                      title={p.title}
                    >
                      {p.title}
                    </h3>

                    {/* Price and Compare Price */}
                    <div className="flex items-baseline gap-2 mt-2.5">
                      <span className="text-lg font-black text-gray-900">
                        ₹{parseFloat(p.price || 0).toLocaleString("en-IN")}
                      </span>
                      {p.compare_at_price && parseFloat(p.compare_at_price) > parseFloat(p.price) && (
                        <span className="text-xs text-gray-400 line-through">
                          ₹{parseFloat(p.compare_at_price).toLocaleString("en-IN")}
                        </span>
                      )}
                    </div>

                    {/* Tags preview */}
                    {p.tags && p.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-3">
                        {p.tags.slice(0, 3).map((tag, i) => (
                          <span
                            key={i}
                            className="text-[10px] bg-gray-50 text-gray-600 px-2 py-0.5 rounded-md border border-gray-100"
                          >
                            #{tag}
                          </span>
                        ))}
                        {p.tags.length > 3 && (
                          <span className="text-[10px] text-gray-400 self-center">
                            +{p.tags.length - 3}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Bottom Actions: Copy Link & Open in Store */}
                <div className="px-4 pb-4 pt-2 border-t border-gray-50 flex items-center justify-between gap-2">
                  {p.product_url && (
                    <button
                      type="button"
                      onClick={() => copyToClipboard(p.product_url, p.id)}
                      className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold text-gray-700 bg-gray-50 hover:bg-emerald-50 hover:text-emerald-700 border border-gray-200 rounded-lg transition"
                      title="Copy direct product link to paste in WhatsApp chat"
                    >
                      {isCopied ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                          <span className="text-emerald-700">Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5 text-gray-500" />
                          <span>Copy Link</span>
                        </>
                      )}
                    </button>
                  )}

                  {p.product_url && (
                    <a
                      href={p.product_url}
                      target="_blank"
                      rel="noreferrer"
                      className="p-1.5 text-gray-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg border border-gray-200 transition"
                      title="View product page on Shopify website"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
