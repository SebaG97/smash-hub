import type { MetadataRoute } from "next";

// Without this file /robots.txt fell into the 404 page; organizers' tools stay unindexed.
export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: "*", allow: "/", disallow: "/admin" } };
}
