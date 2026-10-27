import sharp from "sharp";
import { apiBase, slotSize, type Art } from "./og";

/**
 * Images organizers upload to replace the render of a place in a share image. They
 * are used only for that image and never stored. Field names: image-<row index>.
 */
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
const FORMATS = new Set(["jpeg", "png", "webp", "gif", "avif"]);

function problem(status: number, message: string) {
  return new Response(message, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

async function isOrganizer(request: Request) {
  const authorization = request.headers.get("authorization");
  if (!authorization) return false;
  const r = await fetch(`${apiBase(request)}/seeding/session`, {
    headers: {
      Authorization: authorization,
      "X-Admin-Name": request.headers.get("x-admin-name") ?? "",
    },
  }).catch(() => null);
  return Boolean(r?.ok);
}

async function prepare(file: File, index: number): Promise<Art> {
  const input = sharp(Buffer.from(await file.arrayBuffer()), {
    limitInputPixels: 50_000_000,
  });
  const meta = await input.metadata();
  if (!meta.format || !FORMATS.has(meta.format)) throw new Error("format");
  const slot = slotSize(index);
  if (meta.hasAlpha) {
    // A cutout (transparent PNG) goes where the render would.
    const { data, info } = await input
      .trim()
      .resize({ width: 640, height: 640, fit: "inside" })
      .png()
      .toBuffer({ resolveWithObject: true });
    return {
      src: `data:image/png;base64,${data.toString("base64")}`,
      width: info.width,
      height: info.height,
    };
  }
  // A photo fills the card, centered on the most interesting area (usually a face).
  const data = await input
    .rotate()
    .resize({ ...slot, fit: "cover", position: sharp.strategy.attention })
    .jpeg({ quality: 88 })
    .toBuffer();
  return {
    src: `data:image/jpeg;base64,${data.toString("base64")}`,
    ...slot,
    fill: true,
  };
}

/** Uploaded images by row index, or an error response. */
export async function readUploads(
  request: Request,
): Promise<Map<number, Art> | Response> {
  if (!(await isOrganizer(request)))
    return problem(401, "Necesitás la clave de organizador.");
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return problem(400, "No se pudieron leer las imágenes.");
  }
  const uploads = new Map<number, Art>();
  for (const [name, value] of form.entries()) {
    const index = Number(/^image-(\d{1,2})$/.exec(name)?.[1] ?? NaN);
    if (!Number.isInteger(index) || index > 11 || typeof value === "string")
      continue;
    if (value.size > MAX_UPLOAD_BYTES)
      return problem(
        413,
        `La imagen de la fila ${index + 1} pesa más de 5 MB.`,
      );
    try {
      uploads.set(index, await prepare(value, index));
    } catch {
      return problem(
        422,
        `La imagen de la fila ${index + 1} no es una imagen válida (JPG, PNG, WebP, GIF o AVIF).`,
      );
    }
  }
  return uploads;
}
