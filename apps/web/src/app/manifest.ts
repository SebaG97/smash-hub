import type { MetadataRoute } from "next";
import { publicOrigin } from "../lib/install";

/** Concrete grey of the club logo (--concrete in globals.css). */
export const APP_BACKGROUND = "#26221f";

/**
 * Web app manifest (SH-PWA-01), served at /manifest.webmanifest. Static: the same for
 * every visitor, with no user data or query parameters.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Smash Hub",
    short_name: "Smash Hub",
    description:
      "Ranking, torneos, Prode y logros de la escena de Smash Ultimate en Paraguay.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: APP_BACKGROUND,
    theme_color: APP_BACKGROUND,
    lang: "es",
    dir: "ltr",
    categories: ["games", "sports"],
    // Lets Chromium tell an already installed app (getInstalledRelatedApps) without
    // offering a native store app instead.
    prefer_related_applications: false,
    related_applications: [
      { platform: "webapp", url: `${publicOrigin()}/manifest.webmanifest` },
    ],
    icons: [
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
