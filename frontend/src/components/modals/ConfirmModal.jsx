import React from "react";
import { X, AlertCircle } from "lucide-react";

export default function ConfirmModal({
  isOpen,
  title = "Notice",
  message,
  confirmText = "OK",
  cancelText = "Cancel",
  isDestructive = false,
  showCancel = true,
  onConfirm,
  onCancel,
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl max-w-sm w-full p-5 shadow-2xl border border-gray-100 flex flex-col gap-3">
        {title && (
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-gray-900 text-sm flex items-center gap-1.5">
              <AlertCircle className={`w-4 h-4 ${isDestructive ? "text-red-500" : "text-emerald-600"}`} />
              {title}
            </h3>
            {showCancel && (
              <button
                type="button"
                onClick={onCancel}
                className="p-1 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
        <div className="text-xs text-gray-600 whitespace-pre-line leading-relaxed">
          {message}
        </div>
        <div className="flex items-center justify-end gap-2 pt-2">
          {showCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-3.5 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded-xl transition cursor-pointer"
            >
              {cancelText}
            </button>
          )}
          <button
            type="button"
            onClick={onConfirm}
            className={`px-4 py-2 text-xs font-bold rounded-xl shadow-xs transition cursor-pointer ${
              isDestructive
                ? "bg-red-600 hover:bg-red-700 text-white"
                : "bg-emerald-600 hover:bg-emerald-700 text-white"
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
