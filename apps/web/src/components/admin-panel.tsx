"use client";

import Link from "next/link";
import { clearAdmin, useAdmin } from "../lib/admin";
import { isStaff, signInHref, useMe } from "../lib/session";
import { AdminLogin } from "./seeding-board";
import { SyncPanel } from "./sync-panel";
import { AchievementsAdmin } from "./achievements";

/** /admin: organizers sign in with their own account and reach every tool. */
export function AdminPanel() {
  const me = useMe();
  const admin = useAdmin();
  if (!me) return <p role="status">Cargando…</p>;
  const staff = isStaff(me.user);
  return (
    <div className="competition-page">
      <h1>Panel de administración</h1>
      {!admin ? (
        <>
          {me.user ? (
            <p role="alert">
              Tu cuenta (<strong>@{me.user.username}</strong>) no tiene permisos
              de administración. Si organizás, pedíselo a un superadministrador.
            </p>
          ) : (
            <p>
              <Link className="primary-button" href={signInHref("/admin")}>
                Ingresar con tu cuenta
              </Link>
            </p>
          )}
          {me.legacy_admin_key && (
            <details className="account-history">
              <summary>Clave compartida (transición)</summary>
              <p className="seeding-lead">
                Mientras cada organizador crea su cuenta, la clave anterior
                sigue funcionando por un tiempo limitado. Queda guardada solo en
                esta pestaña.
              </p>
              <AdminLogin />
            </details>
          )}
        </>
      ) : (
        <>
          <p className="seeding-lead">
            {admin.role === "legacy" ? (
              <>
                Entraste con la clave compartida como{" "}
                <strong>{admin.name}</strong>. Va a dejar de funcionar pronto:
                creá tu cuenta y pedí el rol de administrador.
              </>
            ) : (
              <>
                Sesión de <strong>@{admin.name}</strong> (
                {admin.role === "superadmin"
                  ? "superadministrador"
                  : "administrador"}
                ). Cada página muestra sus herramientas y los borradores.
              </>
            )}
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
            <article className="data-card">
              <h3>
                <Link href="/prode">Prode</Link>
              </h3>
              <p>
                Abrir, cerrar y liquidar el Prode desde la pestaña de cada
                torneo en la previa.
              </p>
            </article>
            {staff && (
              <article className="data-card">
                <h3>
                  <Link href="/admin/vinculaciones">Vinculaciones</Link>
                </h3>
                <p>
                  Revisar solicitudes de jugadores y vincular o desvincular
                  cuentas con fichas.
                </p>
              </article>
            )}
            {me.user?.role === "superadmin" && (
              <article className="data-card">
                <h3>
                  <Link href="/admin/usuarios">Usuarios y roles</Link>
                </h3>
                <p>
                  Nombrar administradores, desactivar cuentas, emitir enlaces de
                  recuperación y ver el registro.
                </p>
              </article>
            )}
          </div>
          <SyncPanel />
          <AchievementsAdmin />
          {admin.role === "legacy" && (
            <button className="primary-button" onClick={clearAdmin}>
              Olvidar la clave
            </button>
          )}
        </>
      )}
    </div>
  );
}

/** Header badge, only while the legacy shared key is in use in this tab. */
export function AdminBadge() {
  const admin = useAdmin();
  if (admin?.role !== "legacy") return null;
  return (
    <span className="admin-badge">
      <Link href="/admin">Admin (clave): {admin.name}</Link> ·{" "}
      <button className="link-button" onClick={clearAdmin}>
        Salir
      </button>
    </span>
  );
}
