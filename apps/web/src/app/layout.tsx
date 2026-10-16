import type { Metadata } from "next";
import Link from "next/link";
import { modules } from "../lib/modules";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "Smash PY Hub · La comunidad nos mueve",
    template: "%s · Smash PY Hub",
  },
  description:
    "El punto de encuentro de la comunidad competitiva de Smash en Paraguay.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>
        <a href="#contenido" className="skip-link">
          Saltar al contenido
        </a>
        <header className="site-header">
          <Link href="/" className="brand" aria-label="Smash PY Hub, inicio">
            <span className="brand-icon" aria-hidden="true">
              S<span>↗</span>
            </span>
            <span>
              SMASH <b>PY</b>
              <small>COMMUNITY HUB</small>
            </span>
          </Link>
          <nav aria-label="Navegación principal">
            {modules.map((m) => (
              <Link key={m.slug} href={`/${m.slug}`}>
                {m.title}
              </Link>
            ))}
          </nav>
          <span className="country-badge">
            PY <span aria-hidden="true">●</span> Paraguay
          </span>
        </header>
        <main id="contenido">{children}</main>
        <footer>
          <Link className="footer-brand" href="/">
            SMASH PY HUB<span>Una comunidad. Muchas historias.</span>
          </Link>
          <p>Hecho para la escena, desde Paraguay.</p>
          <span className="version">FUNDACIÓN · V0.1</span>
        </footer>
      </body>
    </html>
  );
}
