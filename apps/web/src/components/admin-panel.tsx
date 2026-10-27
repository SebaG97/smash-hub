"use client";

import Link from "next/link";
import { clearAdmin, useAdmin } from "../lib/admin";
import { AdminLogin } from "./seeding-board";

/** /admin: sign in with the organizers' key and reach every tool. */
export function AdminPanel() {
  const admin = useAdmin();
  return (
    <div className="competition-page">
      <h1>Panel de administración</h1>
      {!admin ? (
        <>
          <p className="seeding-lead">
            Entra con la clave de organizadores. Queda guardada solo en esta
            pestaña y se borra al cerrarla.
          </p>
          <AdminLogin />
        </>
      ) : (
        <>
          <p className="seeding-lead">
            Sesión iniciada como <strong>{admin.name}</strong>. Mientras estés
            dentro, cada página muestra sus herramientas y los borradores.
          </p>
          <div className="data-grid">
            <article className="data-card">
              <h3>
                <Link href="/tournaments">Torneos</Link>
              </h3>
              <p>
                Importar torneos de Paraguay desde start.gg y marcar cuáles
                cuentan para el ranking.
              </p>
            </article>
            <article className="data-card">
              <h3>
                <Link href="/seeding">Seeding</Link>
              </h3>
              <p>Crear seedings, ajustar, publicar o despublicar y exportar.</p>
            </article>
            <article className="data-card">
              <h3>
                <Link href="/rankings">Rankings</Link>
              </h3>
              <p>
                Crear rankings, comparar métodos, elegir el oficial y unir IDs.
              </p>
            </article>
          </div>
          <button className="primary-button" onClick={clearAdmin}>
            Salir
          </button>
        </>
      )}
    </div>
  );
}

/** Header badge, only while an organizer is signed in. */
export function AdminBadge() {
  const admin = useAdmin();
  if (!admin) return null;
  return (
    <span className="admin-badge">
      <Link href="/admin">Admin: {admin.name}</Link> ·{" "}
      <button className="link-button" onClick={clearAdmin}>
        Salir
      </button>
    </span>
  );
}
