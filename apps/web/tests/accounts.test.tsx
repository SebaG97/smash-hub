import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
} from "@testing-library/react";
import {
  AccountBadge,
  AccountPage,
  ForgotForm,
  RegisterForm,
  ResetForm,
  SignInForm,
} from "../src/components/account";
import { LinkAdmin, UserAdmin } from "../src/components/admin-accounts";
import {
  adminHeaders,
  clearAdmin,
  saveAdmin,
  useAdmin,
} from "../src/lib/admin";
import { safeNext, setMe, type Me, type SessionUser } from "../src/lib/session";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  push.mockReset();
  clearAdmin();
});

function user(extra: Partial<SessionUser> = {}): SessionUser {
  return {
    id: "u1",
    username: "ana",
    display_name: "Ana",
    name: "Ana",
    role: "user",
    email: "ana@example.com",
    player: null,
    ...extra,
  };
}

function me(u: SessionUser | null, extra: Partial<Me> = {}): Me {
  return {
    user: u,
    legacy_admin_key: false,
    ...extra,
  };
}

type Call = { url: string; init?: RequestInit };

function serve(answer: (call: Call) => { status?: number; body: unknown }) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      const { status = 200, body } = answer({ url, init });
      return new Response(status === 204 ? null : JSON.stringify(body), {
        status,
      });
    }),
  );
  return calls;
}

describe("sign-up and sign-in", () => {
  it("checks the passwords match before asking the API", () => {
    const calls = serve(() => ({ body: {} }));
    render(<RegisterForm />);
    fireEvent.change(screen.getByLabelText(/^Usuario/), {
      target: { value: "Ana" },
    });
    fireEvent.change(screen.getByLabelText(/^Correo/), {
      target: { value: "ana@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^Contraseña/), {
      target: { value: "una frase bastante larga" },
    });
    fireEvent.change(screen.getByLabelText("Repetí la contraseña"), {
      target: { value: "otra cosa distinta" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(screen.getByRole("alert")).toHaveTextContent("no coinciden");
    expect(calls).toHaveLength(0);
  });

  it("creates the account with the hub's header and the cookie", async () => {
    const calls = serve(() => ({ status: 201, body: me(user()) }));
    render(<RegisterForm next="/prode" />);
    fireEvent.change(screen.getByLabelText(/^Usuario/), {
      target: { value: "Ana" },
    });
    fireEvent.change(screen.getByLabelText(/^Correo/), {
      target: { value: "ana@example.com" },
    });
    for (const label of [/^Contraseña/, "Repetí la contraseña"])
      fireEvent.change(screen.getByLabelText(label), {
        target: { value: "una frase bastante larga" },
      });
    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/prode"));
    const [call] = calls;
    expect(call.url).toMatch(/auth\/register$/);
    expect(call.init?.credentials).toBe("include");
    expect(
      (call.init?.headers as Record<string, string>)["X-Requested-With"],
    ).toBe("smashhub");
    expect(JSON.parse(String(call.init?.body))).toEqual({
      username: "ana",
      email: "ana@example.com",
      password: "una frase bastante larga",
    });
    // Nothing about the session is stored in the page.
    expect(localStorage.length).toBe(0);
  });

  it("shows the API's answer for a wrong password and stays", async () => {
    serve(() => ({
      status: 401,
      body: { detail: "Usuario o contraseña incorrectos." },
    }));
    render(<SignInForm next="https://evil.example" />);
    fireEvent.change(screen.getByLabelText("Usuario o correo"), {
      target: { value: "ana" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "no es" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Usuario o contraseña incorrectos.",
    );
    expect(push).not.toHaveBeenCalled();
  });

  it("never sends people to another site after signing in", async () => {
    serve(() => ({ body: me(user()) }));
    render(<SignInForm next="//evil.example" />);
    fireEvent.change(screen.getByLabelText("Usuario o correo"), {
      target: { value: "ana" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "una frase bastante larga" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    for (const unsafe of ["https://x.example", "//x", "/\\x", undefined])
      expect(safeNext(unsafe)).toBe("/");
    expect(safeNext("/previa/cs#prode")).toBe("/previa/cs#prode");
  });
});

describe("password recovery", () => {
  it("sends people to an administrator for a one-time link", () => {
    render(<ForgotForm />);
    expect(screen.getByText(/enlace de recuperación/)).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).toBeNull(); // nothing is sent anywhere
  });

  it("sends the token from the fragment and clears it from the address", async () => {
    window.history.replaceState(null, "", "/recuperar/nueva#token=abc123token");
    const calls = serve(() => ({ status: 204, body: null }));
    render(<ResetForm />);
    expect(window.location.hash).toBe("");
    for (const label of [/^Contraseña nueva/, "Repetila"])
      fireEvent.change(screen.getByLabelText(label), {
        target: { value: "mi frase nueva y larga" },
      });
    fireEvent.click(screen.getByRole("button", { name: "Guardar contraseña" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Listo");
    const reset = calls.find((c) => c.url.endsWith("auth/password/reset"))!;
    expect(JSON.parse(String(reset.init?.body))).toEqual({
      token: "abc123token",
      password: "mi frase nueva y larga",
    });
  });
});

describe("header and account page", () => {
  it("offers to sign in, and the admin tools only to organizers", () => {
    const { rerender } = render(<AccountBadge />);
    expect(screen.getByRole("link", { name: "Ingresar" })).toBeInTheDocument();
    for (const [role, staff] of [
      ["user", false],
      ["admin", true],
      ["superadmin", true],
    ] as const) {
      setMe(me(user({ role })));
      rerender(<AccountBadge />);
      const button = screen.getByRole("button", { name: "Mi perfil: Ana" });
      expect(button).toHaveAttribute("aria-expanded", "false");
      expect(screen.queryByRole("link", { name: "Mi cuenta" })).toBeNull();
      fireEvent.click(button);
      expect(button).toHaveAttribute("aria-expanded", "true");
      expect(screen.getByRole("link", { name: "Mi cuenta" })).toHaveAttribute(
        "href",
        "/cuenta",
      );
      expect(screen.getByText("@ana")).toBeInTheDocument();
      const admin = screen.queryByRole("link", { name: "Administración" });
      if (staff) expect(admin).toHaveAttribute("href", "/admin");
      else expect(admin).toBeNull();
      fireEvent.click(button);
      expect(button).toHaveAttribute("aria-expanded", "false");
    }
  });

  it("closes the user menu with Escape, a click outside or a link", () => {
    setMe(me(user()));
    render(
      <>
        <AccountBadge />
        <p>afuera</p>
      </>,
    );
    const button = screen.getByRole("button", { name: "Mi perfil: Ana" });
    fireEvent.click(button);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveFocus();
    fireEvent.click(button);
    fireEvent.pointerDown(screen.getByText("afuera"));
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    // jsdom cannot navigate; the menu only has to close.
    document.addEventListener("click", (e) => e.preventDefault(), {
      once: true,
    });
    fireEvent.click(screen.getByRole("link", { name: "Mi cuenta" }));
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("signs out from the user menu", async () => {
    setMe(me(user()));
    const calls = serve(() => ({ status: 204, body: null }));
    render(<AccountBadge />);
    fireEvent.click(screen.getByRole("button", { name: "Mi perfil: Ana" }));
    fireEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));
    expect(
      await screen.findByRole("link", { name: "Ingresar" }),
    ).toBeInTheDocument();
    expect(calls.some((c) => c.url.endsWith("auth/logout"))).toBe(true);
  });

  it("shows the verification code of a pending link request", async () => {
    setMe(me(user()));
    serve(({ url }) =>
      url.endsWith("links/mine")
        ? {
            body: {
              player: null,
              requests: [
                {
                  id: "r1",
                  player: { id: "p1", tag: "Chag" },
                  status: "pending",
                  code: "SH-AB12CD",
                  evidence: "Mi start.gg",
                  created_at: null,
                  review_note: null,
                },
              ],
            },
          }
        : { body: { open: 1 } },
    );
    render(<AccountPage />);
    expect(await screen.findByText("SH-AB12CD")).toBeInTheDocument();
    expect(screen.getByText(/Pediste vincularte con/)).toHaveTextContent(
      "Chag",
    );
  });
});

describe("organizer access", () => {
  it("uses the session for administrators and the key only when typed", () => {
    setMe(me(user({ role: "admin", username: "org" })));
    const { result } = renderHook(() => useAdmin());
    expect(result.current).toEqual({ name: "org", role: "admin" });
    expect(adminHeaders(result.current)).toEqual({
      "X-Requested-With": "smashhub",
    });
    setMe(me(null));
    saveAdmin({ key: "k", name: "Org" });
    const legacy = renderHook(() => useAdmin()).result.current;
    expect(legacy).toEqual({ key: "k", name: "Org", role: "legacy" });
    expect(adminHeaders(legacy)).toEqual({
      "X-Requested-With": "smashhub",
      Authorization: "Bearer k",
      "X-Admin-Name": "Org",
    });
  });

  it("keeps the admin screens closed to accounts without the role", () => {
    setMe(me(user()));
    serve(() => ({ body: [] }));
    render(<LinkAdmin />);
    expect(screen.getByRole("alert")).toHaveTextContent("no tiene permiso");
    cleanup();
    setMe(me(user({ role: "admin" })));
    render(<UserAdmin />);
    expect(screen.getByRole("alert")).toHaveTextContent("no tiene permiso");
  });

  it("lists pending requests for administrators to review", async () => {
    setMe(me(user({ role: "admin", username: "org" })));
    serve(({ url }) =>
      url.includes("link-requests")
        ? {
            body: [
              {
                id: "r1",
                player: { id: "p1", tag: "Chag" },
                user: { id: "u9", username: "beto", display_name: "Beto" },
                code: "SH-XY34ZW",
                evidence: "start.gg/user/chag",
                created_at: "2026-11-10T12:00:00Z",
              },
            ],
          }
        : { body: [] },
    );
    render(<LinkAdmin />);
    expect(await screen.findByText("@beto → Chag")).toBeInTheDocument();
    const approve = screen.getByRole("button", { name: "Aprobar" });
    expect(approve).toBeDisabled(); // until the reviewer says how they checked
    fireEvent.change(screen.getByLabelText("Cómo lo comprobaste"), {
      target: { value: "El código está en su bio de start.gg" },
    });
    expect(approve).toBeEnabled();
  });
});
