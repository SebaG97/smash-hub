import type { Metadata } from "next";
import { headers } from "next/headers";
import { apiFor, originFromHeaders } from "./origin";

/**
 * Link previews (Open Graph) for WhatsApp, Discord and other apps: each page gets a
 * title, a one-line description and its share image, with absolute URLs.
 */
export async function siteOrigin() {
  return originFromHeaders(await headers(), "http://localhost:3000");
}

export async function apiJson<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${apiFor(await siteOrigin())}/${path}`, {
      signal: AbortSignal.timeout(5000),
      next: { revalidate: 300 },
    });
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

export async function preview({
  title,
  description,
  path,
  image,
  square = false,
}: {
  title: string;
  description: string;
  path: string;
  image: string;
  /** Podium images are 1080×1080; player cards are 1200×630. */
  square?: boolean;
}): Promise<Metadata> {
  const origin = await siteOrigin();
  const size = square
    ? { width: 1080, height: 1080 }
    : { width: 1200, height: 630 };
  const images = [{ url: `${origin}${image}`, ...size, alt: title }];
  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `${origin}${path}`,
      siteName: "Smash Club Paraguay",
      locale: "es_PY",
      type: "website",
      images,
    },
    twitter: {
      card: square ? "summary" : "summary_large_image",
      title,
      description,
      images,
    },
  };
}

export function placeText(place: number) {
  return `${place}.º`;
}
