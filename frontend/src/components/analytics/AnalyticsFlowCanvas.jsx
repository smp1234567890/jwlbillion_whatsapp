import React, { useState, useMemo, useRef } from "react";
import {
  Zap,
  Clock,
  Send,
  GitBranch,
  CheckCircle2,
  ShoppingCart,
  CloudRain,
  UserPlus,
  Package,
  Tag,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Users,
  Award,
  Filter,
  ArrowRight,
  Hand
} from "lucide-react";

export default function AnalyticsFlowCanvas({
  flow,
  sessions = [],
  selectedStepId,
  onSelectStep,
  onViewContactsAtStep
}) {
  const [zoom, setZoom] = useState(0.85);
  const containerRef = useRef(null);
  const isDraggingRef = useRef(false);
  const startPosRef = useRef({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 });

  const handleMouseDown = (e) => {
    // Only pan when clicking on canvas background, not on interactive cards/buttons
    if (e.target.closest("button") || e.target.closest(".group") || e.target.closest("input")) {
      return;
    }
    isDraggingRef.current = true;
    startPosRef.current = {
      x: e.clientX,
      y: e.clientY,
      scrollLeft: containerRef.current ? containerRef.current.scrollLeft : 0,
      scrollTop: containerRef.current ? containerRef.current.scrollTop : 0
    };
  };

  const handleMouseMove = (e) => {
    if (!isDraggingRef.current || !containerRef.current) return;
    e.preventDefault();
    const dx = e.clientX - startPosRef.current.x;
    const dy = e.clientY - startPosRef.current.y;
    containerRef.current.scrollLeft = startPosRef.current.scrollLeft - dx;
    containerRef.current.scrollTop = startPosRef.current.scrollTop - dy;
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  const allNodes = flow?.nodes || [];
  const allEdges = flow?.edges || [];
  const totalEnrolled = sessions.length;

  // Calculate session counts and active contacts per node
  const { nodeCounts, activeCounts } = useMemo(() => {
    const counts = {};
    const active = {};

    sessions.forEach((s) => {
      const traversedNodes = new Set();
      (s.history || []).forEach((h) => {
        if (h.node_id) traversedNodes.add(String(h.node_id));
      });
      if (s.current_node_id) {
        traversedNodes.add(String(s.current_node_id));
        if (s.status === "ACTIVE" || s.status === "WAITING_DELAY") {
          active[String(s.current_node_id)] = (active[String(s.current_node_id)] || 0) + 1;
        }
      }
      traversedNodes.forEach((nid) => {
        counts[nid] = (counts[nid] || 0) + 1;
      });
    });

    // Root trigger node count is always total enrolled
    const root = allNodes.find((n) => n.type?.toLowerCase() === "trigger") || allNodes[0];
    if (root) {
      counts[String(root.id)] = totalEnrolled;
    }

    return { nodeCounts: counts, activeCounts: active };
  }, [sessions, allNodes, totalEnrolled]);

  // Helper to get edge target from source
  const getEdgeTarget = (sourceId, handle = null) => {
    const matched = allEdges.filter((e) => {
      if (String(e.source) !== String(sourceId)) return false;
      if (handle) {
        return String(e.sourceHandle || "").toLowerCase() === handle.toLowerCase();
      }
      return true;
    });
    return matched.length > 0 ? matched[0].target : null;
  };

  // Node Card Renderer matching FlowchartCanvas.jsx
  const renderNodeCard = (node) => {
    const isSelected = selectedStepId === String(node.id);
    const isTrigger = node.type === "trigger";
    const isDelay = node.type === "delay";
    const isWhatsApp =
      node.type === "whatsapp_message" ||
      node.type === "action_whatsapp" ||
      node.type === "whatsapp";
    const isCondition = node.type === "condition";
    const isTag = node.type === "tag";
    const isExit = node.type === "exit" || node.type === "goal";

    const count = nodeCounts[String(node.id)] ?? 0;
    const active = activeCounts[String(node.id)] ?? 0;
    const pct = totalEnrolled > 0 ? Math.round((count / totalEnrolled) * 100) : 0;

    // Condition Cards - Purple Gradient Card
    if (isCondition) {
      const conditionType = node.data?.condition_type || "ORDER_PLACED";
      let defaultConditionLabel = "Did Customer Purchase?";
      let defaultConditionDesc = "Checks if order was placed";

      if (conditionType === "MESSAGE_READ") {
        defaultConditionLabel = "Was Message Read?";
        defaultConditionDesc = "Checks blue tick status";
      } else if (conditionType === "CART_VALUE_ABOVE") {
        defaultConditionLabel = `Cart Value > ₹${node.data?.threshold || 500}`;
        defaultConditionDesc = "Evaluates total cart value";
      }

      const isGenericTitle =
        !node.label ||
        node.label === "Did Customer Purchase?" ||
        node.label === "Was Message Read?" ||
        node.label?.startsWith("Cart Value > ₹") ||
        node.label === "Check Condition";

      const displayTitle = isGenericTitle ? defaultConditionLabel : node.label;
      const isGenericDesc =
        !node.data?.description ||
        node.data.description === "Checks if order was placed" ||
        node.data.description === "Checks blue tick status" ||
        node.data.description === "Evaluates total cart value";
      const displayDesc = isGenericDesc ? defaultConditionDesc : node.data?.description;

      return (
        <div
          key={node.id}
          onClick={() => onSelectStep?.(isSelected ? null : String(node.id))}
          className={`group relative w-72 rounded-2xl transition-all cursor-pointer shadow-md hover:shadow-lg hover:-translate-y-0.5 bg-gradient-to-r from-[#5B42D6] via-[#654BE2] to-[#7952E8] text-white p-3.5 border ${
            isSelected
              ? "border-white ring-4 ring-purple-300"
              : "border-purple-400/40 hover:border-purple-300"
          }`}
        >
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-white/20 backdrop-blur-xs flex items-center justify-center font-bold text-white text-base shadow-xs shrink-0">
              ?
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="font-bold text-white text-xs truncate leading-snug">
                {displayTitle}
              </h4>
              {displayDesc && (
                <p className="text-[10px] text-purple-200 truncate mt-0.5 font-medium">
                  {displayDesc}
                </p>
              )}
            </div>
          </div>

          {/* Analytics Stats Badge */}
          <div className="mt-2.5 pt-2 border-t border-white/20 flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-1.5 font-semibold">
              <Users className="w-3.5 h-3.5 text-purple-200" />
              <span className="font-bold text-white">{count}</span>
              <span className="text-purple-200 text-[10px]">evaluated</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="font-mono font-bold text-white bg-white/20 px-2 py-0.5 rounded-full text-[10px]">
                {pct}%
              </span>
            </div>
          </div>
        </div>
      );
    }

    // Action & Trigger Cards
    const triggerType = node.data?.trigger_type || flow?.trigger_type;
    const theme = isTrigger
      ? triggerType === "WEATHER_TRIGGER"
        ? { bg: "bg-white", border: "border-gray-200", iconBg: "bg-sky-500 text-white", tag: "WEATHER", tagColor: "text-sky-700 bg-sky-50" }
        : triggerType === "NEW_CUSTOMER_WELCOME"
        ? { bg: "bg-white", border: "border-gray-200", iconBg: "bg-emerald-600 text-white", tag: "WELCOME", tagColor: "text-emerald-700 bg-emerald-50" }
        : triggerType === "BACK_IN_STOCK"
        ? { bg: "bg-white", border: "border-gray-200", iconBg: "bg-purple-600 text-white", tag: "STOCK", tagColor: "text-purple-700 bg-purple-50" }
        : { bg: "bg-white", border: "border-gray-200", iconBg: "bg-blue-600 text-white", tag: "TRIGGER", tagColor: "text-blue-700 bg-blue-50" }
      : isDelay
      ? { bg: "bg-white", border: "border-gray-200", iconBg: "bg-amber-100 text-amber-800", tag: "DELAY", tagColor: "text-amber-800 bg-amber-50" }
      : isWhatsApp
      ? { bg: "bg-white", border: "border-gray-200", iconBg: "bg-[#25D366] text-white", tag: "WHATSAPP", tagColor: "text-emerald-800 bg-emerald-50" }
      : isTag
      ? { bg: "bg-white", border: "border-gray-200", iconBg: "bg-indigo-600 text-white", tag: "TAG CRM", tagColor: "text-indigo-800 bg-indigo-50" }
      : node.data?.outcome === "GOAL_MET" || node.label?.toLowerCase().includes("goal")
      ? { bg: "bg-white", border: "border-gray-200", iconBg: "bg-[#10B981] text-white", tag: "GOAL", tagColor: "text-emerald-800 bg-emerald-50" }
      : { bg: "bg-white", border: "border-gray-200", iconBg: "bg-gray-600 text-white", tag: "EXIT", tagColor: "text-gray-700 bg-gray-100" };

    return (
      <div
        key={node.id}
        onClick={() => onSelectStep?.(isSelected ? null : String(node.id))}
        className={`group relative w-72 bg-white rounded-2xl border transition-all cursor-pointer shadow-xs hover:shadow-md hover:-translate-y-0.5 ${
          isSelected
            ? "border-[#25D366] ring-4 ring-emerald-100 shadow-md"
            : "border-gray-200/90 hover:border-gray-300"
        }`}
      >
        <div className="p-3.5">
          <div className="flex items-center gap-3">
            {/* Leading Rounded Icon Box */}
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 shadow-xs ${theme.iconBg}`}>
              {isTrigger && (
                triggerType === "WEATHER_TRIGGER" ? <CloudRain className="w-4 h-4" /> :
                triggerType === "NEW_CUSTOMER_WELCOME" ? <UserPlus className="w-4 h-4" /> :
                triggerType === "BACK_IN_STOCK" ? <Package className="w-4 h-4" /> :
                <Zap className="w-4 h-4 fill-white" />
              )}
              {isDelay && <Clock className="w-4 h-4 text-amber-700" />}
              {isWhatsApp && <Send className="w-4 h-4" />}
              {isTag && <Tag className="w-4 h-4" />}
              {(isExit || theme.tag === "GOAL") && <CheckCircle2 className="w-4 h-4" />}
            </div>

            {/* Node Text Info */}
            <div className="flex-1 min-w-0">
              <h4 className="font-bold text-gray-900 text-xs truncate leading-snug">
                {node.label}
              </h4>
              {isTrigger && (
                <p className="text-[10px] text-blue-600 font-medium truncate mt-0.5">
                  {node.data?.min_cart_value > 0
                    ? `Min Cart: ≥ ₹${node.data.min_cart_value}`
                    : node.data?.inactive_days > 0
                    ? `Inactive: ≥ ${node.data.inactive_days} Days`
                    : node.data?.description || "Starting Trigger"}
                </p>
              )}
              {!isTrigger && node.data?.description && (
                <p className="text-[10px] text-gray-400 font-medium truncate mt-0.5">
                  {node.data.description}
                </p>
              )}
              {!isTrigger && !node.data?.description && node.data?.template_name && (
                <p className="text-[10px] text-gray-400 font-medium truncate mt-0.5">
                  {node.data.template_name}
                </p>
              )}
            </div>
          </div>

          {/* Analytics Stats Badge */}
          <div className="mt-2.5 pt-2 border-t border-gray-100 flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-1.5 text-gray-600 font-medium">
              <Users className="w-3.5 h-3.5 text-gray-400" />
              <span className="font-bold text-gray-900 font-mono text-xs">{count}</span>
              <span className="text-[10px] text-gray-400">contacts</span>
              {active > 0 && (
                <span className="ml-1 text-[9px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.2 rounded-full">
                  ⏳ {active} active
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-[10px] font-bold text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                {pct}%
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Recursive Flow Chain Renderer - Exact Same Visual Hierarchy as FlowchartCanvas
  const renderFlowChain = (startNodeId) => {
    const chainNodes = [];
    const visited = new Set();
    let curId = startNodeId;

    while (curId && !visited.has(curId)) {
      visited.add(curId);
      const n = allNodes.find((x) => String(x.id) === String(curId));
      if (!n) break;
      chainNodes.push(n);

      if (n.type === "condition") {
        break;
      }

      curId = getEdgeTarget(curId);
    }

    if (chainNodes.length === 0) return null;

    return (
      <div className="flex flex-col items-center w-max">
        {chainNodes.map((node, idx) => {
          const isLast = idx === chainNodes.length - 1;
          const isNodeCondition = node.type === "condition";

          return (
            <React.Fragment key={node.id}>
              {/* Node Card */}
              {renderNodeCard(node)}

              {/* Connector Down to Next Node */}
              {!isLast && (
                <div className="flex flex-col items-center my-1 relative">
                  <div className="w-0.5 h-6 bg-gray-300" />
                  <div className="w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent border-t-gray-400" />
                </div>
              )}

              {/* Exact Condition Tree Fork with Connected Curved Lines */}
              {isNodeCondition && (() => {
                const isReadCondition = node.data?.condition_type === "MESSAGE_READ";
                const yesLabel = isReadCondition ? "YES (Read)" : "YES";
                const noLabel = isReadCondition ? "NO (Unread)" : "NO";

                const yesTargetId = getEdgeTarget(node.id, "yes");
                const noTargetId = getEdgeTarget(node.id, "no");

                const parentCount = nodeCounts[String(node.id)] ?? 0;
                const yesCount = yesTargetId ? (nodeCounts[String(yesTargetId)] ?? 0) : 0;
                const noCount = noTargetId ? (nodeCounts[String(noTargetId)] ?? 0) : 0;

                const yesPct = parentCount > 0 ? Math.round((yesCount / parentCount) * 100) : 0;
                const noPct = parentCount > 0 ? Math.round((noCount / parentCount) * 100) : 0;

                return (
                  <div className="flex flex-col items-center w-max">
                    <div className="flex items-start justify-center px-4 pt-0">
                      {/* LEFT BRANCH: YES */}
                      <div className="flex flex-col items-center min-w-[280px]">
                        <div className="w-full flex h-8">
                          <div className="w-1/2" />
                          <div className="w-1/2 border-t-2 border-l-2 border-gray-400 rounded-tl-xl" />
                        </div>

                        <div className="flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-[#E6F4EA] text-[#137333] text-[11px] font-bold border border-[#CEEAD6] shadow-xs select-none z-10">
                          <span>{yesLabel}</span>
                          <span className="text-[9px] font-mono bg-emerald-200/80 text-emerald-900 px-1.5 py-0.2 rounded-full">
                            {yesPct}% ({yesCount})
                          </span>
                        </div>

                        <div className="w-0.5 h-4 bg-gray-400" />
                        <div className="w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent border-t-gray-500 mb-2" />

                        {yesTargetId && renderFlowChain(yesTargetId)}
                      </div>

                      {/* RIGHT BRANCH: NO */}
                      <div className="flex flex-col items-center min-w-[280px]">
                        <div className="w-full flex h-8">
                          <div className="w-1/2 border-t-2 border-r-2 border-gray-400 rounded-tr-xl" />
                          <div className="w-1/2" />
                        </div>

                        <div className="flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-[#FEF7E0] text-[#B06000] text-[11px] font-bold border border-[#FEEFC3] shadow-xs select-none z-10">
                          <span>{noLabel}</span>
                          <span className="text-[9px] font-mono bg-amber-200/80 text-amber-900 px-1.5 py-0.2 rounded-full">
                            {noPct}% ({noCount})
                          </span>
                        </div>

                        <div className="w-0.5 h-4 bg-gray-400" />
                        <div className="w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent border-t-gray-500 mb-2" />

                        {noTargetId && renderFlowChain(noTargetId)}
                      </div>
                    </div>
                  </div>
                );
              })()}
            </React.Fragment>
          );
        })}
      </div>
    );
  };

  // Find root node (trigger or node without incoming edges)
  const rootNode =
    allNodes.find((n) => n.type?.toLowerCase() === "trigger") ||
    allNodes.find((n) => !allEdges.some((e) => String(e.target) === String(n.id))) ||
    allNodes[0];

  return (
    <div className="relative flex-1 h-full w-full flex flex-col bg-[#F8FAFC] select-none overflow-hidden">
      {/* Top Floating Control Bar */}
      <div className="absolute top-4 right-6 z-20 flex items-center gap-3 bg-white/90 backdrop-blur-sm p-1.5 rounded-2xl border border-gray-200 shadow-sm">
        {selectedStepId && (
          <button
            type="button"
            onClick={() => onSelectStep?.(null)}
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-xl transition cursor-pointer"
          >
            <Filter className="w-3.5 h-3.5" />
            Clear Selected Step
          </button>
        )}

        {/* Zoom Controls */}
        <div className="flex items-center bg-gray-100 rounded-xl p-0.5 border border-gray-200 text-xs">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.3, z - 0.1))}
            className="p-1.5 hover:bg-white rounded-lg text-gray-600 transition cursor-pointer"
            title="Zoom Out"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="px-2.5 font-mono text-[11px] text-gray-600 font-semibold min-w-[42px] text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(1.5, z + 0.1))}
            className="p-1.5 hover:bg-white rounded-lg text-gray-600 transition cursor-pointer"
            title="Zoom In"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setZoom(0.85)}
            className="p-1.5 hover:bg-white rounded-lg text-gray-600 transition cursor-pointer"
            title="Reset Zoom"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Selected Step Action Banner */}
      {selectedStepId && (
        <div className="absolute top-4 left-6 z-20 flex items-center gap-2 bg-emerald-50 border border-emerald-200 px-3.5 py-2 rounded-xl shadow-xs">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-bold text-emerald-800">
            Filtered by step: {allNodes.find((n) => String(n.id) === selectedStepId)?.label || selectedStepId}
          </span>
          <span className="text-xs font-mono font-bold text-emerald-900 bg-emerald-200/70 px-2 py-0.5 rounded-full">
            {nodeCounts[selectedStepId] || 0} contacts
          </span>
          {onViewContactsAtStep && (
            <button
              type="button"
              onClick={onViewContactsAtStep}
              className="ml-2 flex items-center gap-1 text-xs font-bold text-emerald-700 hover:text-emerald-900 underline cursor-pointer"
            >
              View in Contacts Table <ArrowRight className="w-3 h-3" />
            </button>
          )}
        </div>
      )}

      {/* Canvas Workspace with Exact SVG Dot Grid Pattern */}
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className="relative flex-1 h-full w-full overflow-x-auto overflow-y-auto bg-[#F8FAFC] scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent cursor-grab active:cursor-grabbing select-none"
      >
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: "radial-gradient(#CBD5E1 1px, transparent 1px)",
            backgroundSize: "24px 24px"
          }}
        />

        {/* Canvas Scaled Content Container */}
        <div
          className="min-h-full min-w-full w-max flex flex-col items-center justify-start transition-transform origin-top mx-auto"
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "top center",
            paddingTop: "48px",
            paddingLeft: "64px",
            paddingRight: "64px",
            paddingBottom: `${Math.max(160, Math.round(500 * zoom))}px`,
            minHeight: `${Math.round(100 / Math.max(zoom, 0.3))}%`
          }}
        >
          {rootNode ? (
            renderFlowChain(rootNode.id)
          ) : (
            <div className="p-8 text-center text-gray-400 text-sm">
              No flow steps found for this automation.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
