"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
  type FormEvent,
} from "react";
import {
  type SessionUser,
  apiFetch,
  errorText,
  isStaff,
  login,
  logout,
  refreshMe,
  register,
  safeNext,
  signInHref,
  useMe,
} from "../lib/session";
import { MyAchievements } from "./achievements";

/* Smash Hub accounts (Mission SH-AUTH-01, ADR-021): header badge, sign-in, sign-up,
   password recovery and the account page with the player-link request. */

const MIN_PASSWORD = 10;

/** Header: sign in, or the user menu (Mission SH-UI-01). */
export function AccountBadge() {
  const me = useMe();
  if (!me) return null;
  if (!me.user)
    return (
      <span className="user-badge">
        <Link href={signInHref()}>Ingresar</Link>
      </span>
    );
  return <UserMenu user={me.user} />;
}

function UserIcon() {
  return (
    <svg
      className="user-menu-icon"
      viewBox="0 0 24 24"
      width="20"
      height="20"
      aria-hidden="true"
      focusable="false"
    >
      <circle
        cx="12"
        cy="8"
        r="4"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * The signed-in user's menu: a disclosure button with the account, the admin tools for
 * organizers and sign-out. Opens with click, tap, Enter or Space; Escape, a click outside
 * or following a link closes it.
 */
function UserMenu({ user }: { user: SessionUser }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  useEffect(() => {
    if (!open) return;
    function outside(e: PointerEvent | FocusEvent) {
      if (root.current && !root.current.contains(e.target as Node))
        setOpen(false);
    }
    function key(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      setOpen(false);
      button.current?.focus();
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("focusin", outside);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("focusin", outside);
      document.removeEventListener("keydown", key);
    };
  }, [open]);
  const close = () => setOpen(false);
  return (
    <div className="user-menu" ref={root}>
      <button
        ref={button}
        type="button"
        className="user-menu-button"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((o) => !o)}
      >
        <UserIcon />
        <span className="visually-hidden">Mi perfil: </span>
        <span className="user-menu-name">{user.display_name}</span>
        <svg
          className="user-menu-caret"
          viewBox="0 0 12 12"
          width="12"
          height="12"
          aria-hidden="true"
          focusable="false"
        >
          <path
            d="M2 4.5 6 8.5 10 4.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <div className="user-menu-panel" id={menuId} hidden={!open}>
        <p className="user-menu-who">
          <strong>{user.display_name}</strong>
          <small>@{user.username}</small>
        </p>
        <ul>
          <li>
            <Link href="/cuenta" onClick={close}>
              Mi cuenta
            </Link>
          </li>
          {isStaff(user) && (
            <li>
              <Link href="/admin" className="user-badge-admin" onClick={close}>
                Administración
              </Link>
            </li>
          )}
          <li>
            <button
              type="button"
              onClick={() => {
                close();
                void logout();
              }}
            >
              Cerrar sesión
            </button>
          </li>
        </ul>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  ...input
}: {
  label: string;
  hint?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label>
      {label}
      <input {...input} />
      {hint && <small>{hint}</small>}
    </label>
  );
}

/** /ingresar */
export function SignInForm({ next }: { next?: string }) {
  const me = useMe();
  const router = useRouter();
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const target = safeNext(next);
  if (me?.user)
    return (
      <p>
        Ya ingresaste como <strong>{me.user.display_name}</strong>.{" "}
        <Link href={target}>Seguir →</Link>
      </p>
    );
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const problem = await login(name.trim(), password);
    setBusy(false);
    if (problem) return setError(problem);
    router.push(target);
  }
  return (
    <form className="account-form" onSubmit={submit}>
      <Field
        label="Usuario o correo"
        value={name}
        autoComplete="username"
        maxLength={254}
        required
        onChange={(e) => setName(e.target.value)}
      />
      <Field
        label="Contraseña"
        type="password"
        value={password}
        autoComplete="current-password"
        maxLength={200}
        required
        onChange={(e) => setPassword(e.target.value)}
      />
      <button className="primary-button" type="submit" disabled={busy}>
        {busy ? "Ingresando…" : "Ingresar"}
      </button>
      {error && <p role="alert">{error}</p>}
      <p className="account-links">
        <Link href={`/registro?next=${encodeURIComponent(target)}`}>
          Crear una cuenta
        </Link>
        <Link href="/recuperar">Olvidé mi contraseña</Link>
      </p>
    </form>
  );
}

/** /registro */
export function RegisterForm({ next }: { next?: string }) {
  const me = useMe();
  const router = useRouter();
  const [fields, setFields] = useState({
    username: "",
    display_name: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const target = safeNext(next ?? "/cuenta");
  const set =
    (key: keyof typeof fields) => (e: React.ChangeEvent<HTMLInputElement>) =>
      setFields((f) => ({ ...f, [key]: e.target.value }));
  if (me?.user)
    return (
      <p>
        Ya tenés una cuenta: <Link href="/cuenta">{me.user.display_name}</Link>.
      </p>
    );
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (fields.password.length < MIN_PASSWORD)
      return setError(
        `La contraseña necesita al menos ${MIN_PASSWORD} caracteres.`,
      );
    if (fields.password !== fields.confirm)
      return setError("Las contraseñas no coinciden.");
    setBusy(true);
    const problem = await register({
      username: fields.username.trim().toLowerCase(),
      email: fields.email.trim(),
      password: fields.password,
      display_name: fields.display_name.trim() || undefined,
    });
    setBusy(false);
    if (problem) return setError(problem);
    router.push(target);
  }
  return (
    <form className="account-form" onSubmit={submit}>
      <Field
        label="Usuario"
        hint="De 3 a 30 caracteres: letras, números, punto, guion o guion bajo. Con él ingresás."
        value={fields.username}
        autoComplete="username"
        pattern="[A-Za-z0-9_.\-]{3,30}"
        maxLength={30}
        required
        onChange={set("username")}
      />
      <Field
        label="Nombre visible (opcional)"
        hint="Como te ven en el ranking del Prode. Podés cambiarlo después."
        value={fields.display_name}
        maxLength={40}
        onChange={set("display_name")}
      />
      <Field
        label="Correo"
        hint="Para recuperar la contraseña. No se muestra a nadie."
        type="email"
        value={fields.email}
        autoComplete="email"
        maxLength={254}
        required
        onChange={set("email")}
      />
      <Field
        label="Contraseña"
        hint={`Al menos ${MIN_PASSWORD} caracteres. Una frase es más fácil de recordar.`}
        type="password"
        value={fields.password}
        autoComplete="new-password"
        minLength={MIN_PASSWORD}
        maxLength={128}
        required
        onChange={set("password")}
      />
      <Field
        label="Repetí la contraseña"
        type="password"
        value={fields.confirm}
        autoComplete="new-password"
        maxLength={128}
        required
        onChange={set("confirm")}
      />
      <button className="primary-button" type="submit" disabled={busy}>
        {busy ? "Creando…" : "Crear cuenta"}
      </button>
      {error && <p role="alert">{error}</p>}
      <p className="account-links">
        <Link href={signInHref(target)}>Ya tengo cuenta</Link>
      </p>
    </form>
  );
}

/** /recuperar: there is no e-mail yet, so a superadmin issues a one-time link. */
export function ForgotForm() {
  return (
    <div className="prode-login">
      <p>
        Pedile a un administrador de la comunidad (por el Discord o en persona)
        que te genere un enlace de recuperación.
      </p>
      <p>
        Te lo va a pasar por un canal de confianza. Sirve una sola vez, durante
        24 horas, y al usarlo se cierran todas las sesiones abiertas de tu
        cuenta. Nadie del hub te va a pedir tu contraseña.
      </p>
    </div>
  );
}

/** /recuperar/nueva#token=…: the token travels in the fragment, never to a server log. */
let resetToken: string | null = null;
function readResetToken() {
  resetToken ??=
    new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
  return resetToken;
}

export function ResetForm() {
  const token = useSyncExternalStore(
    () => () => {},
    readResetToken,
    () => null,
  );
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    // Out of the address bar (and history) once read.
    if (token && window.location.hash)
      window.history.replaceState(null, "", window.location.pathname);
  }, [token]);
  if (token === null) return <p role="status">Cargando…</p>;
  if (done)
    return (
      <p role="status">
        Listo, ya podés <Link href={signInHref("/cuenta")}>ingresar</Link> con
        la contraseña nueva. Cerramos todas las sesiones abiertas de tu cuenta.
      </p>
    );
  if (!token)
    return (
      <p role="alert">
        Este enlace no es válido. <Link href="/recuperar">Pedí uno nuevo</Link>.
      </p>
    );
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) return setError("Las contraseñas no coinciden.");
    setBusy(true);
    const r = await apiFetch("auth/password/reset", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }).catch(() => null);
    setBusy(false);
    if (!r) return setError("No se pudo contactar a la API.");
    if (!r.ok) return setError(await errorText(r));
    refreshMe();
    setDone(true);
  }
  return (
    <form className="account-form" onSubmit={submit}>
      <Field
        label="Contraseña nueva"
        hint={`Al menos ${MIN_PASSWORD} caracteres.`}
        type="password"
        value={password}
        autoComplete="new-password"
        minLength={MIN_PASSWORD}
        maxLength={128}
        required
        onChange={(e) => setPassword(e.target.value)}
      />
      <Field
        label="Repetila"
        type="password"
        value={confirm}
        autoComplete="new-password"
        maxLength={128}
        required
        onChange={(e) => setConfirm(e.target.value)}
      />
      <button className="primary-button" type="submit" disabled={busy}>
        Guardar contraseña
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}

type LinkRequest = {
  id: string;
  player: { id: string; tag: string };
  status: "pending" | "approved" | "rejected" | "cancelled";
  code: string;
  evidence: string;
  created_at: string | null;
  review_note: string | null;
};
type Mine = {
  player: { id: string; tag: string } | null;
  requests: LinkRequest[];
};
type FoundPlayer = { id: string; tag: string; linked: boolean };

const REQUEST_STATUS: Record<LinkRequest["status"], string> = {
  pending: "Pendiente de revisión",
  approved: "Aprobada",
  rejected: "Rechazada",
  cancelled: "Cancelada",
};

/** Search player records by tag (2+ letters), for a link request or an admin link. */
export function usePlayerSearch(path: string) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<FoundPlayer[]>([]);
  useEffect(() => {
    const text = q.trim();
    if (text.length < 2) return;
    let active = true;
    const timer = setTimeout(() => {
      apiFetch(`${path}?q=${encodeURIComponent(text)}`)
        .then((r) => (r.ok ? (r.json() as Promise<FoundPlayer[]>) : []))
        .then((rows) => active && setFound(rows))
        .catch(() => active && setFound([]));
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [q, path]);
  return { q, setQ, found: q.trim().length < 2 ? [] : found };
}

function LinkSection() {
  const [mine, setMine] = useState<Mine | null>(null);
  const [chosen, setChosen] = useState<FoundPlayer | null>(null);
  const [evidence, setEvidence] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const search = usePlayerSearch("links/players");
  useEffect(() => {
    apiFetch("links/mine")
      .then((r) => (r.ok ? (r.json() as Promise<Mine>) : null))
      .then(setMine)
      .catch(() => setMine(null));
  }, []);
  if (!mine) return <p role="status">Cargando…</p>;
  const pending = mine.requests.find((r) => r.status === "pending");

  async function send(path: string, init: RequestInit) {
    setBusy(true);
    setError("");
    const r = await apiFetch(path, init).catch(() => null);
    setBusy(false);
    if (!r) return setError("No se pudo contactar a la API.");
    if (!r.ok) return setError(await errorText(r));
    setMine((await r.json()) as Mine);
    setChosen(null);
    setEvidence("");
    refreshMe();
  }

  return (
    <>
      {mine.player ? (
        <p>
          Tu cuenta está vinculada a{" "}
          <Link href={`/players/${mine.player.id}`}>
            <strong>{mine.player.tag}</strong>
          </Link>
          . Tus logros del Prode también se ven en esa ficha. Si hay un error,
          hablá con un administrador.
        </p>
      ) : pending ? (
        <div className="prode-login">
          <p>
            Pediste vincularte con <strong>{pending.player.tag}</strong>. Un
            administrador lo va a revisar.
          </p>
          <p>
            Tu código de verificación es{" "}
            <strong className="account-code">{pending.code}</strong>. Ponelo en
            la bio de tu perfil de start.gg o mostráselo a un administrador por
            el Discord de la comunidad o en persona: así comprueba que la ficha
            es tuya.
          </p>
          <button
            className="link-button"
            disabled={busy}
            onClick={() =>
              void send(`links/requests/${pending.id}`, { method: "DELETE" })
            }
          >
            Cancelar la solicitud
          </button>
        </div>
      ) : (
        <form
          className="account-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!chosen) return setError("Elegí tu ficha de la lista.");
            void send("links/requests", {
              method: "POST",
              body: JSON.stringify({ player_id: chosen.id, evidence }),
            });
          }}
        >
          <p className="seeding-lead">
            Si competís, pedí vincular tu cuenta con tu ficha de jugador. No
            hace falta para jugar el Prode.
          </p>
          <Field
            label="Buscá tu tag"
            value={search.q}
            maxLength={60}
            onChange={(e) => {
              search.setQ(e.target.value);
              setChosen(null);
            }}
          />
          {search.found.length > 0 && !chosen && (
            <ul className="account-results">
              {search.found.map((p) => (
                <li key={p.id}>
                  {p.linked ? (
                    <span>
                      {p.tag} <small>(ya vinculada)</small>
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => setChosen(p)}
                    >
                      {p.tag}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {chosen && (
            <>
              <p>
                Ficha elegida: <strong>{chosen.tag}</strong>{" "}
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setChosen(null)}
                >
                  cambiar
                </button>
              </p>
              <label>
                ¿Cómo podemos comprobar que sos vos?
                <textarea
                  value={evidence}
                  maxLength={1000}
                  rows={3}
                  required
                  placeholder="Tu perfil de start.gg, tu usuario de Discord, en qué torneo te podemos ver…"
                  onChange={(e) => setEvidence(e.target.value)}
                />
              </label>
              <button className="primary-button" type="submit" disabled={busy}>
                Pedir vinculación
              </button>
            </>
          )}
        </form>
      )}
      {error && <p role="alert">{error}</p>}
      {mine.requests.some((r) => r.status !== "pending") && (
        <details className="account-history">
          <summary>Solicitudes anteriores</summary>
          <ul>
            {mine.requests
              .filter((r) => r.status !== "pending")
              .map((r) => (
                <li key={r.id}>
                  {r.player.tag}: {REQUEST_STATUS[r.status]}
                  {r.review_note && r.status === "rejected"
                    ? ` (${r.review_note})`
                    : ""}
                </li>
              ))}
          </ul>
        </details>
      )}
    </>
  );
}

function ProfileSection({ name }: { name: string }) {
  const [displayName, setDisplayName] = useState(name);
  const [message, setMessage] = useState("");
  return (
    <form
      className="account-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setMessage("");
        const r = await apiFetch("auth/me", {
          method: "PUT",
          body: JSON.stringify({ display_name: displayName.trim() }),
        }).catch(() => null);
        if (!r) return setMessage("No se pudo contactar a la API.");
        if (!r.ok) return setMessage(await errorText(r));
        refreshMe();
        setMessage("Guardado.");
      }}
    >
      <Field
        label="Nombre visible"
        value={displayName}
        maxLength={40}
        required
        onChange={(e) => setDisplayName(e.target.value)}
      />
      <button className="primary-button" type="submit">
        Guardar
      </button>
      {message && <p role="status">{message}</p>}
    </form>
  );
}

function SecuritySection() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [message, setMessage] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  useEffect(() => {
    apiFetch("auth/sessions")
      .then((r) => (r.ok ? (r.json() as Promise<{ open: number }>) : null))
      .then((d) => setOpen(d?.open ?? null))
      .catch(() => setOpen(null));
  }, []);
  return (
    <>
      <form
        className="account-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setMessage("");
          const r = await apiFetch("auth/password", {
            method: "PUT",
            body: JSON.stringify({
              current_password: current,
              new_password: next,
            }),
          }).catch(() => null);
          if (!r) return setMessage("No se pudo contactar a la API.");
          if (!r.ok) return setMessage(await errorText(r));
          setCurrent("");
          setNext("");
          setOpen(1);
          setMessage(
            "Contraseña cambiada. Cerramos tus sesiones en otros dispositivos.",
          );
        }}
      >
        <Field
          label="Contraseña actual"
          type="password"
          value={current}
          autoComplete="current-password"
          maxLength={200}
          required
          onChange={(e) => setCurrent(e.target.value)}
        />
        <Field
          label="Contraseña nueva"
          hint={`Al menos ${MIN_PASSWORD} caracteres.`}
          type="password"
          value={next}
          autoComplete="new-password"
          minLength={MIN_PASSWORD}
          maxLength={128}
          required
          onChange={(e) => setNext(e.target.value)}
        />
        <button className="primary-button" type="submit">
          Cambiar contraseña
        </button>
      </form>
      <p>
        {open === null
          ? null
          : open === 1
            ? "Tenés una sola sesión abierta: esta."
            : `Tenés ${open} sesiones abiertas.`}{" "}
        {open !== null && open > 1 && (
          <button
            className="link-button"
            onClick={async () => {
              const r = await apiFetch("auth/sessions/revoke-others", {
                method: "POST",
              }).catch(() => null);
              if (r?.ok) {
                setOpen(1);
                setMessage("Cerramos las demás sesiones.");
              }
            }}
          >
            Cerrar las demás
          </button>
        )}
      </p>
      {message && <p role="status">{message}</p>}
    </>
  );
}

const ROLE_NAMES = {
  user: "Usuario",
  admin: "Administrador",
  superadmin: "Superadministrador",
};

/** /cuenta */
export function AccountPage() {
  const me = useMe();
  if (!me) return <p role="status">Cargando…</p>;
  if (!me.user)
    return (
      <p>
        <Link className="primary-button" href={signInHref("/cuenta")}>
          Ingresar
        </Link>{" "}
        <Link href="/registro">o creá una cuenta</Link>
      </p>
    );
  const user = me.user;
  return (
    <>
      <p className="seeding-lead">
        <strong>@{user.username}</strong> · {user.email} ·{" "}
        {ROLE_NAMES[user.role]}
        {isStaff(user) && (
          <>
            {" · "}
            <Link href="/admin">Panel de administración</Link>
          </>
        )}
      </p>
      <p>
        <Link href={`/prode/u/${user.id}`}>
          Mis pronósticos y logros del Prode →
        </Link>
      </p>
      <section className="account-section" aria-labelledby="perfil">
        <h2 id="perfil">Perfil</h2>
        <ProfileSection name={user.display_name} />
      </section>
      <section className="account-section" aria-labelledby="jugador">
        <h2 id="jugador">Ficha de jugador</h2>
        <LinkSection />
      </section>
      <section className="account-section" aria-labelledby="logros">
        <h2 id="logros">Logros y vitrina</h2>
        <MyAchievements />
      </section>
      <section className="account-section" aria-labelledby="seguridad">
        <h2 id="seguridad">Seguridad</h2>
        <SecuritySection />
      </section>
    </>
  );
}
