"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <section className="empty-state" role="alert">
      <h1>No pudimos cargar esta página.</h1>
      <p>Intenta nuevamente en unos instantes.</p>
      <button className="primary-button" onClick={reset}>
        Reintentar
      </button>
    </section>
  );
}
