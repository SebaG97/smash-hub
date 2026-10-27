import { seedingImage } from "../../../../lib/og-seeding";
import { readUploads } from "../../../../lib/og-uploads";

type Params = { params: Promise<{ slug: string }> };

export async function GET(request: Request, { params }: Params) {
  return seedingImage(request, (await params).slug);
}

/** Same image with pictures uploaded by an organizer (form fields image-<row>). */
export async function POST(request: Request, { params }: Params) {
  const uploads = await readUploads(request);
  if (uploads instanceof Response) return uploads;
  return seedingImage(request, (await params).slug, uploads);
}
