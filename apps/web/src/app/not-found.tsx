import Link from "next/link";
export default function NotFound() {
  return (
    <section className="empty-state">
      <h1>Página no encontrada</h1>
      <Link href="/" className="primary-button">
        Volver al inicio
      </Link>
    </section>
  );
}
