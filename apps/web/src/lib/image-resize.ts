/**
 * Downscale a captured image client-side before upload.
 *
 * Phone cameras emit 4–12 MB full-res JPEGs that blow past the server upload
 * caps and slow the double send (Vision analysis + photo upload) on tablet
 * Wi-Fi. Resale shots, the 1200 px storefront canvas, and Claude Vision never
 * need more than a couple thousand pixels, so we redraw to a bounded longest
 * side and re-encode as JPEG.
 *
 * EXIF orientation is honoured (createImageBitmap with imageOrientation, or the
 * browser's default <img> orientation) so portrait phone shots aren't rotated.
 *
 * Best-effort: on any failure (decode error, no canvas) the original file is
 * returned so capture is never blocked.
 */

interface DownscaleOptions {
  maxDim?: number;
  quality?: number;
}

const DEFAULT_MAX_DIM = 2000;
const DEFAULT_QUALITY = 0.82;
// Below this, a small image is already fine — skip the needless re-encode.
const SKIP_BELOW_BYTES = 1.5 * 1024 * 1024;

export async function downscaleImage(
  file: File,
  { maxDim = DEFAULT_MAX_DIM, quality = DEFAULT_QUALITY }: DownscaleOptions = {},
): Promise<File> {
  if (typeof document === 'undefined') return file;
  if (!file.type.startsWith('image/')) return file;

  try {
    const source = await loadDrawable(file);
    if (!source) return file;

    const { width, height } = source;
    const scale = Math.min(1, maxDim / Math.max(width, height));

    // Already small in both dimensions and bytes → keep the original.
    if (scale >= 1 && file.size <= SKIP_BELOW_BYTES) {
      source.cleanup();
      return file;
    }

    const w = Math.max(1, Math.round(width * scale));
    const h = Math.max(1, Math.round(height * scale));
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      source.cleanup();
      return file;
    }
    ctx.drawImage(source.image, 0, 0, w, h);
    source.cleanup();

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', quality),
    );
    if (!blob || blob.size === 0) return file;

    const baseName = file.name.replace(/\.[^./\\]+$/, '') || 'photo';
    return new File([blob], `${baseName}.jpg`, {
      type: 'image/jpeg',
      lastModified: Date.now(),
    });
  } catch {
    return file;
  }
}

interface Drawable {
  image: CanvasImageSource;
  width: number;
  height: number;
  cleanup: () => void;
}

async function loadDrawable(file: File): Promise<Drawable | null> {
  // Preferred: createImageBitmap honours EXIF orientation and decodes off the
  // main thread. Not all engines accept the options bag, so guard it.
  if (typeof createImageBitmap === 'function') {
    try {
      const bitmap = await createImageBitmap(file, {
        imageOrientation: 'from-image',
      } as ImageBitmapOptions);
      return {
        image: bitmap,
        width: bitmap.width,
        height: bitmap.height,
        cleanup: () => bitmap.close(),
      };
    } catch {
      // fall through to the <img> path
    }
  }

  // Fallback: decode via an <img> + object URL.
  return new Promise<Drawable | null>((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () =>
      resolve({
        image: img,
        width: img.naturalWidth,
        height: img.naturalHeight,
        cleanup: () => URL.revokeObjectURL(url),
      });
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(null);
    };
    img.src = url;
  });
}
