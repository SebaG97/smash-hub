import { isCharacterKey } from "../../../../lib/characters";
import {
  RENDER_WIDTHS,
  render,
  type RenderWidth,
} from "../../../../lib/renders";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ key: string; costume: string }> },
) {
  const { key, costume } = await params;
  const n = Number(costume);
  const width = Number(new URL(request.url).searchParams.get("w") ?? 320);
  if (
    !isCharacterKey(key) ||
    !Number.isInteger(n) ||
    n < 1 ||
    n > 8 ||
    !RENDER_WIDTHS.includes(width as RenderWidth)
  )
    return new Response("No encontrado", { status: 404 });
  const result = await render(key, n, width as RenderWidth);
  if (!result) return new Response("No disponible", { status: 502 });
  return new Response(new Uint8Array(result.data), {
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "public, max-age=604800",
    },
  });
}
