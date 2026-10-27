"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { modules } from "../lib/modules";

const aliases: Record<string, string[]> = {
  players: ["/players", "/jugadores"],
  tournaments: ["/tournaments", "/torneos", "/events"],
};

/** Main menu; the section being viewed is marked for sight and screen readers. */
export function NavLinks() {
  const path = usePathname() || "/";
  return (
    <nav aria-label="Navegación principal">
      {modules.map((m) => {
        const roots = aliases[m.slug] ?? [`/${m.slug}`];
        const current = roots.some(
          (r) => path === r || path.startsWith(`${r}/`),
        );
        return (
          <Link
            key={m.slug}
            href={`/${m.slug}`}
            aria-current={current ? "page" : undefined}
          >
            {m.title}
          </Link>
        );
      })}
    </nav>
  );
}
