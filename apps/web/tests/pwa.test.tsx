import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import manifest, { APP_BACKGROUND } from "../src/app/manifest";
import { HomeInstallCard, InstallGuide } from "../src/components/pwa";
import {
  DEFAULT_PUBLIC_ORIGIN,
  EARLY_PROMPT_KEY,
  EARLY_PROMPT_SCRIPT,
  detectPlatform,
  installUrl,
  isInAppBrowser,
  isIosSafari,
  isStandalone,
  validPublicOrigin,
} from "../src/lib/install";
import {
  resetInstallState,
  startInstallListener,
  type BeforeInstallPromptEvent,
} from "../src/lib/pwa";
import { setMe, type SessionUser } from "../src/lib/session";

vi.mock("next/headers", () => ({
  headers: async () =>
    new Headers({ host: "smashclubpy.com", "x-forwarded-proto": "https" }),
}));

const UA = {
  iphone:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
  iphoneChrome:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0 Mobile/15E148 Safari/604.1",
  iphoneInstagram:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 350.0",
  ipad: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
  android:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36",
  windows:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36 Edg/131.0",
};

const user: SessionUser = {
  id: "u1",
  username: "ana",
  display_name: "Ana",
  name: "Ana",
  role: "user",
  email: null,
  player: null,
};

function device(userAgent: string, maxTouchPoints = 0) {
  vi.spyOn(navigator, "userAgent", "get").mockReturnValue(userAgent);
  // jsdom has no maxTouchPoints.
  Object.defineProperty(navigator, "maxTouchPoints", {
    value: maxTouchPoints,
    configurable: true,
  });
}

function displayMode(standalone: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: standalone && query === "(display-mode: standalone)",
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

/** A Chromium install offer whose dialog answers `outcome`. */
function offer(outcome: "accepted" | "dismissed") {
  const event = new Event("beforeinstallprompt", {
    cancelable: true,
  }) as BeforeInstallPromptEvent;
  const prompt = vi.fn(() => Promise.resolve());
  Object.assign(event, {
    prompt,
    userChoice: Promise.resolve({ outcome, platform: "web" }),
  });
  return { event, prompt };
}

let stop: () => void = () => {};
beforeEach(() => {
  resetInstallState();
  displayMode(false);
  stop = startInstallListener();
});
afterEach(() => {
  stop();
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("manifest and metadata", () => {
  it("describes an installable standalone app scoped to the whole site", () => {
    const m = manifest();
    expect(m).toMatchObject({
      id: "/",
      name: "Smash Hub",
      short_name: "Smash Hub",
      start_url: "/",
      scope: "/",
      display: "standalone",
      lang: "es",
      background_color: APP_BACKGROUND,
      theme_color: APP_BACKGROUND,
    });
    expect(APP_BACKGROUND).toBe("#26221f");
    // Nothing personal or dynamic: no query strings anywhere.
    expect(JSON.stringify(m)).not.toMatch(/\?|token|session/i);
    const icons = m.icons ?? [];
    expect(icons.map((i) => `${i.sizes} ${i.purpose}`)).toEqual([
      "192x192 any",
      "512x512 any",
      "512x512 maskable",
    ]);
  });

  it("ships every icon at its declared size", () => {
    const size = (file: string) => {
      const png = readFileSync(join(__dirname, "../public", file));
      expect(png.subarray(1, 4).toString()).toBe("PNG");
      return `${png.readUInt32BE(16)}x${png.readUInt32BE(20)}`;
    };
    for (const icon of manifest().icons ?? [])
      expect(size(icon.src)).toBe(icon.sizes);
    expect(size("/icons/apple-touch-icon.png")).toBe("180x180");
  });

  it("links the manifest's look from the root layout", async () => {
    const layout = await import("../src/app/layout");
    expect(layout.viewport).toMatchObject({
      themeColor: APP_BACKGROUND,
      viewportFit: "cover",
    });
    const meta = await layout.generateMetadata();
    expect(meta.appleWebApp).toMatchObject({
      capable: true,
      title: "Smash Hub",
    });
    expect(meta.icons).toMatchObject({
      apple: { url: "/icons/apple-touch-icon.png", sizes: "180x180" },
    });
  });
});

describe("public install URL", () => {
  it("defaults to the public domain's install page", () => {
    expect(installUrl(undefined)).toBe("https://smashclubpy.com/install");
    expect(DEFAULT_PUBLIC_ORIGIN).toBe("https://smashclubpy.com");
  });

  it("uses a configured origin only when it is a bare secure origin", () => {
    expect(installUrl("https://beta.smashclubpy.com/")).toBe(
      "https://beta.smashclubpy.com/install",
    );
    expect(validPublicOrigin("http://localhost:3000")).toBe(
      "http://localhost:3000",
    );
    for (const bad of [
      "http://smashclubpy.com",
      "javascript:alert(1)",
      "https://user:pw@smashclubpy.com",
      "https://smashclubpy.com/x",
      "https://smashclubpy.com/?next=//evil.com",
      "https://smashclubpy.com/#token",
      "not a url",
      "",
    ]) {
      expect(validPublicOrigin(bad)).toBeNull();
      expect(installUrl(bad)).toBe("https://smashclubpy.com/install");
    }
  });

  it("reads NEXT_PUBLIC_SITE_URL by default", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://smash.example.org");
    expect(installUrl()).toBe("https://smash.example.org/install");
  });
});

describe("device and standalone detection", () => {
  it("tells iPhone, iPad, Android and computers apart", () => {
    expect(detectPlatform(UA.iphone)).toBe("ios");
    expect(detectPlatform(UA.ipad, 5)).toBe("ios");
    expect(detectPlatform(UA.ipad, 0)).toBe("desktop");
    expect(detectPlatform(UA.android)).toBe("android");
    expect(detectPlatform(UA.windows)).toBe("desktop");
  });

  it("knows which iPhone browsers can add to the home screen", () => {
    expect(isIosSafari(UA.iphone)).toBe(true);
    expect(isIosSafari(UA.iphoneChrome)).toBe(false);
    expect(isIosSafari(UA.iphoneInstagram)).toBe(false);
    expect(isInAppBrowser(UA.iphoneInstagram)).toBe(true);
    expect(isInAppBrowser(UA.android)).toBe(false);
  });

  it("detects the installed app by display mode or iOS's flag", () => {
    expect(isStandalone(undefined)).toBe(false);
    displayMode(true);
    expect(isStandalone(window)).toBe(true);
    displayMode(false);
    expect(isStandalone(window)).toBe(false);
    const ios = {
      navigator: { standalone: true },
    } as unknown as Window;
    expect(isStandalone(ios)).toBe(true);
  });
});

describe("home install block", () => {
  it("is only for signed-in visitors", () => {
    render(<HomeInstallCard />);
    expect(screen.queryByText("Smash Hub en tu celular")).toBeNull();
  });

  it("shows the QR of the public install page and a link for this device", () => {
    device(UA.iphone);
    setMe({ user, legacy_admin_key: false });
    render(<HomeInstallCard />);
    const block = screen.getByRole("region", {
      name: "Smash Hub en tu celular",
    });
    expect(within(block).getByText(/sin descargar un APK/)).toBeInTheDocument();
    const qr = within(block).getByRole("img", {
      name: "Código QR para abrir https://smashclubpy.com/install",
    });
    expect(qr.getAttribute("height")).toBe("76");
    expect(
      within(block).getByRole("link", { name: "Cómo instalar en iPhone" }),
    ).toHaveAttribute("href", "/install");
    // No session data travels in the block's links.
    expect(block.innerHTML).not.toMatch(/token|session|ana/i);
  });

  it("adapts the link to Android and computers", () => {
    setMe({ user, legacy_admin_key: false });
    device(UA.android);
    const { unmount } = render(<HomeInstallCard />);
    expect(
      screen.getByRole("link", { name: "Instalar en Android" }),
    ).toBeInTheDocument();
    unmount();
    device(UA.windows);
    render(<HomeInstallCard />);
    expect(
      screen.getByRole("link", { name: "Instalar en esta computadora" }),
    ).toBeInTheDocument();
  });

  it("is hidden inside the installed app", () => {
    displayMode(true);
    setMe({ user, legacy_admin_key: false });
    render(<HomeInstallCard />);
    expect(screen.queryByText("Smash Hub en tu celular")).toBeNull();
  });

  it("offers the browser's dialog and disappears once installed", async () => {
    device(UA.android);
    setMe({ user, legacy_admin_key: false });
    render(<HomeInstallCard />);
    const { event, prompt } = offer("accepted");
    act(() => {
      window.dispatchEvent(event);
    });
    expect(event.defaultPrevented).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Instalar ahora" }));
    expect(prompt).toHaveBeenCalledOnce();
    expect(await screen.findByRole("status")).toHaveTextContent("Instalando");
    act(() => {
      window.dispatchEvent(new Event("appinstalled"));
    });
    expect(screen.queryByText("Smash Hub en tu celular")).toBeNull();
  });
});

describe("/install page", () => {
  it("has the logo, name, benefits and a way in without installing", () => {
    device(UA.windows);
    const { container } = render(<InstallGuide />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Smash Hub" }),
    ).toBeInTheDocument();
    expect(container.querySelector('img[src="/smashclublogo.jpg"]')).not.toBe(
      null,
    );
    expect(screen.getByText(/Sin APK/)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Entrar sin instalar" }),
    ).toHaveAttribute("href", "/");
  });

  it("falls back to manual steps without beforeinstallprompt", () => {
    device(UA.android);
    render(<InstallGuide />);
    expect(screen.queryByRole("button", { name: /Instalar/ })).toBeNull();
    expect(
      screen.getByRole("heading", { name: "Cómo instalar" }),
    ).toBeInTheDocument();
    // The detected device comes first and open; the rest stay available.
    const guides = Array.from(document.querySelectorAll("details"));
    expect(guides.map((d) => d.querySelector("summary")?.textContent)).toEqual([
      "Android",
      "iPhone y iPad",
      "Computadora",
    ]);
    expect(guides.map((d) => d.open)).toEqual([true, false, false]);
    expect(guides[0]).toHaveTextContent("Instalar aplicación");
  });

  it("gives Safari's Share → Add to Home Screen steps on iPhone", () => {
    device(UA.iphone);
    render(<InstallGuide />);
    const first = document.querySelector("details")!;
    expect(first.querySelector("summary")).toHaveTextContent("iPhone");
    expect(first).toHaveTextContent("Compartir");
    expect(first).toHaveTextContent("Agregar a pantalla de inicio");
    expect(first).not.toHaveTextContent("Abrí esta página en Safari");
  });

  it("asks for Safari in other iPhone browsers and warns inside other apps", () => {
    device(UA.iphoneChrome);
    const { unmount } = render(<InstallGuide />);
    expect(screen.getByText(/Abrí esta página en/)).toBeInTheDocument();
    unmount();
    device(UA.iphoneInstagram);
    render(<InstallGuide />);
    expect(screen.getByText(/navegador de otra app/)).toBeInTheDocument();
  });

  it("does not claim success until the browser confirms", async () => {
    device(UA.windows);
    render(<InstallGuide />);
    const { event, prompt } = offer("accepted");
    act(() => {
      window.dispatchEvent(event);
    });
    expect(
      screen.getByRole("heading", { name: "Otras formas de instalar" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Instalar Smash Hub" }));
    expect(prompt).toHaveBeenCalledOnce();
    const status = screen.getByRole("status");
    expect(await screen.findByText(/Instalando/)).toBe(status);
    expect(status).not.toHaveTextContent("Listo");
    // An offer is single-use: the button goes away until the browser sends another.
    expect(screen.queryByRole("button", { name: "Instalar Smash Hub" })).toBe(
      null,
    );
    act(() => {
      window.dispatchEvent(new Event("appinstalled"));
    });
    expect(status).toHaveTextContent("el navegador confirmó la instalación");
  });

  it("says when the person cancels the dialog", async () => {
    device(UA.android);
    render(<InstallGuide />);
    const { event } = offer("dismissed");
    act(() => {
      window.dispatchEvent(event);
    });
    fireEvent.click(screen.getByRole("button", { name: "Instalar Smash Hub" }));
    expect(await screen.findByText(/Se canceló la instalación/)).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Cómo instalar" }),
    ).toBeVisible();
  });

  it("inside the installed app only offers to go home", () => {
    displayMode(true);
    render(<InstallGuide />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Ya estás usando Smash Hub instalada",
    );
    expect(screen.getByRole("link", { name: "Ir al inicio" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(document.querySelector("details")).toBeNull();
  });

  it("keeps an offer fired before the app hydrated", () => {
    stop();
    const { event } = offer("accepted");
    // What the inline head script does.
    new Function("window", EARLY_PROMPT_SCRIPT)(window);
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    expect(
      (window as unknown as Record<string, unknown>)[EARLY_PROMPT_KEY],
    ).toBe(event);
    stop = startInstallListener();
    expect(
      (window as unknown as Record<string, unknown>)[EARLY_PROMPT_KEY],
    ).toBeUndefined();
    render(<InstallGuide />);
    expect(
      screen.getByRole("button", { name: "Instalar Smash Hub" }),
    ).toBeInTheDocument();
  });
});
