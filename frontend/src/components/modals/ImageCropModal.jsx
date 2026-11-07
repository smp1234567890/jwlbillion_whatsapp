import React, { useState, useCallback } from "react";
import Cropper from "react-easy-crop";
import { X, Check, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";
import { getCroppedImg } from "../../utils/cropImage";

export default function ImageCropModal({
  isOpen,
  imageSrc,
  title = "Crop & Center Product Image",
  aspect = 1, // 1:1 square recommended for carousel
  onClose,
  onCropComplete: onConfirmCrop
}) {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const onCropChange = (newCrop) => {
    setCrop(newCrop);
  };

  const onZoomChange = (newZoom) => {
    setZoom(newZoom);
  };

  const handleCropAreaChange = useCallback((croppedArea, croppedAreaPixels) => {
    setCroppedAreaPixels(croppedAreaPixels);
  }, []);

  const handleApply = async () => {
    if (!imageSrc || !croppedAreaPixels) return;
    setIsProcessing(true);
    try {
      const croppedBlob = await getCroppedImg(imageSrc, croppedAreaPixels, 1080, 1080);
      await onConfirmCrop(croppedBlob);
      onClose();
    } catch (e) {
      console.error("Crop error:", e);
      const msg = e?.message || (typeof e === "string" ? e : JSON.stringify(e)) || "Unknown error";
      alert("Failed to crop image: " + msg);
    } finally {
      setIsProcessing(false);
    }
  };

  if (!isOpen || !imageSrc) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs animate-in fade-in">
      <div className="bg-white rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50">
          <div>
            <h3 className="font-bold text-gray-900 text-sm">{title}</h3>
            <p className="text-[11px] text-gray-500">
              Drag to position jewelry in the center. Pinch or use slider to zoom.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Cropper area */}
        <div className="relative w-full h-80 sm:h-96 bg-gray-900">
          <Cropper
            image={imageSrc}
            crop={crop}
            zoom={zoom}
            aspect={aspect}
            onCropChange={onCropChange}
            onZoomChange={onZoomChange}
            onCropComplete={handleCropAreaChange}
            showGrid={true}
          />
        </div>

        {/* Zoom Controls */}
        <div className="px-6 py-3 bg-gray-50 border-t border-gray-200 flex items-center gap-4">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(1, z - 0.2))}
            className="p-1 text-gray-500 hover:text-gray-700"
            title="Zoom out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <input
            type="range"
            value={zoom}
            min={1}
            max={3}
            step={0.05}
            aria-labelledby="Zoom"
            onChange={(e) => setZoom(Number(e.target.value))}
            className="w-full h-1.5 bg-gray-300 rounded-lg appearance-none cursor-pointer accent-[#25D366]"
          />
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(3, z + 0.2))}
            className="p-1 text-gray-500 hover:text-gray-700"
            title="Zoom in"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => {
              setZoom(1);
              setCrop({ x: 0, y: 0 });
            }}
            className="text-[11px] text-gray-500 hover:text-gray-800 flex items-center gap-1 shrink-0 ml-1 font-medium"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reset
          </button>
        </div>

        {/* Footer actions */}
        <div className="px-6 py-3.5 bg-white border-t border-gray-100 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-2 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleApply}
            disabled={isProcessing}
            className="flex items-center gap-1.5 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-5 py-2 rounded-lg text-xs font-bold shadow-md transition disabled:opacity-50"
          >
            <Check className="w-4 h-4" />
            {isProcessing ? "Processing & Uploading..." : "Crop & Use Image"}
          </button>
        </div>
      </div>
    </div>
  );
}

