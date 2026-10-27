import { seedingImage } from "../../../../lib/og-seeding";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ slug: string }> },
) {
  return seedingImage(request, (await params).slug);
}
