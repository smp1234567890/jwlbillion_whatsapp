import React, { useState, useCallback } from "react";
import Cropper from "react-easy-crop";
import { X, Check, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";
import { getCroppedImg } from "../../utils/cropImage";

export default function ImageCropModal({
  isOpen,
  imageSrc,
  title = "Crop & Center Product Image",
  aspect = 1, // default
  onClose,
  onCropComplete: onConfirmCrop
}) {
  // Preset ratios: 1:1 (1080x1080) and 4:3 (1200x900)
  const [selectedPreset, setSelectedPreset] = useState("1080x1080"); // "1080x1080" | "1200x900"
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const currentAspect = selectedPreset === "1200x900" ? 4 / 3 : 1;
  const targetDims = selectedPreset === "1200x900" ? { width: 1200, height: 900 } : { width: 1080, height: 1080 };

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
      const croppedBlob = await getCroppedImg(
        imageSrc,
        croppedAreaPixels,
        targetDims.width,
        targetDims.height
      );
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
      <div className="bg-white rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-gray-100 flex items-center justify-between bg-gray-50">
          <div>
            <h3 className="font-bold text-gray-900 text-sm">{title}</h3>
            <p className="text-[11px] text-gray-500">
              Select dimension, then drag to position jewelry in the frame.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Aspect Ratio Selector Tabs */}
        <div className="px-5 py-2.5 bg-white border-b border-gray-100 flex items-center justify-between gap-2">
          <span className="text-xs font-bold text-gray-700 uppercase">Image Size:</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setSelectedPreset("1080x1080");
                setCrop({ x: 0, y: 0 });
                setZoom(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition border flex items-center gap-1.5 ${
                selectedPreset === "1080x1080"
                  ? "bg-[#25D366]/10 text-emerald-800 border-[#25D366] shadow-xs"
                  : "bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100"
              }`}
            >
              <span className="w-2.5 h-2.5 rounded-xs border border-current"></span>
              Square (1080 × 1080)
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedPreset("1200x900");
                setCrop({ x: 0, y: 0 });
                setZoom(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition border flex items-center gap-1.5 ${
                selectedPreset === "1200x900"
                  ? "bg-[#25D366]/10 text-emerald-800 border-[#25D366] shadow-xs"
                  : "bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100"
              }`}
            >
              <span className="w-3.5 h-2.5 rounded-xs border border-current"></span>
              Landscape 4:3 (1200 × 900)
            </button>
          </div>
        </div>

        {/* Cropper area */}
        <div className="relative w-full h-72 sm:h-84 bg-gray-900">
          <Cropper
            image={imageSrc}
            crop={crop}
            zoom={zoom}
            aspect={currentAspect}
            onCropChange={onCropChange}
            onZoomChange={onZoomChange}
            onCropComplete={handleCropAreaChange}
            showGrid={true}
          />
        </div>

        {/* Zoom Controls */}
        <div className="px-6 py-2.5 bg-gray-50 border-t border-gray-200 flex items-center gap-4">
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
        <div className="px-6 py-3 bg-white border-t border-gray-100 flex items-center justify-between">
          <div className="text-[11px] text-gray-500 font-mono">
            Output: <span className="font-bold text-gray-700">{targetDims.width} × {targetDims.height} px</span>
          </div>
          <div className="flex items-center gap-2">
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
              {isProcessing ? "Processing..." : `Crop & Use (${targetDims.width}×${targetDims.height})`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

