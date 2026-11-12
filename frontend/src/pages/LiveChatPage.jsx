import React, { useEffect, useRef, useState } from "react";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Star,
  MessageSquare,
  Phone,
  PhoneCall,
  RefreshCw,
  Clock,
  Check,
  CheckCheck,
  Send,
  Volume2,
  VolumeX,
  ArrowDown,
  ShoppingBag,
  Trash2,
  Paperclip,
  Image as ImageIcon,
  FileText,
  Video,
  Music,
  X,
  Download,
  ExternalLink,
  User,
  Smile,
  ThumbsUp,
  ThumbsDown,
  LogOut,
  Mic,
  Square,
  Ban
} from "lucide-react";
import { formatToISTTime, formatToISTDateTime, formatChatDateDivider, getMessageISTDateKey } from "../utils/dateUtils";
import { getApiBaseUrl } from "../api";
import axios from "axios";
import { getStoredQuickReplies } from "../utils/quickRepliesStorage";
import ChatInputBox from "../components/ChatInputBox";

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
  handleSendChatMessage,
  handleSendChatMedia,
  handleReactToMessage,
  handleDeleteConversation,
  handleBlockContact,
  optOuts = [],
  isNativeApp = false,
  onLogout
}) {
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const isNearBottomRef = useRef(true);
  const prevPhoneRef = useRef(selectedChatPhone);
  const prevMessagesLengthRef = useRef(chatMessages.length);
  const [showScrollBottomBtn, setShowScrollBottomBtn] = useState(false);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedFileType, setSelectedFileType] = useState("document");
  const [mediaCaption, setMediaCaption] = useState("");
  const [localInputText, setLocalInputText] = useState("");
  const [serverQuickReplies, setServerQuickReplies] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [callPermStatus, setCallPermStatus] = useState(null); // null | "checking" | "granted" | "no_permission" | "requesting"
  const [callModalOpen, setCallModalOpen] = useState(false);
  const [callStatusMsg, setCallStatusMsg] = useState("");
  const [isCalling, setIsCalling] = useState(false);
  const [callDuration, setCallDuration] = useState(0);
  const [activeCallId, setActiveCallId] = useState(null);
  const peerConnectionRef = useRef(null);
  const localAudioStreamRef = useRef(null);
  const remoteAudioRef = useRef(null);
  const callTimerRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingTimerRef = useRef(null);
  const fileInputRef = useRef(null);
  const replyInputRef = useRef(null);

  // Sync external chatReplyText changes (e.g. from parent initial state)
  useEffect(() => {
    if (chatReplyText !== undefined) {
      setLocalInputText(chatReplyText);
    }
  }, [chatReplyText]);

  // Fetch customizable quick replies (instant local cache + background server sync)
  useEffect(() => {
    const local = getStoredQuickReplies();
    if (local && local.length > 0) {
      setServerQuickReplies(local);
    }
    const fetchQR = async () => {
      try {
        const token = localStorage.getItem("token");
        const res = await axios.get("/api/quick-replies", {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
        if (Array.isArray(res.data) && res.data.length > 0) {
          setServerQuickReplies(res.data);
        }
      } catch (e) {}
    };
    fetchQR();
  }, []);

  const handlePaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.type.indexOf("image") !== -1) {
        const file = item.getAsFile();
        if (file) {
          e.preventDefault();
          const ext = file.type.split("/")[1] || "png";
          const imageFile = new File([file], `pasted_image_${Date.now()}.${ext}`, { type: file.type });
          setSelectedFile(imageFile);
          setSelectedFileType("image");
          setShowAttachMenu(false);
          break;
        }
      }
    }
  };

  const startVoiceRecording = async () => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert("Microphone is not supported in this browser or environment.");
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      let mimeType = "audio/webm";
      if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
        mimeType = "audio/webm;codecs=opus";
      } else if (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")) {
        mimeType = "audio/ogg;codecs=opus";
      } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
        mimeType = "audio/mp4";
      }

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        if (audioChunksRef.current.length > 0 && recorder.__sendOnStop) {
          const actualMime = recorder.mimeType || mimeType || "audio/webm";
          const ext = actualMime.includes("ogg") ? "ogg" : actualMime.includes("mp4") ? "m4a" : "webm";
          const audioBlob = new Blob(audioChunksRef.current, { type: actualMime });
          const audioFile = new File([audioBlob], `voice_note_${Date.now()}.${ext}`, { type: actualMime });
          if (handleSendChatMedia) {
            await handleSendChatMedia({
              file: audioFile,
              mediaType: "audio",
              caption: ""
            });
            setTimeout(() => scrollToBottom("smooth"), 100);
          }
        }
        audioChunksRef.current = [];
        setIsRecording(false);
        setRecordingSeconds(0);
      };

      recorder.__sendOnStop = true;
      recorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);

      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error("Failed to start voice recording:", err);
      alert("Microphone access was denied or is unavailable: " + (err.message || err));
    }
  };

  const stopVoiceRecording = (send = true) => {
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.__sendOnStop = send;
      mediaRecorderRef.current.stop();
    } else {
      setIsRecording(false);
      setRecordingSeconds(0);
    }
  };

  useEffect(() => {
    return () => {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.__sendOnStop = false;
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  // Check WhatsApp call permission when customer is selected
  useEffect(() => {
    if (!selectedChatPhone) {
      setCallPermStatus(null);
      return;
    }
    let isMounted = true;
    const checkPerm = async () => {
      try {
        const token = localStorage.getItem("token");
        const res = await axios.get(`/api/calls/permission?phone=${encodeURIComponent(selectedChatPhone)}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
        if (isMounted) {
          const perm = res.data.permission_status;
          if (perm === "temporary" || perm === "permanent" || perm === "granted" || res.data.can_start_call) {
            setCallPermStatus("granted");
          } else {
            setCallPermStatus(perm || "no_permission");
          }
        }
      } catch (err) {
        if (isMounted) setCallPermStatus("no_permission");
      }
    };
    checkPerm();
    return () => { isMounted = false; };
  }, [selectedChatPhone]);

  const handleSendCallPermissionRequest = async () => {
    if (!selectedChatPhone) return;
    try {
      setCallStatusMsg("Sending call request to customer on WhatsApp...");
      const token = localStorage.getItem("token");
      await axios.post("/api/calls/request-permission", {
        customer_phone: selectedChatPhone,
        custom_message: "We would like to connect with you via WhatsApp Voice Call regarding your inquiry. Please tap Allow below."
      }, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      setCallStatusMsg("Request sent! Once customer taps 'Allow' on WhatsApp, you can place the call.");
      setCallPermStatus("pending");
      if (fetchChatMessages) fetchChatMessages(selectedChatPhone, false);
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to send call request";
      setCallStatusMsg(`Error: ${msg}`);
    }
  };

  const handleStartWhatsAppCall = async () => {
    if (!selectedChatPhone) return;
    try {
      setIsCalling(true);
      setCallStatusMsg("Requesting microphone access...");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      localAudioStreamRef.current = stream;

      setCallStatusMsg("Initializing WebRTC audio session...");
      const pc = new RTCPeerConnection({
        iceServers: [
          { urls: "stun:stun.l.google.com:19302" },
          { urls: "stun:stun1.l.google.com:19302" }
        ]
      });
      peerConnectionRef.current = pc;

      // Add local audio tracks
      stream.getTracks().forEach((track) => {
        pc.addTrack(track, stream);
      });

      // Handle remote incoming audio from customer
      pc.ontrack = (event) => {
        if (remoteAudioRef.current && event.streams[0]) {
          remoteAudioRef.current.srcObject = event.streams[0];
          remoteAudioRef.current.play().catch(() => {});
        }
      };

      // Create WebRTC Offer
      const offer = await pc.createOffer({
        offerToReceiveAudio: true
      });
      await pc.setLocalDescription(offer);

      setCallStatusMsg("Dialing customer on WhatsApp (+91 88660 22206)...");
      const token = localStorage.getItem("token");
      const res = await axios.post("/api/calls/initiate", {
        customer_phone: selectedChatPhone,
        sdp_offer: offer.sdp
      }, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });

      if (res.data?.call_id) {
        setActiveCallId(res.data.call_id);
        setCallStatusMsg("Ringing on customer's WhatsApp...");
        setCallDuration(0);
        if (callTimerRef.current) clearInterval(callTimerRef.current);
        callTimerRef.current = setInterval(() => {
          setCallDuration((prev) => prev + 1);
        }, 1000);
      } else {
        setCallStatusMsg("Calling initiated. Waiting for response...");
      }
    } catch (err) {
      console.error("Call error:", err);
      const msg = err.response?.data?.detail || err.message || "Failed to connect call";
      setCallStatusMsg(`Call failed: ${msg}`);
      handleEndCall();
    }
  };

  const handleEndCall = async () => {
    if (callTimerRef.current) {
      clearInterval(callTimerRef.current);
      callTimerRef.current = null;
    }
    if (localAudioStreamRef.current) {
      localAudioStreamRef.current.getTracks().forEach((t) => t.stop());
      localAudioStreamRef.current = null;
    }
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
    if (activeCallId) {
      try {
        const token = localStorage.getItem("token");
        await axios.post("/api/calls/terminate", { call_id: activeCallId }, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
      } catch (e) {}
      setActiveCallId(null);
    }
    setIsCalling(false);
    setCallDuration(0);
  };

  const handleFilePicked = (e, forcedType = null) => {
    const file = e.target.files?.[0];
    if (!file) return;

    let type = forcedType;
    if (!type) {
      if (file.type.startsWith("image/")) type = "image";
      else if (file.type.startsWith("video/")) type = "video";
      else if (file.type.startsWith("audio/")) type = "audio";
      else type = "document";
    }

    setSelectedFile(file);
    setSelectedFileType(type);
    setShowAttachMenu(false);
    // Reset file input value so re-selecting same file triggers onChange
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSendMediaSubmit = async (e) => {
    e?.preventDefault();
    if (!selectedFile || !handleSendChatMedia || chatSending) return;

    const fileToSend = selectedFile;
    const typeToSend = selectedFileType;
    const captionToSend = mediaCaption.trim();

    setSelectedFile(null);
    setMediaCaption("");
    setShowAttachMenu(false);

    await handleSendChatMedia({
      file: fileToSend,
      mediaType: typeToSend,
      caption: captionToSend
    });
    setTimeout(() => scrollToBottom("smooth"), 100);
  };

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
      if (replyInputRef.current) {
        replyInputRef.current.style.height = "auto";
      }
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
    <div className={`bg-white overflow-hidden flex flex-col flex-1 min-h-0 w-full ${isNativeApp ? "h-[100dvh] rounded-none border-0" : "rounded-2xl border border-gray-200 shadow-sm"}`}>
      {/* Dedicated Native WhatsApp App Top Header (Shown on conversation list) */}
      {isNativeApp && !selectedChatPhone && (
        <div className="bg-[#075E54] text-white px-4 pt-[env(safe-area-inset-top,10px)] pb-2.5 flex items-center justify-between shadow-sm shrink-0 z-30">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-full bg-[#25D366] text-black font-extrabold flex items-center justify-center text-sm shadow-inner shrink-0">
              JW
            </div>
            <div className="min-w-0">
              <h1 className="font-bold text-base tracking-wide leading-tight truncate">JWL Whatsapp</h1>
              <p className="text-[11px] text-emerald-200 flex items-center gap-1.5 leading-tight">
                <span className="w-2 h-2 rounded-full bg-[#25D366] inline-block animate-pulse"></span>
                Live Customer Chat
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => {
                const next = !chatSoundEnabled;
                setChatSoundEnabled(next);
                if (next && playIncomingMessageSound) playIncomingMessageSound(true);
              }}
              className="p-2 rounded-full hover:bg-white/10 text-emerald-100 transition"
              title={chatSoundEnabled ? "Mute sound" : "Enable sound"}
            >
              {chatSoundEnabled ? <Volume2 className="w-4 h-4 text-[#25D366]" /> : <VolumeX className="w-4 h-4 text-emerald-300" />}
            </button>
            {onLogout && (
              <button
                type="button"
                onClick={onLogout}
                className="p-2 rounded-full hover:bg-red-500/20 text-emerald-100 hover:text-white transition"
                title="Exit / Logout"
              >
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      )}
      {/* Top Banner / Live Status Indicator (Desktop only) */}
      {!isNativeApp && <div className="px-6 py-2.5 bg-gradient-to-r from-emerald-50 via-gray-50 to-white border-b border-gray-200 flex items-center justify-between flex-shrink-0">
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
        </div>
      </div>}

      {/* 2-Column WhatsApp Web Layout */}
      <div className="flex-1 flex overflow-hidden min-h-0 relative">
        {/* ── Left Column: Conversation Sidebar (Full-width on mobile when no chat or list active, Collapsible on desktop) ── */}
        <div
          className={`${
            selectedChatPhone ? "hidden md:flex" : "flex w-full"
          } ${
            chatListCollapsed ? "md:w-0 md:border-r-0 md:overflow-hidden md:hidden" : "md:w-80 lg:md:w-96 md:border-r md:border-gray-200"
          } flex-col bg-gray-50/60 min-h-0 transition-all duration-300 ease-in-out`}
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
                onClick={() => {
                  setChatListCollapsed(true);
                  localStorage.setItem("chatListCollapsed", "true");
                }}
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
          <div className="flex-1 flex flex-col bg-[#EFEAE2]/30 min-w-0 overflow-hidden h-full">
            {/* Active Conversation Header */}
            {(() => {
              const activeConv = chatConversations.find(
                (c) => c.customer_phone === selectedChatPhone
              );
              const matchingContact = contacts.find(
                (c) => c.phone === selectedChatPhone
              );
              return (
                <div className={`px-4 py-2.5 bg-white border-b border-gray-200 flex items-center justify-between gap-3 shadow-xs shrink-0 z-30 ${isNativeApp ? "pt-[env(safe-area-inset-top,10px)]" : ""}`}>

                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    {/* Mobile Back to Conversation List button */}
                    <button
                      onClick={() => handleSelectConversation("")}
                      className="md:hidden p-1.5 -ml-1 text-gray-700 hover:bg-gray-100 rounded-lg transition shrink-0 flex items-center gap-0.5 text-xs font-semibold cursor-pointer"
                      title="Back to conversation list"
                    >
                      <ChevronLeft className="w-5 h-5 text-gray-700" />
                    </button>

                    {/* Desktop expand chat list button */}
                    {chatListCollapsed && (
                      <button
                        onClick={() => {
                          setChatListCollapsed(false);
                          localStorage.setItem("chatListCollapsed", "false");
                        }}
                        className="hidden md:flex p-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition shrink-0 items-center gap-1 text-xs font-semibold cursor-pointer"
                        title="Show conversation list"
                      >
                        <ChevronRight className="w-4 h-4" />
                        <span className="hidden sm:inline">Chats</span>
                      </button>
                    )}
                    <div className="w-10 h-10 rounded-full bg-[#25D366] text-white flex items-center justify-center font-bold text-sm shrink-0">
                      {activeConv?.customer_name
                        ? activeConv.customer_name.charAt(0).toUpperCase()
                        : "C"}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-bold text-gray-900 truncate">
                          {activeConv?.customer_name || matchingContact?.name || "Customer"}
                        </h3>
                        {(matchingContact?.total_orders || activeConv?.total_orders || 0) >= 5 && (
                          <span className="px-1.5 py-0.2 bg-amber-100 text-amber-800 font-bold rounded text-[10px] flex items-center gap-0.5 shrink-0">
                            <Star className="w-3 h-3 fill-amber-500 text-amber-500" /> VIP
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500 mt-0.5">
                        <span className="font-mono text-gray-700 font-medium shrink-0">{selectedChatPhone}</span>
                        {(matchingContact?.city || activeConv?.customer_city) && (
                          <>
                            <span className="text-gray-300">•</span>
                            <span className="shrink-0">{matchingContact?.city || activeConv?.customer_city}</span>
                          </>
                        )}
                        <span className="text-gray-300">•</span>
                        <span className="shrink-0">
                          Orders: {matchingContact?.total_orders ?? activeConv?.total_orders ?? 0}
                        </span>
                        {(() => {
                          const order = activeConv?.last_order || matchingContact?.custom_attributes?.last_order;
                          if (!order) return null;
                          return (
                            <span
                              className="inline-flex items-center gap-1 bg-amber-50 text-amber-900 border border-amber-200 px-1.5 py-0.5 rounded text-[11px] font-medium cursor-help shrink-0 max-w-full"
                              title={`Last Order: #${order.order_number || order.order_id}\nTotal: ${order.currency || 'INR'} ${order.total_price}\nItems:\n${(order.items || []).map(i => `• ${i.quantity}x ${i.title} (₹${i.price})`).join('\n') || order.items_summary}`}
                            >
                              <ShoppingBag className="w-3 h-3 text-amber-600 shrink-0" />
                              <span className="font-semibold text-amber-800">Last:</span>
                              <span className="max-w-[120px] sm:max-w-[180px] md:max-w-[240px] truncate text-amber-900 font-medium">
                                {order.items_summary || `#${order.order_number || order.order_id}`}
                              </span>
                              {order.total_price ? (
                                <span className="font-bold text-emerald-700 shrink-0">({order.currency || '₹'}{order.total_price})</span>
                              ) : null}
                            </span>
                          );
                        })()}
                      </div>
                    </div>
                  </div>

                  {/* Actions Header Toolbar: always shrink-0 and visible */}
                  <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
                    {(() => {
                      const isBlocked = optOuts.some(
                        (o) => o.phone === selectedChatPhone || o.phone === selectedChatPhone.replace("+", "")
                      );
                      return (
                        <button
                          onClick={() => handleBlockContact && handleBlockContact(selectedChatPhone, isBlocked)}
                          className={`px-2.5 py-1.5 border rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shrink-0 cursor-pointer ${
                            isBlocked
                              ? "border-red-400 bg-red-100 text-red-800 hover:bg-red-200"
                              : "border-gray-300 bg-white text-gray-700 hover:bg-red-50 hover:text-red-600 hover:border-red-300"
                          }`}
                          title={isBlocked ? "Contact is Blocked / Opted Out (Click to unblock)" : "Block number & add to Opt-Out (DND)"}
                        >
                          <Ban className={`w-3.5 h-3.5 ${isBlocked ? "text-red-700" : "text-gray-500"}`} />
                          <span className="hidden sm:inline">{isBlocked ? "Blocked" : "Block"}</span>
                        </button>
                      );
                    })()}
                    {/* WhatsApp Direct In-App Call Button */}
                    <button
                      type="button"
                      onClick={() => {
                        setCallModalOpen(true);
                        setCallStatusMsg("");
                      }}
                      className={`px-2.5 py-1.5 border rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shrink-0 cursor-pointer ${
                        callPermStatus === "granted"
                          ? "border-emerald-500 bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm"
                          : "border-emerald-400 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
                      }`}
                      title={
                        callPermStatus === "granted"
                          ? "Call directly via WhatsApp Voice Call (Permission Active)"
                          : "WhatsApp Voice Call (Click to check/request permission)"
                      }
                    >
                      <PhoneCall className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">
                        {callPermStatus === "granted" ? "WA Call (Ready)" : "WA Call"}
                      </span>
                    </button>

                    <a
                      href={`tel:${selectedChatPhone}`}
                      className="px-2.5 py-1.5 border border-blue-300 text-blue-700 bg-blue-50 rounded-lg text-xs font-semibold hover:bg-blue-100 transition flex items-center gap-1.5 shrink-0"
                      title={`Call customer directly (${selectedChatPhone})`}
                    >
                      <Phone className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Call</span>
                    </a>
                    <a
                      href={`https://wa.me/${selectedChatPhone.replace("+", "")}`}
                      target="_blank"
                      rel="noreferrer"
                      className="px-2.5 py-1.5 border border-emerald-300 text-emerald-700 bg-emerald-50 rounded-lg text-xs font-semibold hover:bg-emerald-100 transition flex items-center gap-1.5 shrink-0"
                      title="Open in WhatsApp Web"
                    >
                      <PhoneCall className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">WhatsApp Web</span>
                    </a>
                    <button
                      onClick={() => fetchChatMessages(selectedChatPhone, false)}
                      disabled={chatLoading}
                      className="p-1.5 text-gray-500 hover:text-gray-800 rounded-lg hover:bg-gray-100 transition cursor-pointer shrink-0"
                      title="Refresh messages"
                    >
                      <RefreshCw className={`w-4 h-4 ${chatLoading ? "animate-spin" : ""}`} />
                    </button>
                    {handleDeleteConversation && (
                      <button
                        onClick={() => handleDeleteConversation(selectedChatPhone)}
                        className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg transition cursor-pointer shrink-0"
                        title="Delete this conversation"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })()}

            {/* Messages Scroll Area */}
            <div className="flex-1 relative min-h-0 flex flex-col">
              <div
                ref={messagesContainerRef}
                onScroll={handleScroll}
                className="flex-1 p-3 sm:p-5 overflow-y-auto space-y-2.5 bg-[#E5DDD5]/20 min-w-0 overscroll-contain"
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
                    const currentDateKey = getMessageISTDateKey(msg.created_at);
                    const prevDateKey = index > 0 ? getMessageISTDateKey(chatMessages[index - 1]?.created_at) : null;
                    const showDateDivider = index === 0 || (currentDateKey && currentDateKey !== prevDateKey);
                    const dividerText = showDateDivider ? formatChatDateDivider(msg.created_at) : "";

                    return (
                      <React.Fragment key={msg.id || index}>
                        {showDateDivider && dividerText && (
                          <div className="flex justify-center my-3 select-none">
                            <span className="bg-white/80 backdrop-blur-xs text-gray-500 text-[11px] font-semibold px-3 py-1 rounded-full shadow-xs border border-gray-200/60 uppercase tracking-wider">
                              {dividerText}
                            </span>
                          </div>
                        )}
                        <div
                          className={`flex group/msg ${isAgent ? "justify-end" : "justify-start"} mb-1.5`}
                        >
                        <div
                          className={`max-w-[85%] md:max-w-lg break-words rounded-2xl px-4 py-2.5 shadow-xs text-sm relative group ${
                            isAgent
                              ? "bg-[#D9FDD3] text-gray-900 rounded-tr-xs border border-emerald-200/60"
                              : "bg-white text-gray-900 rounded-tl-xs border border-gray-200/80"
                          }`}
                        >
                          {/* Quick Reaction Toolbar (visible on hover or tap) */}
                          {handleReactToMessage && typeof msg.id === "number" && (
                            <div
                              className={`absolute -top-3.5 ${
                                isAgent ? "left-2" : "right-2"
                              } opacity-0 group-hover/msg:opacity-100 transition-all duration-150 flex items-center gap-1 bg-white border border-gray-200 shadow-md rounded-full px-2 py-0.5 z-10`}
                            >
                              <button
                                type="button"
                                title="Thumbs Up"
                                onClick={() => handleReactToMessage(msg.id, "👍")}
                                className={`p-1 rounded-full hover:bg-emerald-50 transition transform hover:scale-125 ${
                                  msg.reaction === "👍" ? "text-emerald-600 bg-emerald-100" : "text-gray-500 hover:text-emerald-600"
                                }`}
                              >
                                <ThumbsUp className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                title="Thumbs Down"
                                onClick={() => handleReactToMessage(msg.id, "👎")}
                                className={`p-1 rounded-full hover:bg-rose-50 transition transform hover:scale-125 ${
                                  msg.reaction === "👎" ? "text-rose-600 bg-rose-100" : "text-gray-500 hover:text-rose-600"
                                }`}
                              >
                                <ThumbsDown className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          )}
                          {isAgent && msg.message_type === "template" && (
                            <div className="text-[10px] font-bold text-amber-800 bg-amber-100/90 px-2 py-0.5 rounded inline-block mb-1">
                               WhatsApp Template Broadcast
                            </div>
                          )}
                          {!isAgent && (
                            <div className="text-[10px] font-bold text-emerald-700 mb-0.5">
                              Customer
                            </div>
                          )}

                          {/* Contact Card Message */}
                          {msg.message_type === "contacts" && (
                            <div className="mb-2 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-gray-900 flex items-center gap-3">
                              <div className="w-10 h-10 rounded-full bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                                <User className="w-5 h-5" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="text-xs font-bold text-gray-900 truncate">
                                  {msg.filename || msg.text?.replace("👤", "").trim() || "Shared Contact"}
                                </p>
                                {msg.text && msg.text.includes("\n") && (
                                  <p className="text-[11px] font-mono text-emerald-800 truncate">
                                    {msg.text.split("\n")[1]}
                                  </p>
                                )}
                                <span className="inline-block mt-0.5 text-[10px] font-semibold text-emerald-700 bg-emerald-100/80 px-1.5 py-0.2 rounded">
                                  WhatsApp Contact
                                </span>
                              </div>
                            </div>
                          )}

                          {/* Media Rendering */}
                          {msg.media_url && (() => {
                            const rawUrl = msg.media_url;
                            const fullUrl = rawUrl.startsWith("http://") || rawUrl.startsWith("https://") || rawUrl.startsWith("blob:")
                              ? rawUrl
                              : `${getApiBaseUrl().replace(/\/$/, "")}${rawUrl.startsWith("/") ? "" : "/"}${rawUrl}`;

                            return (
                              <div className="mb-2">
                                {msg.message_type === "image" && (
                                  <div className="rounded-xl overflow-hidden border border-gray-200/60 max-w-sm bg-black/5">
                                    <img
                                      src={fullUrl}
                                      alt={msg.filename || "WhatsApp Image"}
                                      className="max-h-64 w-full object-cover rounded-xl hover:opacity-95 transition cursor-pointer"
                                      onClick={() => window.open(fullUrl, "_blank")}
                                    />
                                  </div>
                                )}

                                {msg.message_type === "sticker" && (
                                  <div className="p-1 max-w-[160px] bg-transparent">
                                    <img
                                      src={fullUrl}
                                      alt="WhatsApp Sticker"
                                      className="max-h-36 max-w-[160px] object-contain drop-shadow hover:scale-105 transition cursor-pointer"
                                      onClick={() => window.open(fullUrl, "_blank")}
                                    />
                                  </div>
                                )}

                                {msg.message_type === "video" && (
                                  <div className="rounded-xl overflow-hidden border border-gray-200/60 max-w-sm bg-black">
                                    <video
                                      src={fullUrl}
                                      controls
                                      preload="metadata"
                                      playsInline
                                      className="max-h-64 w-full rounded-xl"
                                    />
                                    <div className="p-1.5 bg-black/80 flex items-center justify-between text-[11px] text-gray-300 px-3">
                                      <span className="truncate max-w-[200px]">{msg.filename || "WhatsApp Video"}</span>
                                      <a
                                        href={fullUrl}
                                        target="_blank"
                                        rel="noreferrer"
                                        download={msg.filename || "video.mp4"}
                                        className="text-emerald-400 hover:text-emerald-300 font-semibold flex items-center gap-1"
                                      >
                                        <Download className="w-3.5 h-3.5" /> Open / Download
                                      </a>
                                    </div>
                                  </div>
                                )}

                                {msg.message_type === "audio" && (
                                  <div className="py-1 min-w-[220px] sm:min-w-[260px]">
                                    <audio
                                      src={fullUrl}
                                      controls
                                      preload="metadata"
                                      className="w-full h-10 rounded-lg"
                                    />
                                  </div>
                                )}

                                {msg.message_type === "document" && (
                                  <a
                                    href={fullUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    download={msg.filename || "document"}
                                    className="flex items-center gap-3 p-2.5 rounded-xl bg-black/5 hover:bg-black/10 border border-gray-200/60 transition group text-left"
                                  >
                                    <div className="w-10 h-10 rounded-lg bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                                      <FileText className="w-5 h-5" />
                                    </div>
                                    <div className="min-w-0 flex-1">
                                      <p className="text-xs font-bold text-gray-900 truncate">
                                        {msg.filename || "Document Attachment"}
                                      </p>
                                      <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">
                                        Click to download / view
                                      </p>
                                    </div>
                                    <Download className="w-4 h-4 text-gray-400 group-hover:text-emerald-600 shrink-0 transition" />
                                  </a>
                                )}
                              </div>
                            );
                          })()}

                          {/* Fallback for sticker message without downloaded media_url */}
                          {msg.message_type === "sticker" && !msg.media_url && (
                            <div className="mb-2 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 flex items-center gap-3">
                              <Smile className="w-6 h-6 text-amber-600 shrink-0" />
                              <div className="min-w-0">
                                <p className="text-xs font-bold text-amber-900">WhatsApp Sticker</p>
                                <p className="text-[10px] text-amber-700">Sticker message received from customer</p>
                              </div>
                            </div>
                          )}

                          {/* Text or Caption (omitted if already rendered as contact card or sticker) */}
                          {msg.text && msg.message_type !== "contacts" && !(msg.message_type === "sticker" && !msg.media_url) && (
                            <p className="whitespace-pre-wrap leading-relaxed text-xs md:text-sm">
                              {msg.text}
                            </p>
                          )}

                          {/* Render Attached Reaction Badge if active */}
                          {msg.reaction && (
                            <div
                              onClick={() => handleReactToMessage && typeof msg.id === "number" && handleReactToMessage(msg.id, msg.reaction)}
                              title="Click to remove reaction"
                              className={`absolute -bottom-2.5 ${
                                isAgent ? "left-3" : "right-3"
                              } bg-white border border-gray-200/90 shadow-xs rounded-full px-1.5 py-0.5 text-xs flex items-center gap-0.5 cursor-pointer hover:scale-110 transition z-10`}
                            >
                              <span>{msg.reaction}</span>
                            </div>
                          )}

                          <div
                            className={`flex items-center gap-1.5 justify-end mt-1 text-[10px] ${
                              isAgent ? "text-emerald-800/70" : "text-gray-400"
                            }`}
                          >
                            <span>
                              {formatToISTDateTime(msg.created_at)}
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
                    </React.Fragment>
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

            {/* Quick Reply Suggestions (Max 2 lines, Vertically scrollable) */}
            <div className="px-3.5 py-1.5 bg-gray-50 border-t border-gray-200 flex items-start gap-2 flex-shrink-0 min-w-0 max-w-full">
              <span className="text-[10px] font-bold uppercase text-gray-500 flex items-center gap-1 flex-shrink-0 pt-1">
                <Sparkles className="w-3 h-3 text-[#F5A623]" /> Quick replies:
              </span>
              <div className="flex-1 max-h-[68px] overflow-y-auto flex flex-wrap gap-1.5 pr-1">
                {(serverQuickReplies.length > 0 ? serverQuickReplies : [
                  { id: 1, title: "Welcome & Website", message: "Hello! Welcome to JWL Billion. How can we assist you today?\nVisit our website: https://jwlbillion.com/" },
                  { id: 2, title: "Order Processing", message: "Your order has been confirmed and is being processed for dispatch." },
                  { id: 4, title: "Welcome Discount", message: "Here is your special discount code: WELCOME (7% OFF)" },
                  { id: 5, title: "Order ID Inquiry", message: "Could you please share your Order ID so we can check the status?" }
                ]).map((qr, idx) => {
                  const text = typeof qr === "string" ? qr : (qr.message || qr.title);
                  const label = typeof qr === "string" ? qr : (qr.title || qr.message);
                  return (
                    <button
                      key={qr.id || idx}
                      type="button"
                      onClick={() => {
                        setLocalInputText(text);
                        if (setChatReplyText) setChatReplyText(text);
                        if (replyInputRef.current) {
                          replyInputRef.current.focus();
                        }
                      }}
                      title={text}
                      className="px-2.5 py-1 bg-white hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-300 border border-gray-200 rounded-lg text-xs text-gray-700 transition shadow-2xs font-medium cursor-pointer max-w-[280px] truncate leading-tight"
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Hidden native file inputs */}
            <input
              type="file"
              ref={fileInputRef}
              className="hidden"
              onChange={(e) => handleFilePicked(e, selectedFileType)}
            />

            {/* Media Attachment Preview Tray (if file selected) */}
            {selectedFile && (
              <div className="p-3 bg-emerald-50/90 border-t border-emerald-200 flex items-center justify-between gap-3 flex-shrink-0 animate-in fade-in duration-150">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-sm">
                    {selectedFileType === "image" && <ImageIcon className="w-5 h-5" />}
                    {selectedFileType === "video" && <Video className="w-5 h-5" />}
                    {selectedFileType === "audio" && <Music className="w-5 h-5" />}
                    {selectedFileType === "document" && <FileText className="w-5 h-5" />}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-gray-900 truncate">
                        {selectedFile.name}
                      </span>
                      <span className="text-[10px] font-semibold text-emerald-800 bg-emerald-100 px-1.5 py-0.2 rounded uppercase">
                        {selectedFileType}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-500">
                      {(selectedFile.size / 1024).toFixed(1)} KB • Ready to send via WhatsApp
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedFile(null);
                      setMediaCaption("");
                    }}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-white rounded-lg transition"
                    title="Cancel attachment"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            {/* Chat Input Bar (Sticky Fixed at bottom of chat) */}
            <div className="p-2 sm:p-3 bg-white border-t border-gray-200 relative flex-shrink-0 min-w-0 w-full pb-[max(env(safe-area-inset-bottom,0px),16px)] z-20">
              {/* Attachment Popup Menu */}
              {showAttachMenu && (
                <div className="absolute bottom-16 left-4 z-30 bg-white border border-gray-200 rounded-2xl shadow-xl p-2 flex flex-col gap-1 w-52 animate-in fade-in slide-in-from-bottom-2 duration-150">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedFileType("document");
                      fileInputRef.current.accept = ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv";
                      fileInputRef.current.click();
                    }}
                    className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-emerald-50 hover:text-emerald-800 rounded-xl transition text-left cursor-pointer"
                  >
                    <div className="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="font-bold text-gray-900">Document / PDF</p>
                      <p className="text-[10px] text-gray-400">PDF, Word, Excel, TXT</p>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setSelectedFileType("image");
                      fileInputRef.current.accept = "image/*";
                      fileInputRef.current.click();
                    }}
                    className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-emerald-50 hover:text-emerald-800 rounded-xl transition text-left cursor-pointer"
                  >
                    <div className="w-7 h-7 rounded-lg bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0">
                      <ImageIcon className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="font-bold text-gray-900">Image / Photo</p>
                      <p className="text-[10px] text-gray-400">PNG, JPG, WEBP</p>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setSelectedFileType("video");
                      fileInputRef.current.accept = "video/mp4,video/3gpp";
                      fileInputRef.current.click();
                    }}
                    className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-emerald-50 hover:text-emerald-800 rounded-xl transition text-left cursor-pointer"
                  >
                    <div className="w-7 h-7 rounded-lg bg-red-100 text-red-600 flex items-center justify-center shrink-0">
                      <Video className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="font-bold text-gray-900">Video Clip</p>
                      <p className="text-[10px] text-gray-400">MP4, 3GP</p>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setSelectedFileType("audio");
                      fileInputRef.current.accept = "audio/*";
                      fileInputRef.current.click();
                    }}
                    className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-emerald-50 hover:text-emerald-800 rounded-xl transition text-left cursor-pointer"
                  >
                    <div className="w-7 h-7 rounded-lg bg-amber-100 text-amber-600 flex items-center justify-center shrink-0">
                      <Music className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="font-bold text-gray-900">Audio / Voice Note</p>
                      <p className="text-[10px] text-gray-400">MP3, AAC, OGG</p>
                    </div>
                  </button>
                </div>
              )}

              {/* Form Bar */}
              <div className="flex items-end gap-2 min-w-0 w-full">
                {/* Paperclip Button */}
                <button
                  type="button"
                  onClick={() => setShowAttachMenu((prev) => !prev)}
                  className={`p-2.5 rounded-xl border transition cursor-pointer shrink-0 mb-0.5 ${
                    showAttachMenu || selectedFile
                      ? "bg-emerald-100 text-emerald-800 border-emerald-300"
                      : "bg-gray-100 text-gray-600 hover:text-gray-900 hover:bg-gray-200 border-gray-200"
                  }`}
                  title="Attach document, image, video or audio"
                >
                  <Paperclip className="w-4 h-4" />
                </button>

                {/* Recording Active Bar */}
                {isRecording ? (
                  <div className="flex-1 flex items-center justify-between bg-red-50 border border-red-200 rounded-xl px-4 py-2 animate-pulse">
                    <div className="flex items-center gap-2.5">
                      <div className="w-3 h-3 rounded-full bg-red-600 animate-ping" />
                      <span className="text-xs font-bold text-red-700">
                        Recording {Math.floor(recordingSeconds / 60)}:
                        {(recordingSeconds % 60).toString().padStart(2, "0")}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => stopVoiceRecording(false)}
                        className="px-2.5 py-1 text-xs font-medium text-gray-600 hover:text-red-700 hover:bg-red-100 rounded-lg transition"
                        title="Cancel voice recording"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => stopVoiceRecording(true)}
                        className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-bold shadow-xs transition flex items-center gap-1"
                        title="Finish and send voice note"
                      >
                        <Send className="w-3 h-3" /> Send
                      </button>
                    </div>
                  </div>
                ) : (
                  <ChatInputBox
                    selectedFile={selectedFile}
                    mediaCaption={mediaCaption}
                    setMediaCaption={setMediaCaption}
                    chatSending={chatSending}
                    handlePaste={handlePaste}
                    handleSendChatMessage={handleSendChatMessage}
                    handleSendMediaSubmit={handleSendMediaSubmit}
                    startVoiceRecording={startVoiceRecording}
                    scrollToBottom={scrollToBottom}
                    isNearBottomRef={isNearBottomRef}
                    selectedFileType={selectedFileType}
                    replyInputRef={replyInputRef}
                    initialText={localInputText}
                  />
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="hidden md:flex flex-1 flex-col items-center justify-center p-8 text-center bg-gray-50/50 relative">
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

      {/* WhatsApp Voice Calling Permission & Dial Modal */}
      {callModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center">
                  <PhoneCall className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-gray-900 text-base">WhatsApp Voice Calling</h3>
                  <p className="text-xs text-gray-500 font-mono">{selectedChatPhone}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setCallModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100 cursor-pointer text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div className="bg-emerald-50/70 border border-emerald-200/60 rounded-xl p-3.5 text-xs text-emerald-900 leading-relaxed">
              Calls placed here will ring directly on the customer's WhatsApp application from your verified WhatsApp business profile (<strong>+91 88660 22206</strong>).
            </div>

            {callPermStatus === "granted" ? (
              <div className="flex flex-col gap-3 py-2">
                <div className="flex items-center gap-2 text-xs font-semibold text-emerald-700 bg-emerald-100/70 px-3 py-2 rounded-lg">
                  <CheckCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Call Permission is Active! Ready to connect.</span>
                </div>
                <p className="text-xs text-gray-600 leading-relaxed">
                  Your microphone will be used to stream audio directly into the customer's WhatsApp call.
                </p>

                {callStatusMsg && (
                  <div className="text-xs p-2.5 rounded-lg bg-gray-100 text-gray-800 font-medium animate-pulse">
                    {callStatusMsg}
                  </div>
                )}

                {isCalling ? (
                  <div className="flex flex-col gap-2 pt-2">
                    <div className="text-center font-mono text-sm font-bold text-emerald-600">
                      Duration: {Math.floor(callDuration / 60).toString().padStart(2, "0")}:{(callDuration % 60).toString().padStart(2, "0")}
                    </div>
                    <button
                      type="button"
                      onClick={handleEndCall}
                      className="w-full py-2.5 bg-red-600 hover:bg-red-700 text-white font-bold text-sm rounded-xl shadow-sm transition flex items-center justify-center gap-2 cursor-pointer"
                    >
                      <Ban className="w-4 h-4" />
                      End Call
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={handleStartWhatsAppCall}
                    className="w-full py-2.5 bg-[#25D366] hover:bg-[#1EBE5D] text-white font-bold text-sm rounded-xl shadow-sm transition flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <PhoneCall className="w-4 h-4" />
                    Start WhatsApp Call
                  </button>
                )}
                {/* Hidden audio element to play remote customer voice */}
                <audio ref={remoteAudioRef} autoPlay playsInline className="hidden" />
              </div>
            ) : (
              <div className="flex flex-col gap-3 py-1">
                <div className="text-xs text-gray-600 leading-relaxed">
                  Meta's anti-spam policy requires the customer to allow outbound calls. Tap below to send a <strong>Call Permission Request</strong> interactive card to their WhatsApp chat.
                </div>
                {callStatusMsg && (
                  <div className="text-xs p-2.5 rounded-lg bg-gray-100 text-gray-800 font-medium">
                    {callStatusMsg}
                  </div>
                )}
                <div className="flex items-center gap-2 pt-2">
                  <button
                    type="button"
                    onClick={handleSendCallPermissionRequest}
                    className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl shadow-sm transition flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <Send className="w-3.5 h-3.5" />
                    Send Call Request (WhatsApp)
                  </button>
                  <button
                    type="button"
                    onClick={() => setCallModalOpen(false)}
                    className="px-4 py-2.5 border border-gray-200 text-gray-600 text-xs font-semibold rounded-xl hover:bg-gray-50 cursor-pointer"
                  >
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
