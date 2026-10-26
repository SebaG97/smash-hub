import Link from "next/link";
import { notFound } from "next/navigation";
import { modules } from "../../lib/modules";
export function generateStaticParams() {
  return modules
    .filter(
      (m) =>
        !["players", "tournaments", "estadisticas", "seeding"].includes(m.slug),
    )
    .map((m) => ({ module: m.slug }));
}
export default async function ModulePage({
  params,
}: {
  params: Promise<{ module: string }>;
}) {
  const { module } = await params;
  const item = modules.find((m) => m.slug === module);
  if (!item) notFound();
  return (
    <section className="empty-state">
      <p className="eyebrow">EL HUB ESTÁ CRECIENDO · {item.number}</p>
      <h1>{item.title}</h1>
      <p>{item.description}</p>
      <div className="empty-panel">
        <span aria-hidden="true">↗</span>
        <h2>El próximo capítulo está en camino.</h2>
        <p>
          Este módulo todavía no está implementado. Aquí aparecerán datos
          verificados cuando se habilite su funcionalidad.
        </p>
        <Link className="primary-button" href="/">
          Volver al inicio
        </Link>
      </div>
    </section>
  );
}
