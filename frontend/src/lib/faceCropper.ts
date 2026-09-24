export interface CropRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ProcessedPhotoResult {
  file: File;
  previewUrl: string;
  originalWidth: number;
  originalHeight: number;
  crop: CropRect;
  gender: "male" | "female" | "unknown";
  genderConfidence: number;
  faceDetected: boolean;
}

const ASPECT_RATIO = 4 / 5; // Standard 4:5 Instagram Portrait Ratio

let modelsLoaded = false;
let modelLoadingPromise: Promise<void> | null = null;

/**
 * Loads face-api.js models from local public/models directory.
 */
export async function loadFaceModels(modelUrl = "/models"): Promise<void> {
  if (modelsLoaded) return;
  if (modelLoadingPromise) return modelLoadingPromise;

  modelLoadingPromise = (async () => {
    try {
      const faceapi = await import("face-api.js");

      // Load SSD MobileNet V1 face detector and AgeGender model
      await Promise.all([
        faceapi.nets.ssdMobilenetv1.loadFromUri(modelUrl),
        faceapi.nets.ageGenderNet.loadFromUri(modelUrl),
      ]);

      modelsLoaded = true;
    } catch (err) {
      console.warn("Could not load local face models, falling back to CDN:", err);
      try {
        const faceapi = await import("face-api.js");
        const cdnUrl = "https://raw.githubusercontent.com/justadudewhohacks/face-api.js/master/weights";
        await Promise.all([
          faceapi.nets.ssdMobilenetv1.loadFromUri(cdnUrl),
          faceapi.nets.ageGenderNet.loadFromUri(cdnUrl),
        ]);
        modelsLoaded = true;
      } catch (fallbackErr) {
        console.error("Failed to load face detection models:", fallbackErr);
      }
    }
  })();

  return modelLoadingPromise;
}

/**
 * Heuristic fallback crop when no face is detected or detection is bypassed.
 * Centers a 4:5 rectangle in the upper third of the photo.
 */
export function heuristicCrop(imageWidth: number, imageHeight: number): CropRect {
  let cropWidth = Math.round(imageWidth * 0.7);
  let cropHeight = Math.round(cropWidth / ASPECT_RATIO);

  if (cropHeight > imageHeight) {
    cropHeight = imageHeight;
    cropWidth = Math.round(cropHeight * ASPECT_RATIO);
  }

  const x = Math.round((imageWidth - cropWidth) / 2);
  const y = Math.round(imageHeight * 0.08);
  const clampedY = Math.min(y, imageHeight - cropHeight);

  return {
    x: Math.max(0, x),
    y: Math.max(0, clampedY),
    width: Math.min(cropWidth, imageWidth),
    height: Math.min(cropHeight, imageHeight),
  };
}

/**
 * Loads an image File into an HTMLImageElement in memory.
 */
function loadImageFromFile(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = (e) => {
      URL.revokeObjectURL(url);
      reject(e);
    };
    img.src = url;
  });
}

/**
 * Automatically detects the face, crops to headshot (4:5 ratio),
 * detects gender, and returns the cropped File and metadata.
 */
export async function autoCropAndDetectFace(file: File): Promise<ProcessedPhotoResult> {
  const imgEl = await loadImageFromFile(file);
  const naturalWidth = imgEl.naturalWidth || imgEl.width;
  const naturalHeight = imgEl.naturalHeight || imgEl.height;

  let crop: CropRect = heuristicCrop(naturalWidth, naturalHeight);
  let gender: "male" | "female" | "unknown" = "unknown";
  let genderConfidence = 0;
  let faceDetected = false;

  try {
    await loadFaceModels();
    const faceapi = await import("face-api.js");

    if (faceapi.nets.ssdMobilenetv1.isLoaded) {
      // Detect single face with age & gender
      const result: any = await faceapi
        .detectSingleFace(imgEl)
        .withAgeAndGender();

      if (result && result.detection && result.detection.box) {
        const box = result.detection.box;
        faceDetected = true;

        // 1.65x expansion captures hair, chin, and top collar nicely
        let cropWidth = Math.round(box.width * 1.65);
        let cropHeight = Math.round(cropWidth / ASPECT_RATIO);

        if (cropWidth > naturalWidth || cropHeight > naturalHeight) {
          cropHeight = naturalHeight;
          cropWidth = Math.round(cropHeight * ASPECT_RATIO);
          if (cropWidth > naturalWidth) {
            cropWidth = naturalWidth;
            cropHeight = Math.round(cropWidth / ASPECT_RATIO);
          }
        }

        const rawX = Math.round(box.x + box.width / 2 - cropWidth / 2);
        // Position face in top 35-40% of portrait for pleasing headshot composition
        const rawY = Math.round(box.y - cropHeight * 0.18);

        const clampedX = Math.max(0, Math.min(rawX, naturalWidth - cropWidth));
        const clampedY = Math.max(0, Math.min(rawY, naturalHeight - cropHeight));

        crop = {
          x: clampedX,
          y: clampedY,
          width: cropWidth,
          height: cropHeight,
        };

        if (result.gender) {
          gender = result.gender.toLowerCase() as "male" | "female";
          genderConfidence = Math.round((result.genderProbability || 0) * 100);
        }
      }
    }
  } catch (err) {
    console.warn("Face detection failed, using heuristic crop:", err);
  }

  // Draw crop onto an offscreen canvas and export cropped JPEG
  const canvas = document.createElement("canvas");
  // Target clean resolution for AI likeness (864 x 1080)
  canvas.width = 864;
  canvas.height = 1080;
  const ctx = canvas.getContext("2d");

  if (!ctx) {
    throw new Error("Unable to create canvas context for cropping.");
  }

  // Smooth image rendering
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";

  ctx.drawImage(
    imgEl,
    crop.x,
    crop.y,
    crop.width,
    crop.height,
    0,
    0,
    canvas.width,
    canvas.height
  );

  const croppedBlob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob);
        else reject(new Error("Failed to export canvas blob"));
      },
      "image/jpeg",
      0.95
    );
  });

  const baseName = file.name.replace(/\.[^/.]+$/, "");
  const croppedFile = new File([croppedBlob], `${baseName}_crop.jpg`, {
    type: "image/jpeg",
  });
  const previewUrl = URL.createObjectURL(croppedBlob);

  return {
    file: croppedFile,
    previewUrl,
    originalWidth: naturalWidth,
    originalHeight: naturalHeight,
    crop,
    gender,
    genderConfidence,
    faceDetected,
  };
}
