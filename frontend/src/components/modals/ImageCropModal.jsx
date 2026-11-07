import React, { useState, useCallback } from "react";
import Cropper from "react-easy-crop";
import { X, Check, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";
import { getCroppedImg } from "../../utils/cropImage";

export default function ImageCropModal({
  isOpen,
  imageSrc,
  title = "Crop & Center Product Image",
  aspect = 1.91, // default
  initialPreset = "1125x600",
  onClose,
  onCropComplete: onConfirmCrop
}) {
  // Preset ratios: Meta Standard 1.91:1 (1125x600) and Square 1:1 (1080x1080)
  const [selectedPreset, setSelectedPreset] = useState(initialPreset || "1125x600");
  const [bgMode, setBgMode] = useState("white"); // "white" | "blur"
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Sync initialPreset when modal opens or prop changes
  React.useEffect(() => {
    if (initialPreset) {
      setSelectedPreset(initialPreset);
    }
  }, [initialPreset, isOpen]);

  const currentAspect = selectedPreset === "1080x1080" ? 1 : (1125 / 600);
  const targetDims = selectedPreset === "1080x1080" ? { width: 1080, height: 1080 } : { width: 1125, height: 600 };

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
      // If imageSrc is a remote URL or server path (recropping existing card), send crop parameters to server
      if (typeof imageSrc === "string" && (imageSrc.startsWith("http") || imageSrc.startsWith("/uploads/"))) {
        await onConfirmCrop({
          type: "server_crop",
          image_url: imageSrc,
          crop: croppedAreaPixels,
          target_width: targetDims.width,
          target_height: targetDims.height,
          preset: selectedPreset,
          bg_mode: bgMode
        });
      } else {
        // If imageSrc is a freshly picked local data URL (FileReader), canvas crop in browser is 100% untainted
        const croppedBlob = await getCroppedImg(
          imageSrc,
          croppedAreaPixels,
          targetDims.width,
          targetDims.height,
          bgMode
        );
        croppedBlob.preset = selectedPreset;
        croppedBlob.bg_mode = bgMode;
        await onConfirmCrop(croppedBlob);
      }
      onClose();
    } catch (e) {
      console.error("Crop error:", e);
      const msg = e?.response?.data?.detail || e?.message || (typeof e === "string" ? e : JSON.stringify(e)) || "Unknown error";
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

        {/* Aspect Ratio & Background Padding Controls */}
        <div className="px-5 py-2.5 bg-white border-b border-gray-100 flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Ratio:</span>
            <button
              type="button"
              onClick={() => {
                setSelectedPreset("1125x600");
                setCrop({ x: 0, y: 0 });
                setZoom(1);
              }}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition border flex items-center gap-1.5 ${
                selectedPreset === "1125x600"
                  ? "bg-[#25D366]/10 text-emerald-800 border-[#25D366] shadow-xs"
                  : "bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100"
              }`}
            >
              <span className="w-3.5 h-2 rounded-xs border border-current"></span>
              Meta 1.91:1
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedPreset("1080x1080");
                setCrop({ x: 0, y: 0 });
                setZoom(1);
              }}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition border flex items-center gap-1.5 ${
                selectedPreset === "1080x1080"
                  ? "bg-[#25D366]/10 text-emerald-800 border-[#25D366] shadow-xs"
                  : "bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100"
              }`}
            >
              <span className="w-2.5 h-2.5 rounded-xs border border-current"></span>
              Square 1:1
            </button>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Sides:</span>
            <button
              type="button"
              onClick={() => setBgMode("white")}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition border ${
                bgMode === "white"
                  ? "bg-emerald-50 text-emerald-800 border-emerald-400 shadow-xs"
                  : "bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100"
              }`}
              title="Clean white background padding"
            >
              White Sides
            </button>
            <button
              type="button"
              onClick={() => setBgMode("blur")}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition border ${
                bgMode === "blur"
                  ? "bg-purple-50 text-purple-800 border-purple-400 shadow-xs"
                  : "bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100"
              }`}
              title="Blurred photo background padding"
            >
              Blurred Sides
            </button>
          </div>
        </div>

        {/* Cropper area */}
        <div
          className="relative w-full h-72 sm:h-84 overflow-hidden border-y border-gray-200"
          style={{
            backgroundColor: "#f0f2f5",
            backgroundImage: `
              linear-gradient(45deg, #e4e7eb 25%, transparent 25%),
              linear-gradient(-45deg, #e4e7eb 25%, transparent 25%),
              linear-gradient(45deg, transparent 75%, #e4e7eb 75%),
              linear-gradient(-45deg, transparent 75%, #e4e7eb 75%)
            `,
            backgroundSize: "16px 16px",
            backgroundPosition: "0 0, 0 8px, 8px -8px, -8px 0px"
          }}
        >
          <Cropper
            image={imageSrc}
            crop={crop}
            zoom={zoom}
            minZoom={0.5}
            maxZoom={3}
            restrictPosition={false}
            aspect={currentAspect}
            onCropChange={onCropChange}
            onZoomChange={onZoomChange}
            onCropComplete={handleCropAreaChange}
            showGrid={true}
            style={{
              containerStyle: {
                backgroundColor: "transparent"
              }
            }}
          />
        </div>

        {/* Zoom Controls */}
        <div className="px-6 py-2.5 bg-gray-50 border-t border-gray-200 flex items-center gap-4">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.5, z - 0.2))}
            className="p-1 text-gray-500 hover:text-gray-700"
            title="Zoom out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <input
            type="range"
            value={zoom}
            min={0.5}
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
              setZoom(0.55);
              setCrop({ x: 0, y: 0 });
            }}
            className="text-[11px] text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 px-2 py-1 rounded-md flex items-center gap-1 shrink-0 ml-1 font-bold transition shadow-2xs"
            title="Automatically scale to fit the entire full photo with side padding"
          >
            Fit Entire Photo
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

