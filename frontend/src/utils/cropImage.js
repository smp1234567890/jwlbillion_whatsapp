/**
 * Helper to produce cropped image Blob from image source and crop coordinates (from react-easy-crop)
 */
export const createImage = (url) =>
  new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = (error) => {
      // If crossOrigin fails or error event triggers, try loading without crossOrigin
      if (image.crossOrigin) {
        const fallback = new Image();
        fallback.onload = () => resolve(fallback);
        fallback.onerror = (err) => reject(new Error("Could not load image"));
        fallback.src = url;
      } else {
        reject(new Error("Could not load image"));
      }
    };
    image.src = url;
  });

export async function getCroppedImg(imageSrc, pixelCrop, outputWidth = 1080, outputHeight = 1080) {
  let image;
  try {
    // If it's a remote URL, fetch as blob first to completely eliminate canvas tainting
    if (typeof imageSrc === "string" && imageSrc.startsWith("http")) {
      const resp = await fetch(imageSrc, { mode: "cors" });
      const blob = await resp.blob();
      const objectUrl = URL.createObjectURL(blob);
      image = await createImage(objectUrl);
    } else {
      image = await createImage(imageSrc);
    }
  } catch (err) {
    image = await createImage(imageSrc);
  }

  const canvas = document.createElement("canvas");
  canvas.width = outputWidth;
  canvas.height = outputHeight;
  const ctx = canvas.getContext("2d");

  // Fill with white background for padded/zoomed out areas
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(0, 0, outputWidth, outputHeight);

  // When restrictPosition is false or zoom < 1, pixelCrop coordinates can extend outside image boundaries.
  // Calculate source clipping rectangle that intersects with actual image dimensions.
  const naturalWidth = image.naturalWidth || image.width;
  const naturalHeight = image.naturalHeight || image.height;

  const srcX = Math.max(0, pixelCrop.x);
  const srcY = Math.max(0, pixelCrop.y);
  const srcRight = Math.min(naturalWidth, pixelCrop.x + pixelCrop.width);
  const srcBottom = Math.min(naturalHeight, pixelCrop.y + pixelCrop.height);

  const srcW = Math.max(0, srcRight - srcX);
  const srcH = Math.max(0, srcBottom - srcY);

  if (srcW > 0 && srcH > 0) {
    const scaleX = outputWidth / pixelCrop.width;
    const scaleY = outputHeight / pixelCrop.height;

    const destX = (srcX - pixelCrop.x) * scaleX;
    const destY = (srcY - pixelCrop.y) * scaleY;
    const destW = srcW * scaleX;
    const destH = srcH * scaleY;

    ctx.drawImage(image, srcX, srcY, srcW, srcH, destX, destY, destW, destH);
  }

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error("Canvas is empty"));
          return;
        }
        resolve(blob);
      },
      "image/jpeg",
      0.95
    );
  });
}

