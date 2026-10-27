import type { Metadata } from "next";
import Link from "next/link";
import { AdminBadge } from "../components/admin-panel";
import { Logo } from "../components/logo";
import { NavLinks } from "../components/nav-links";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Smash Club Paraguay",
    template: "%s | Smash Club Paraguay",
  },
  description:
    "Ranking, torneos y mains de la escena de Smash Ultimate en Paraguay.",
  icons: { icon: "/smashclublogo.jpg", apple: "/smashclublogo.jpg" },
};
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
          <AdminBadge />
        </header>
        <main id="contenido">{children}</main>
        <footer>
          <Link className="footer-brand" href="/">
            Smash Club Paraguay
            <span>Hecho por la comunidad de Smash de Paraguay.</span>
          </Link>
          <Link href="/admin" className="footer-admin">
            Organizadores
          </Link>
        </footer>
      </body>
    </html>
  );
}
