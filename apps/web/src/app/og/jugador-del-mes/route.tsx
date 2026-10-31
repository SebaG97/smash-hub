import { apiBase, type Art } from "../../../lib/og";
import {
  pictureSlot,
  playerOfMonthImage,
  type MonthData,
} from "../../../lib/og-player-of-month";
import { readUploads } from "../../../lib/og-uploads";

/** Players of a month (?month=YYYY-MM, the latest by default), for social media. */
export async function GET(request: Request) {
  return image(request);
}

/** Same image with pictures uploaded by an organizer (form fields image-<row>). */
export async function POST(request: Request) {
  const uploads = await readUploads(request, pictureSlot);
  if (uploads instanceof Response) return uploads;
  return image(request, uploads);
}

async function image(request: Request, uploads?: Map<number, Art>) {
  const month = new URL(request.url).searchParams.get("month");
  const only = month && /^\d{4}-\d{2}$/.test(month) ? `?month=${month}` : "";
  const data = (await fetch(
    `${apiBase(request)}/insights/player-of-month${only}`,
  )
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null)) as MonthData | null;
  if (!data?.regions.some((r) => r.winner))
    return new Response("Ese mes no tiene jugador del mes", { status: 404 });
  return playerOfMonthImage(data, uploads);
}
