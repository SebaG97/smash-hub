import type { PublicSeedingView } from "./api";
import { apiBase, shareImage } from "./og";

/** Top 12 of a published ranking or seeding; drafts are not public, so they 404. */
export async function seedingImage(request: Request, slug: string) {
  const response = await fetch(
    `${apiBase(request)}/seeding/${encodeURIComponent(slug)}`,
  ).catch(() => null);
  if (!response?.ok) return new Response("No publicado", { status: 404 });
  const view = (await response.json()) as PublicSeedingView;
  if (!view.public) return new Response("No publicado", { status: 404 });
  const ranking = view.kind === "ranking";
  return shareImage(request, {
    title: view.name,
    subtitle: ranking
      ? `Ranking, método ${view.method_label}`
      : "Seeds principales",
    rows: view.seeds.slice(0, 12).map((s) => ({
      place: s.seed,
      tag: s.gamer_tag,
      main: s.mains?.[0]?.character,
      costume: s.mains?.[0]?.costume,
      detail: ranking ? `${s.wins ?? 0}–${s.losses ?? 0}` : undefined,
    })),
  });
}
