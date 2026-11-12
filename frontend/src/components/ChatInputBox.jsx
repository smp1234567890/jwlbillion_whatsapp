import React, { useState, useEffect, useRef } from "react";
import { Send, RefreshCw, Mic } from "lucide-react";

export default function ChatInputBox({
  selectedFile,
  mediaCaption,
  setMediaCaption,
  chatSending,
  handlePaste,
  handleSendChatMessage,
  handleSendMediaSubmit,
  startVoiceRecording,
  scrollToBottom,
  isNearBottomRef,
  selectedFileType,
  replyInputRef,
  initialText = ""
}) {
  const textRef = useRef(initialText || "");
  const [hasText, setHasText] = useState(Boolean(initialText && initialText.trim()));
  const debounceRef = useRef(null);

  // Sync external text changes (e.g. quick reply clicked or initialText prop updated)
  useEffect(() => {
    if (initialText !== undefined && initialText !== null) {
      textRef.current = initialText;
      if (replyInputRef?.current && !selectedFile) {
        replyInputRef.current.value = initialText;
      }
      setHasText(Boolean(initialText.trim()));
    }
  }, [initialText, selectedFile, replyInputRef]);

  const handleSubmit = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (isNearBottomRef) isNearBottomRef.current = true;
    if (selectedFile) {
      handleSendMediaSubmit(e);
    } else {
      const currentVal = replyInputRef?.current ? replyInputRef.current.value : textRef.current;
      const trimmed = currentVal ? currentVal.trim() : "";
      if (!trimmed || chatSending) return;
      if (handleSendChatMessage) {
        handleSendChatMessage(e, trimmed);
      }
      textRef.current = "";
      if (replyInputRef?.current) {
        replyInputRef.current.value = "";
      }
      setHasText(false);
    }
    if (replyInputRef?.current) {
      replyInputRef.current.style.height = "auto";
    }
    if (scrollToBottom) {
      setTimeout(() => scrollToBottom("smooth"), 50);
    }
  };

  const hasContent = selectedFile ? Boolean(mediaCaption && mediaCaption.trim()) : hasText;

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-2 min-w-0 w-full">
      <textarea
        ref={replyInputRef}
        rows={1}
        placeholder={
          selectedFile
            ? `Add caption for this ${selectedFileType}...`
            : "Type a message or paste image..."
        }
        defaultValue={selectedFile ? undefined : (initialText || "")}
        value={selectedFile ? mediaCaption : undefined}
        onPaste={handlePaste}
        onInput={(e) => {
          const val = e.target.value;
          if (selectedFile) {
            setMediaCaption(val);
          } else {
            textRef.current = val;
            const isNonEmpty = Boolean(val.trim());
            // Only trigger a React state change when switching between empty/non-empty for Send/Mic button
            if (isNonEmpty !== hasText) {
              clearTimeout(debounceRef.current);
              debounceRef.current = setTimeout(() => {
                setHasText(Boolean(replyInputRef?.current?.value?.trim()));
              }, 100);
            }
          }
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
          }
        }}
        disabled={chatSending}
        autoComplete="off"
        autoCorrect="off"
        spellCheck="false"
        style={{ fieldSizing: "content" }}
        className="flex-1 min-w-0 min-h-[42px] max-h-32 px-4 py-2.5 bg-gray-100/80 border border-gray-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#25D366] resize-none leading-snug box-border overflow-y-auto"
      />

      {/* Microphone Voice Note Button (shown when input is empty) */}
      {!hasContent && (
        <button
          type="button"
          onClick={startVoiceRecording}
          disabled={chatSending}
          className="p-2.5 rounded-xl border border-gray-200 bg-gray-100 text-gray-700 hover:bg-emerald-50 hover:text-[#25D366] hover:border-emerald-300 transition shrink-0 mb-0.5 cursor-pointer"
          title="Record voice note"
        >
          <Mic className="w-4 h-4" />
        </button>
      )}

      {/* Send Button */}
      <button
        type="submit"
        disabled={!hasContent || chatSending}
        className="px-5 py-2.5 bg-[#25D366] hover:bg-[#1EBE5D] disabled:opacity-50 text-white rounded-xl font-bold text-sm shadow-sm transition flex items-center gap-2 flex-shrink-0 cursor-pointer mb-0.5"
      >
        {chatSending ? (
          <RefreshCw className="w-4 h-4 animate-spin" />
        ) : (
          <Send className="w-4 h-4" />
        )}
        {selectedFile ? "Send Media" : "Send"}
      </button>
    </form>
  );
}
