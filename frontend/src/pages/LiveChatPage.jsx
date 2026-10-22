import React, { useEffect, useRef, useState } from "react";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Star,
  MessageSquare,
  PhoneCall,
  RefreshCw,
  Clock,
  Check,
  CheckCheck,
  Send,
  Volume2,
  VolumeX,
  ArrowDown
} from "lucide-react";
import { formatToISTTime } from "../utils/dateUtils";

export default function LiveChatPage({
  chatConversations = [],
  chatMessages = [],
  selectedChatPhone,
  chatLoading,
  chatSending,
  chatReplyText,
  setChatReplyText,
  chatFilterUnreadOnly,
  setChatFilterUnreadOnly,
  chatListCollapsed,
  setChatListCollapsed,
  chatSoundEnabled,
  setChatSoundEnabled,
  playIncomingMessageSound,
  searchTerm,
  setSearchTerm,
  contacts = [],
  handleSelectConversation,
  fetchChatMessages,
  handleSendChatMessage
}) {
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const isNearBottomRef = useRef(true);
  const prevPhoneRef = useRef(selectedChatPhone);
  const prevMessagesLengthRef = useRef(chatMessages.length);
  const [showScrollBottomBtn, setShowScrollBottomBtn] = useState(false);

  const scrollToBottom = (behavior = "auto") => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior, block: "end" });
    }
    isNearBottomRef.current = true;
    setShowScrollBottomBtn(false);
  };

  const handleScroll = () => {
    const el = messagesContainerRef.current;
    if (!el) return;
    // Distance from bottom in pixels
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    // Consider within 80px as "at bottom"
    const isBottom = distanceFromBottom <= 80;
    isNearBottomRef.current = isBottom;
    setShowScrollBottomBtn(!isBottom && el.scrollHeight > el.clientHeight);
  };

  useEffect(() => {
    const isNewChat = prevPhoneRef.current !== selectedChatPhone;
    prevPhoneRef.current = selectedChatPhone;

    if (isNewChat) {
      // 1. Switched / opened conversation -> Always scroll to bottom immediately
      isNearBottomRef.current = true;
      setShowScrollBottomBtn(false);
      prevMessagesLengthRef.current = chatMessages.length;
      scrollToBottom("auto");
      return;
    }

    // 2. Same chat, background polling or new messages arrived
    const hasNewMessage = chatMessages.length > prevMessagesLengthRef.current;
    prevMessagesLengthRef.current = chatMessages.length;

    // Only auto-scroll down if user was already at the bottom
    if (isNearBottomRef.current) {
      scrollToBottom(hasNewMessage ? "smooth" : "auto");
    }
  }, [selectedChatPhone, chatMessages]);

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col flex-1 min-h-0">
      {/* Top Banner / Live Status Indicator */}
      <div className="px-6 py-2.5 bg-gradient-to-r from-emerald-50 via-gray-50 to-white border-b border-gray-200 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-[#25D366]"></span>
            </span>
            <span className="text-xs font-bold text-gray-800 uppercase tracking-wider">
              Meta Cloud Webhook Active
            </span>
          </div>
          <span className="text-xs text-gray-400">|</span>
          <span className="text-xs text-gray-600">
            Two-way synchronized live customer conversations
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              const next = !chatSoundEnabled;
              setChatSoundEnabled(next);
              if (next && playIncomingMessageSound) {
                playIncomingMessageSound(true);
              }
            }}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold border transition cursor-pointer ${
              chatSoundEnabled
                ? "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100"
                : "bg-gray-100 text-gray-500 border-gray-200 hover:bg-gray-200"
            }`}
            title={chatSoundEnabled ? "Sound notifications enabled (Click to mute)" : "Sound notifications muted (Click to unmute)"}
          >
            {chatSoundEnabled ? (
              <>
                <Volume2 className="w-3.5 h-3.5 text-emerald-600" />
                <span>Sound On</span>
              </>
            ) : (
              <>
                <VolumeX className="w-3.5 h-3.5 text-gray-400" />
                <span>Sound Off</span>
              </>
            )}
          </button>
          <div className="flex items-center gap-1.5 text-xs text-gray-500 font-mono">
            <Clock className="w-3.5 h-3.5 text-gray-400" />
            Auto-syncing every 2s
          </div>
        </div>
      </div>

      {/* 2-Column WhatsApp Web Layout */}
      <div className="flex-1 flex overflow-hidden min-h-0 relative">
        {/* ── Left Column: Conversation Sidebar (Collapsible) ── */}
        <div
          className={`${
            chatListCollapsed ? "w-0 md:w-0 border-r-0 overflow-hidden hidden" : "w-80 md:w-96 border-r border-gray-200"
          } flex flex-col bg-gray-50/60 min-h-0 transition-all duration-300 ease-in-out`}
        >
          {/* Search and Filters */}
          <div className="p-3 border-b border-gray-200 space-y-2 bg-white flex-shrink-0">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search chats..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-gray-100/70 border border-gray-200 rounded-lg text-xs focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                />
              </div>
              <button
                onClick={() => setChatListCollapsed(true)}
                className="p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition cursor-pointer"
                title="Collapse conversation list (Full screen chat)"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            </div>
            <div className="flex items-center justify-between pt-1">
              <button
                onClick={() => setChatFilterUnreadOnly(!chatFilterUnreadOnly)}
                className={`text-xs px-2.5 py-1 rounded-full font-medium transition flex items-center gap-1.5 cursor-pointer ${
                  chatFilterUnreadOnly
                    ? "bg-[#25D366] text-black font-bold shadow-xs"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                <Sparkles className="w-3 h-3" />
                Unread only ({chatConversations.filter((c) => (c.unread_count || 0) > 0).length})
              </button>
              <span className="text-[11px] text-gray-500">
                {chatConversations.length} conversation{chatConversations.length !== 1 ? "s" : ""}
              </span>
            </div>
          </div>

          {/* Conversation List */}
          <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
            {chatConversations
              .filter((conv) => {
                if (chatFilterUnreadOnly && (conv.unread_count || 0) === 0) return false;
                if (!searchTerm.trim()) return true;
                const q = searchTerm.toLowerCase();
                return (
                  (conv.customer_name && conv.customer_name.toLowerCase().includes(q)) ||
                  conv.customer_phone.includes(q) ||
                  (conv.last_message_text && conv.last_message_text.toLowerCase().includes(q))
                );
              })
              .map((conv) => {
                const isSelected = selectedChatPhone === conv.customer_phone;
                const isUnread = (conv.unread_count || 0) > 0;
                const isVip = (conv.total_orders || 0) >= 5;

                return (
                  <div
                    key={conv.customer_phone}
                    onClick={() => handleSelectConversation(conv.customer_phone)}
                    className={`p-3.5 cursor-pointer transition flex items-start gap-3 border-l-4 ${
                      isSelected
                        ? "bg-white border-l-[#25D366] shadow-xs"
                        : isUnread
                        ? "bg-emerald-50/40 border-l-emerald-500 hover:bg-emerald-50/80"
                        : "hover:bg-gray-100/70 border-l-transparent"
                    }`}
                  >
                    {/* Avatar */}
                    <div className="relative flex-shrink-0">
                      <div
                        className={`w-11 h-11 rounded-full flex items-center justify-center font-bold text-sm text-white shadow-xs ${
                          isVip
                            ? "bg-amber-500 ring-2 ring-amber-300"
                            : "bg-emerald-600"
                        }`}
                      >
                        {conv.customer_name ? conv.customer_name.charAt(0).toUpperCase() : "C"}
                      </div>
                      {isVip && (
                        <span
                          title="VIP Customer (5+ orders)"
                          className="absolute -bottom-0.5 -right-0.5 bg-amber-400 text-black rounded-full p-0.5 border border-white shadow-xs"
                        >
                          <Star className="w-2.5 h-2.5 fill-current text-amber-900" />
                        </span>
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="text-xs font-bold text-gray-900 truncate">
                          {conv.customer_name || conv.customer_phone}
                        </h4>
                        {conv.last_message_time && (
                          <span className="text-[10px] text-gray-400 whitespace-nowrap ml-1 font-mono">
                            {formatToISTTime(conv.last_message_time)}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center justify-between">
                        <p className="text-xs text-gray-500 truncate flex-1 pr-2">
                          {conv.last_sender === "AGENT" && (
                            <span className="text-emerald-600 font-semibold mr-1">You:</span>
                          )}
                          {conv.last_message_text || "No messages yet"}
                        </p>
                        {isUnread && (
                          <span className="min-w-[18px] h-[18px] px-1.5 flex items-center justify-center bg-[#25D366] text-black text-[10px] font-black rounded-full shadow-xs">
                            {conv.unread_count}
                          </span>
                        )}
                      </div>

                      {/* City & Orders Tag */}
                      <div className="flex items-center gap-1.5 mt-1.5 text-[10px] text-gray-400">
                        <span className="font-mono">{conv.customer_phone}</span>
                        {conv.customer_city && (
                          <>
                            <span>•</span>
                            <span>{conv.customer_city}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}

            {chatConversations.length === 0 && (
              <div className="p-8 text-center text-gray-400">
                <MessageSquare className="w-8 h-8 mx-auto mb-2 text-gray-300 opacity-60" />
                <p className="text-xs font-semibold">No conversations yet</p>
                <p className="text-[11px] text-gray-400 mt-1">
                  When customers reply to WhatsApp campaigns or message your business, their chats will appear here in real-time.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* ── Right Column: Selected Chat Thread & Reply Box ── */}
        {selectedChatPhone ? (
          <div className="flex-1 flex flex-col bg-[#EFEAE2]/30 min-w-0 overflow-hidden">
            {/* Active Conversation Header */}
            {(() => {
              const activeConv = chatConversations.find(
                (c) => c.customer_phone === selectedChatPhone
              );
              const matchingContact = contacts.find(
                (c) => c.phone === selectedChatPhone
              );
              return (
                <div className="px-6 py-3 bg-white border-b border-gray-200 flex items-center justify-between shadow-xs">
                  <div className="flex items-center gap-3">
                    {chatListCollapsed && (
                      <button
                        onClick={() => setChatListCollapsed(false)}
                        className="p-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition mr-1 flex items-center gap-1 text-xs font-semibold cursor-pointer"
                        title="Show conversation list"
                      >
                        <ChevronRight className="w-4 h-4" />
                        <span className="hidden sm:inline">Chats</span>
                      </button>
                    )}
                    <div className="w-10 h-10 rounded-full bg-[#25D366] text-white flex items-center justify-center font-bold text-sm">
                      {activeConv?.customer_name
                        ? activeConv.customer_name.charAt(0).toUpperCase()
                        : "C"}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-bold text-gray-900">
                          {activeConv?.customer_name || matchingContact?.name || "Customer"}
                        </h3>
                        {(matchingContact?.total_orders || activeConv?.total_orders || 0) >= 5 && (
                          <span className="px-2 py-0.5 bg-amber-100 text-amber-800 font-bold rounded text-[10px] flex items-center gap-1">
                            <Star className="w-3 h-3 fill-amber-500 text-amber-500" /> VIP
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-500">
                        <span className="font-mono">{selectedChatPhone}</span>
                        {(matchingContact?.city || activeConv?.customer_city) && (
                          <>
                            <span>•</span>
                            <span>{matchingContact?.city || activeConv?.customer_city}</span>
                          </>
                        )}
                        <span>•</span>
                        <span>
                          Orders: {matchingContact?.total_orders ?? activeConv?.total_orders ?? 0}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <a
                      href={`https://wa.me/${selectedChatPhone.replace("+", "")}`}
                      target="_blank"
                      rel="noreferrer"
                      className="px-3 py-1.5 border border-emerald-300 text-emerald-700 bg-emerald-50 rounded-lg text-xs font-semibold hover:bg-emerald-100 transition flex items-center gap-1.5"
                      title="Open in WhatsApp Web"
                    >
                      <PhoneCall className="w-3.5 h-3.5" />
                      WhatsApp Web
                    </a>
                    <button
                      onClick={() => fetchChatMessages(selectedChatPhone, false)}
                      disabled={chatLoading}
                      className="p-2 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition cursor-pointer"
                      title="Refresh messages"
                    >
                      <RefreshCw className={`w-4 h-4 ${chatLoading ? "animate-spin" : ""}`} />
                    </button>
                  </div>
                </div>
              );
            })()}

            {/* Messages Scroll Area */}
            <div className="flex-1 relative min-h-0 flex flex-col">
              <div
                ref={messagesContainerRef}
                onScroll={handleScroll}
                className="flex-1 p-6 overflow-y-auto space-y-3 bg-[#E5DDD5]/20 min-w-0"
              >
                {chatLoading && chatMessages.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-xs text-gray-400 gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
                    Loading chat history...
                  </div>
                ) : chatMessages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-center text-gray-400">
                    <MessageSquare className="w-10 h-10 text-gray-300 mb-2" />
                    <p className="text-xs font-semibold text-gray-600">No messages in this chat yet</p>
                    <p className="text-[11px] text-gray-400 max-w-xs mt-1">
                      Type a friendly reply below to start conversing with this customer on WhatsApp.
                    </p>
                  </div>
                ) : (
                  chatMessages.map((msg, index) => {
                    const isAgent = msg.sender_type === "AGENT";
                    return (
                      <div
                        key={msg.id || index}
                        className={`flex ${isAgent ? "justify-end" : "justify-start"}`}
                      >
                        <div
                          className={`max-w-[85%] md:max-w-lg break-words rounded-2xl px-4 py-2.5 shadow-xs text-sm relative ${
                            isAgent
                              ? "bg-[#D9FDD3] text-gray-900 rounded-tr-xs border border-emerald-200/60"
                              : "bg-white text-gray-900 rounded-tl-xs border border-gray-200/80"
                          }`}
                        >
                          {isAgent && msg.message_type === "template" && (
                            <div className="text-[10px] font-bold text-amber-800 bg-amber-100/90 px-2 py-0.5 rounded inline-block mb-1">
                              📢 WhatsApp Template Broadcast
                            </div>
                          )}
                          {!isAgent && (
                            <div className="text-[10px] font-bold text-emerald-700 mb-0.5">
                              Customer
                            </div>
                          )}
                          <p className="whitespace-pre-wrap leading-relaxed text-xs md:text-sm">
                            {msg.text}
                          </p>
                          <div
                            className={`flex items-center gap-1.5 justify-end mt-1 text-[10px] ${
                              isAgent ? "text-emerald-800/70" : "text-gray-400"
                            }`}
                          >
                            <span>
                              {formatToISTTime(msg.created_at)}
                            </span>
                            {isAgent && (
                              <span>
                                {msg.status === "SENDING" ? (
                                  <Clock className="w-3 h-3 text-gray-400 animate-spin" />
                                ) : msg.status === "DELIVERED" || msg.status === "READ" ? (
                                  <CheckCheck className="w-3.5 h-3.5 text-blue-500" />
                                ) : (
                                  <Check className="w-3.5 h-3.5 text-emerald-700" />
                                )}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Floating "Jump to Latest" Button when scrolled up */}
              {showScrollBottomBtn && (
                <button
                  type="button"
                  onClick={() => scrollToBottom("smooth")}
                  className="absolute bottom-3 right-5 z-10 px-3 py-1.5 bg-white/95 hover:bg-white text-emerald-800 text-xs font-semibold rounded-full shadow-md border border-emerald-200 hover:border-emerald-300 flex items-center gap-1.5 transition-all cursor-pointer backdrop-blur-xs hover:scale-105"
                  title="Scroll to latest message"
                >
                  <ArrowDown className="w-3.5 h-3.5 text-[#25D366]" />
                  <span>Jump to latest</span>
                </button>
              )}
            </div>

            {/* Quick Reply Suggestions */}
            <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 flex items-center gap-2 overflow-x-auto flex-shrink-0 min-w-0 max-w-full">
              <span className="text-[10px] font-bold uppercase text-gray-500 flex items-center gap-1 flex-shrink-0 pl-1">
                <Sparkles className="w-3 h-3 text-[#F5A623]" /> Quick replies:
              </span>
              {[
                "નમસ્તે! મનુભાઈ ગાંઠિયાવાળામાં આપનું સ્વાગત છે. હું આપની શું સહાય કરી શકું?",
                "તમારો ઓર્ડર તૈયાર છે અને ટૂંક સમયમાં ડિલિવર થશે! 🚚",
                "આજનો સ્પેશિયલ ગરમા ગરમ ગાંઠિયા અને જલેબી નો સ્ટોક ઉપલબ્ધ છે! 😋",
                "Hello! How can we help you today with your order?",
                "Special 10% discount code for you: SAVE10"
              ].map((snippet, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setChatReplyText(snippet)}
                  className="px-3 py-1 bg-white hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-300 border border-gray-200 rounded-full text-xs whitespace-nowrap text-gray-700 transition shadow-2xs font-medium cursor-pointer"
                >
                  {snippet.length > 35 ? snippet.slice(0, 35) + "..." : snippet}
                </button>
              ))}
            </div>

            {/* Chat Input Bar */}
            <form
              onSubmit={(e) => {
                isNearBottomRef.current = true;
                handleSendChatMessage(e);
                setTimeout(() => scrollToBottom("smooth"), 50);
              }}
              className="p-3 bg-white border-t border-gray-200 flex items-center gap-2.5 flex-shrink-0 min-w-0 w-full"
            >
              <input
                type="text"
                placeholder="Type a message to reply on WhatsApp..."
                value={chatReplyText}
                onChange={(e) => setChatReplyText(e.target.value)}
                disabled={chatSending}
                className="flex-1 min-w-0 px-4 py-2 bg-gray-100/80 border border-gray-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
              <button
                type="submit"
                disabled={!chatReplyText.trim() || chatSending}
                className="px-5 py-2 bg-[#25D366] hover:bg-[#1EBE5D] disabled:opacity-50 text-white rounded-xl font-bold text-sm shadow-sm transition flex items-center gap-2 flex-shrink-0 cursor-pointer"
              >
                {chatSending ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                Send
              </button>
            </form>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-gray-50/50 relative">
            {chatListCollapsed && (
              <button
                onClick={() => setChatListCollapsed(false)}
                className="absolute top-4 left-4 px-3 py-1.5 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 rounded-lg transition flex items-center gap-1.5 text-xs font-semibold shadow-xs cursor-pointer"
              >
                <ChevronRight className="w-4 h-4" />
                <span>Show Chats</span>
              </button>
            )}
            <div className="w-16 h-16 rounded-2xl bg-emerald-100 text-[#25D366] flex items-center justify-center mb-4 shadow-xs">
              <MessageSquare className="w-8 h-8" />
            </div>
            <h3 className="text-base font-bold text-gray-900">Select a Conversation</h3>
            <p className="text-xs text-gray-500 max-w-sm mt-1 leading-relaxed">
              Choose a customer from the conversation list to view their full message history and reply directly via WhatsApp Cloud API.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
