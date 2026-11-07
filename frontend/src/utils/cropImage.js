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

  // Fill with white background in case of transparent edges
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(0, 0, outputWidth, outputHeight);

  // Draw image based on cropped area
  ctx.drawImage(
    image,
    pixelCrop.x,
    pixelCrop.y,
    pixelCrop.width,
    pixelCrop.height,
    0,
    0,
    outputWidth,
    outputHeight
  );

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

