"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  apiFetch,
  errorText,
  isStaff,
  signInHref,
  useMe,
  type Role,
} from "../lib/session";
import { usePlayerSearch } from "./account";

/* Administration of accounts and player links (Mission SH-AUTH-01, ADR-021). Every
   permission is checked again by the API; these screens only hide what is not yours. */

type Account = {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  email: string | null;
  disabled: boolean;
  can_sign_in: boolean;
  last_login_at: string | null;
  player: { id: string; tag: string } | null;
};
type Request = {
  id: string;
  player: { id: string; tag: string };
  user: { id: string; username: string; display_name: string };
  code: string;
  evidence: string;
  created_at: string | null;
};
type ActiveLink = {
  id: string;
  user: { id: string; username: string; display_name: string };
  player: { id: string; tag: string };
  method: "request" | "admin" | "startgg_legacy";
  verification: string;
  linked_by: string;
  linked_at: string | null;
};

const METHODS = {
  request: "solicitud",
  admin: "asignación directa",
  startgg_legacy: "ingreso con start.gg",
};

function day(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString("es-PY") : "—";
}

function useJson<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) return;
    let active = true;
    apiFetch(path)
      .then(async (r) => {
        if (!active) return;
        setStatus(r.status);
        setData(r.ok ? ((await r.json()) as T) : null);
      })
      .catch(() => active && setStatus(0));
    return () => {
      active = false;
    };
  }, [path, tick]);
  return { data, status, reload: useCallback(() => setTick((t) => t + 1), []) };
}

async function post(path: string, body: object, method = "POST") {
  const r = await apiFetch(path, {
    method,
    body: JSON.stringify(body),
  }).catch(() => null);
  if (!r) return "No se pudo contactar a la API.";
  return r.ok ? null : errorText(r);
}

/** Who may see an admin screen; the API checks again on every call. */
function Gate({
  role,
  children,
}: {
  role: "staff" | "superadmin";
  children: React.ReactNode;
}) {
  const me = useMe();
  if (!me) return <p role="status">Cargando…</p>;
  if (!me.user)
    return (
      <p>
        <Link className="primary-button" href={signInHref()}>
          Ingresar
        </Link>
      </p>
    );
  const allowed =
    role === "superadmin" ? me.user.role === "superadmin" : isStaff(me.user);
  if (!allowed)
    return <p role="alert">Tu cuenta no tiene permiso para ver esta página.</p>;
  return <>{children}</>;
}

function RequestCard({
  request,
  onDone,
}: {
  request: Request;
  onDone: () => void;
}) {
  const [verification, setVerification] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function act(path: string, body: object) {
    setBusy(true);
    setError("");
    const problem = await post(path, body);
    setBusy(false);
    if (problem) return setError(problem);
    onDone();
  }
  return (
    <article className="account-card">
      <h3>
        @{request.user.username} → {request.player.tag}
      </h3>
      <p className="seeding-lead">
        {request.user.display_name} · pedida el {day(request.created_at)} ·
        código <strong className="account-code">{request.code}</strong>
      </p>
      <blockquote>{request.evidence}</blockquote>
      <p className="seeding-lead">
        Comprobá que el código aparece donde solo el jugador puede ponerlo (bio
        de start.gg, Discord) o confirmalo en persona. Que el usuario se parezca
        al tag no prueba nada.
      </p>
      <label>
        Cómo lo comprobaste
        <input
          value={verification}
          maxLength={500}
          placeholder="Ej.: el código está en su bio de start.gg"
          onChange={(e) => setVerification(e.target.value)}
        />
      </label>
      <div className="seeding-actions">
        <button
          className="primary-button"
          disabled={busy || verification.trim().length < 10}
          onClick={() =>
            void act(`admin/link-requests/${request.id}/approve`, {
              verification,
            })
          }
        >
          Aprobar
        </button>
        <input
          value={note}
          maxLength={500}
          placeholder="Motivo del rechazo"
          aria-label="Motivo del rechazo"
          onChange={(e) => setNote(e.target.value)}
        />
        <button
          className="link-button"
          disabled={busy || note.trim().length < 5}
          onClick={() =>
            void act(`admin/link-requests/${request.id}/reject`, { note })
          }
        >
          Rechazar
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
    </article>
  );
}

function DirectLink({ onDone }: { onDone: () => void }) {
  const [userQ, setUserQ] = useState("");
  const [user, setUser] = useState<Account | null>(null);
  const [player, setPlayer] = useState<{ id: string; tag: string } | null>(
    null,
  );
  const [verification, setVerification] = useState("");
  const [replace, setReplace] = useState(false);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const players = usePlayerSearch("admin/players");
  const users = useJson<Account[]>(
    userQ.trim().length >= 2
      ? `admin/users?q=${encodeURIComponent(userQ.trim())}`
      : null,
  );
  return (
    <form
      className="account-form account-wide"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!user || !player) return setMessage("Elegí la cuenta y la ficha.");
        const problem = await post("admin/links", {
          user_id: user.id,
          player_id: player.id,
          verification,
          replace,
          reason: replace ? reason : null,
        });
        if (problem) return setMessage(problem);
        setMessage(`Vinculaste @${user.username} con ${player.tag}.`);
        setUser(null);
        setPlayer(null);
        setVerification("");
        setReplace(false);
        setReason("");
        onDone();
      }}
    >
      <label>
        Cuenta
        <input
          value={user ? `@${user.username}` : userQ}
          maxLength={60}
          placeholder="Usuario o nombre"
          onChange={(e) => {
            setUser(null);
            setUserQ(e.target.value);
          }}
        />
      </label>
      {!user && userQ.trim().length >= 2 && (
        <ul className="account-results">
          {(users.data ?? []).map((u) => (
            <li key={u.id}>
              <button
                type="button"
                className="link-button"
                onClick={() => setUser(u)}
              >
                @{u.username}
              </button>{" "}
              <small>
                {u.display_name}
                {u.player ? ` · ya vinculada a ${u.player.tag}` : ""}
              </small>
            </li>
          ))}
        </ul>
      )}
      <label>
        Ficha de jugador
        <input
          value={player ? player.tag : players.q}
          maxLength={60}
          placeholder="Tag"
          onChange={(e) => {
            setPlayer(null);
            players.setQ(e.target.value);
          }}
        />
      </label>
      {!player && players.found.length > 0 && (
        <ul className="account-results">
          {players.found.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className="link-button"
                onClick={() => setPlayer(p)}
              >
                {p.tag}
              </button>
              {p.linked && <small> · ya vinculada</small>}
            </li>
          ))}
        </ul>
      )}
      <label>
        Cómo comprobaste que es esa persona
        <input
          value={verification}
          maxLength={500}
          required
          onChange={(e) => setVerification(e.target.value)}
        />
      </label>
      <label className="seeding-check">
        <input
          type="checkbox"
          checked={replace}
          onChange={(e) => setReplace(e.target.checked)}
        />
        Reemplazar una vinculación existente de la cuenta o de la ficha
      </label>
      {replace && (
        <label>
          Motivo del reemplazo (queda en el historial)
          <input
            value={reason}
            maxLength={500}
            required
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
      )}
      <button className="primary-button" type="submit">
        Vincular
      </button>
      {message && <p role="status">{message}</p>}
    </form>
  );
}

function ActiveLinks({ version }: { version: number }) {
  const [q, setQ] = useState("");
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const links = useJson<ActiveLink[]>(
    `admin/links?q=${encodeURIComponent(q.trim())}&v=${version}`,
  );
  return (
    <>
      <label className="account-filter">
        Filtrar por usuario o tag
        <input
          value={q}
          maxLength={60}
          onChange={(e) => setQ(e.target.value)}
        />
      </label>
      {error && <p role="alert">{error}</p>}
      {links.data && links.data.length === 0 && (
        <p className="seeding-lead">No hay vinculaciones.</p>
      )}
      <ul className="account-list">
        {(links.data ?? []).map((l) => (
          <li key={l.id}>
            <span>
              <strong>@{l.user.username}</strong> ↔{" "}
              <Link href={`/players/${l.player.id}`}>{l.player.tag}</Link>
              <small>
                {" "}
                · {METHODS[l.method]} por {l.linked_by} el {day(l.linked_at)} ·{" "}
                {l.verification}
              </small>
            </span>
            <span className="account-inline">
              <input
                value={reasons[l.id] ?? ""}
                maxLength={500}
                placeholder="Motivo"
                aria-label={`Motivo para desvincular a @${l.user.username}`}
                onChange={(e) =>
                  setReasons((r) => ({ ...r, [l.id]: e.target.value }))
                }
              />
              <button
                className="link-button"
                disabled={(reasons[l.id] ?? "").trim().length < 5}
                onClick={async () => {
                  setError("");
                  const problem = await post(`admin/links/${l.id}/unlink`, {
                    reason: reasons[l.id],
                  });
                  if (problem) return setError(problem);
                  links.reload();
                }}
              >
                Desvincular
              </button>
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

/** /admin/vinculaciones */
export function LinkAdmin() {
  const [version, setVersion] = useState(0);
  const requests = useJson<Request[]>(`admin/link-requests?v=${version}`);
  const done = () => setVersion((v) => v + 1);
  return (
    <Gate role="staff">
      <section className="account-section" aria-labelledby="pendientes">
        <h2 id="pendientes">Solicitudes pendientes</h2>
        {requests.data === null ? (
          <p role="status">Cargando…</p>
        ) : requests.data.length === 0 ? (
          <p className="seeding-lead">No hay solicitudes pendientes.</p>
        ) : (
          requests.data.map((r) => (
            <RequestCard key={r.id} request={r} onDone={done} />
          ))
        )}
      </section>
      <section className="account-section" aria-labelledby="directa">
        <h2 id="directa">Vincular directamente</h2>
        <p className="seeding-lead">
          Para quien no puede pedirlo o ya comprobaste en persona. Nadie puede
          vincular su propia cuenta.
        </p>
        <DirectLink onDone={done} />
      </section>
      <section className="account-section" aria-labelledby="activas">
        <h2 id="activas">Vinculaciones activas</h2>
        <p className="seeding-lead">
          Desvincular no borra pronósticos ni logros: siguen en la cuenta.
        </p>
        <ActiveLinks version={version} />
      </section>
    </Gate>
  );
}

type Status = {
  roles: Record<Role, number>;
  legacy_admin_key: {
    configured: boolean;
    active: boolean;
    expires_at: string | null;
    last_used_at: string | null;
  };
};
type AuditRow = {
  at: string;
  action: string;
  actor: string;
  target: string | null;
  details: Record<string, unknown>;
};

function UserRow({
  account,
  self,
  onChange,
}: {
  account: Account;
  self: boolean;
  onChange: () => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [link, setLink] = useState<{ url: string; expires_at: string } | null>(
    null,
  );
  async function run(path: string, body: object, method = "PUT") {
    setError("");
    const problem = await post(path, body, method);
    if (problem) return setError(problem);
    onChange();
  }
  return (
    <li className={account.disabled ? "account-disabled" : undefined}>
      <span>
        <strong>@{account.username}</strong> {account.display_name}
        <small>
          {" "}
          · {account.email ?? "sin correo"}
          {account.player ? ` · ${account.player.tag}` : ""} · último ingreso{" "}
          {day(account.last_login_at)}
          {account.disabled ? " · desactivada" : ""}
        </small>
      </span>
      {self ? (
        <small>(tu cuenta)</small>
      ) : (
        <span className="account-inline">
          <select
            value={account.role}
            aria-label={`Rol de @${account.username}`}
            disabled={!account.can_sign_in}
            onChange={(e) =>
              void run(`admin/users/${account.id}/role`, {
                role: e.target.value,
              })
            }
          >
            <option value="user">Usuario</option>
            <option value="admin">Administrador</option>
            <option value="superadmin">Superadministrador</option>
          </select>
          <input
            value={reason}
            maxLength={500}
            placeholder="Motivo"
            aria-label={`Motivo para @${account.username}`}
            onChange={(e) => setReason(e.target.value)}
          />
          <button
            className="link-button"
            disabled={!account.disabled && reason.trim().length < 5}
            onClick={() =>
              void run(`admin/users/${account.id}/status`, {
                disabled: !account.disabled,
                reason,
              })
            }
          >
            {account.disabled ? "Reactivar" : "Desactivar"}
          </button>
          <button
            className="link-button"
            onClick={() =>
              void run(`admin/users/${account.id}/sessions/revoke`, {}, "POST")
            }
          >
            Cerrar sesiones
          </button>
          {account.can_sign_in && !account.disabled && (
            <button
              className="link-button"
              onClick={async () => {
                setError("");
                const r = await apiFetch(
                  `admin/users/${account.id}/password-reset`,
                  { method: "POST" },
                ).catch(() => null);
                if (!r) return setError("No se pudo contactar a la API.");
                if (!r.ok) return setError(await errorText(r));
                setLink(
                  (await r.json()) as { url: string; expires_at: string },
                );
              }}
            >
              Enlace de recuperación
            </button>
          )}
        </span>
      )}
      {link && (
        <p className="account-reset" role="status">
          Pasale este enlace por un canal de confianza; sirve una vez y vence el{" "}
          {new Date(link.expires_at).toLocaleString("es-PY")}. No se vuelve a
          mostrar:
          <code>{link.url}</code>
        </p>
      )}
      {error && <p role="alert">{error}</p>}
    </li>
  );
}

/** /admin/usuarios (superadmins). */
export function UserAdmin() {
  const me = useMe();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [version, setVersion] = useState(0);
  const users = useJson<Account[]>(
    `admin/users?q=${encodeURIComponent(q.trim())}${role ? `&role=${role}` : ""}&v=${version}`,
  );
  const status = useJson<Status>(
    me?.user?.role === "superadmin" ? `admin/status?v=${version}` : null,
  );
  const audit = useJson<AuditRow[]>(
    me?.user?.role === "superadmin"
      ? `admin/audit?limit=50&v=${version}`
      : null,
  );
  const legacy = status.data?.legacy_admin_key;
  return (
    <Gate role="superadmin">
      {status.data && legacy && (
        <section className="account-section" aria-labelledby="transicion">
          <h2 id="transicion">Estado</h2>
          <p>
            {status.data.roles.superadmin} superadministradores,{" "}
            {status.data.roles.admin} administradores y {status.data.roles.user}{" "}
            usuarios activos. Las contraseñas se recuperan con enlaces que emite
            un superadministrador.
          </p>
          <p className={legacy.active ? "seeding-banner" : "seeding-lead"}>
            Clave compartida de organizadores:{" "}
            {legacy.active
              ? `todavía se acepta, hasta el ${new Date(legacy.expires_at!).toLocaleString("es-PY")}`
              : legacy.configured
                ? "ya no se acepta"
                : "retirada"}
            . Último uso: {day(legacy.last_used_at)}.
            {legacy.active &&
              " Cuando cada organizador tenga su cuenta, quitá ADMIN_TOKEN y ADMIN_TOKEN_EXPIRES de la API."}
          </p>
        </section>
      )}
      <section className="account-section" aria-labelledby="cuentas">
        <h2 id="cuentas">Cuentas y roles</h2>
        <div className="account-inline">
          <label className="account-filter">
            Buscar
            <input
              value={q}
              maxLength={60}
              placeholder="Usuario, nombre o correo"
              onChange={(e) => setQ(e.target.value)}
            />
          </label>
          <label className="account-filter">
            Rol
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="">Todos</option>
              <option value="user">Usuarios</option>
              <option value="admin">Administradores</option>
              <option value="superadmin">Superadministradores</option>
            </select>
          </label>
        </div>
        <p className="seeding-lead">
          Cambiar el rol o desactivar una cuenta cierra sus sesiones. Cada
          administrador usa su propia cuenta: no compartan credenciales.
        </p>
        <ul className="account-list">
          {(users.data ?? []).map((u) => (
            <UserRow
              key={u.id}
              account={u}
              self={u.id === me?.user?.id}
              onChange={() => setVersion((v) => v + 1)}
            />
          ))}
        </ul>
      </section>
      {audit.data && (
        <section className="account-section" aria-labelledby="registro">
          <h2 id="registro">Registro</h2>
          <ul className="account-list account-audit">
            {audit.data.map((row, i) => (
              <li key={`${row.at}-${i}`}>
                <span>
                  <small>{new Date(row.at).toLocaleString("es-PY")}</small>{" "}
                  <strong>{row.actor}</strong> {row.action}
                  {row.target ? ` → @${row.target}` : ""}
                  {typeof row.details.path === "string"
                    ? ` · ${row.details.method} ${row.details.path}`
                    : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </Gate>
  );
}
