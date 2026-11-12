import type { Metadata, Viewport } from "next";
import Link from "next/link";
import Script from "next/script";
import { AdminBadge } from "../components/admin-panel";
import { AccountBadge } from "../components/account";
import { Logo } from "../components/logo";
import { NavLinks } from "../components/nav-links";
import { InstallListener } from "../components/pwa";
import { EARLY_PROMPT_SCRIPT } from "../lib/install";
import { APP_BACKGROUND } from "./manifest";
import { siteOrigin } from "../lib/previews";
import "./globals.css";

const description =
  "Ranking, torneos y mains de la escena de Smash Ultimate en Paraguay.";

// viewport-fit=cover lets the installed app use the whole screen; body pads the
// notch and home-indicator areas back (globals.css, safe areas).
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: APP_BACKGROUND,
};

export async function generateMetadata(): Promise<Metadata> {
  // Absolute URLs for link previews, from the host the visitor used.
  const origin = await siteOrigin();
  return {
    metadataBase: new URL(origin),
    title: {
      default: "Smash Club Paraguay",
      template: "%s | Smash Club Paraguay",
    },
    description,
    applicationName: "Smash Hub",
    icons: {
      icon: "/smashclublogo.jpg",
      apple: { url: "/icons/apple-touch-icon.png", sizes: "180x180" },
    },
    // iPhone: open full screen from the home screen, with a dark status bar.
    appleWebApp: { capable: true, title: "Smash Hub", statusBarStyle: "black" },
    openGraph: {
      siteName: "Smash Club Paraguay",
      title: "Smash Club Paraguay",
      description,
      locale: "es_PY",
      type: "website",
      images: [
        { url: `${origin}/smashclublogo.jpg`, alt: "Smash Club Paraguay" },
      ],
    },
    twitter: { card: "summary" },
  };
}
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <head>
        {/* Big Shoulders Display: sports signage; Atkinson Hyperlegible: readable text. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin=""
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Big+Shoulders+Display:wght@700;800;900&display=swap"
        />
        {/* Keeps Chromium's one-time install offer if it arrives before hydration. */}
        <Script id="install-offer" strategy="beforeInteractive">
          {EARLY_PROMPT_SCRIPT}
        </Script>
      </head>
      <body>
        <a href="#contenido" className="skip-link">
          Saltar al contenido
        </a>
        <header className="site-header">
          <Link
            href="/"
            className="brand"
            aria-label="Smash Club Paraguay, inicio"
          >
            <Logo size={52} className="brand-logo" />
            <span>Smash Club Paraguay</span>
          </Link>
          <NavLinks />
          <AccountBadge />
          <AdminBadge />
        </header>
        <main id="contenido">{children}</main>
        <InstallListener />
        <footer>
          <Link className="footer-brand" href="/">
            Smash Club Paraguay
            <span>
              Para la comunidad de Smash de Paraguay. Desarrollado por
              SegirSistems
            </span>
          </Link>
          <Link href="/admin" className="footer-admin">
            Organizadores
          </Link>
        </footer>
      </body>
    </html>
  );
}
