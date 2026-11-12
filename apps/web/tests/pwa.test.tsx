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
  waitFor,
  within,
} from "@testing-library/react";
import manifest, { APP_BACKGROUND } from "../src/app/manifest";
import Home from "../src/app/page";
import {
  HomeInstallCard,
  InstallGuide,
  OFFER_WAIT_MS,
} from "../src/components/pwa";
import {
  DEFAULT_PUBLIC_ORIGIN,
  EARLY_PROMPT_KEY,
  EARLY_PROMPT_SCRIPT,
  detectBrowser,
  detectPlatform,
  installUrl,
  isInAppBrowser,
  offersInstallDialog,
  openInChromeUrl,
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
  androidInstagram:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0 Mobile Safari/537.36 Instagram 350.0",
  androidWebView:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0 Mobile Safari/537.36",
  androidWhatsApp:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36 WhatsApp/2.24",
  androidGoogleApp:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36 GSA/15.0",
  androidSamsung:
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0 Mobile Safari/537.36",
  androidFirefox:
    "Mozilla/5.0 (Android 14; Mobile; rv:131.0) Gecko/131.0 Firefox/131.0",
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
    // Lets Chromium report an installed app; never points to a store app.
    expect(m.prefer_related_applications).toBe(false);
    expect(m.related_applications).toEqual([
      {
        platform: "webapp",
        url: "https://smashclubpy.com/manifest.webmanifest",
      },
    ]);
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

describe("Android browsers", () => {
  it("tells Chrome, Samsung Internet, Firefox and in-app browsers apart", () => {
    expect(detectBrowser(UA.android)).toBe("chrome");
    expect(detectBrowser(UA.androidSamsung)).toBe("samsung");
    expect(detectBrowser(UA.androidFirefox)).toBe("firefox");
    expect(detectBrowser(UA.windows)).toBe("edge");
    expect(detectBrowser(UA.iphone)).toBe("safari");
    for (const ua of [
      UA.androidInstagram,
      UA.androidWebView,
      UA.androidWhatsApp,
      UA.androidGoogleApp,
      UA.iphoneInstagram,
    ]) {
      expect(isInAppBrowser(ua)).toBe(true);
      expect(detectBrowser(ua)).toBe("inapp");
    }
  });

  it("expects the native dialog only from Chromium outside iPhone", () => {
    expect(offersInstallDialog(UA.android)).toBe(true);
    expect(offersInstallDialog(UA.androidSamsung)).toBe(true);
    expect(offersInstallDialog(UA.windows)).toBe(true);
    expect(offersInstallDialog(UA.androidFirefox)).toBe(false);
    expect(offersInstallDialog(UA.androidWebView)).toBe(false);
    expect(offersInstallDialog(UA.iphone)).toBe(false);
    expect(offersInstallDialog(UA.iphoneChrome)).toBe(false);
  });

  it("builds a Chrome intent for the public install page only", () => {
    expect(openInChromeUrl("https://smashclubpy.com/install")).toBe(
      "intent://smashclubpy.com/install#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=https%3A%2F%2Fsmashclubpy.com%2Finstall;end",
    );
  });
});

describe("home install card", () => {
  it("is only for signed-in visitors", () => {
    render(<HomeInstallCard />);
    expect(screen.queryByText("Smash Hub en tu celular")).toBeNull();
  });

  it("is compact: QR of the public install page and a link for this device", () => {
    device(UA.iphone);
    setMe({ user, legacy_admin_key: false });
    render(<HomeInstallCard />);
    const card = screen.getByRole("region", {
      name: "Smash Hub en tu celular",
    });
    expect(within(card).getByText("Instalá Smash Hub gratis.")).toBeVisible();
    const qr = within(card).getByRole("img", {
      name: "Código QR para abrir https://smashclubpy.com/install",
    });
    expect(Number(qr.getAttribute("height"))).toBeGreaterThanOrEqual(64);
    expect(Number(qr.getAttribute("height"))).toBeLessThanOrEqual(76);
    expect(
      within(card).getByRole("link", { name: "Instalar en iPhone" }),
    ).toHaveAttribute("href", "/install");
    // No session data travels in the card.
    expect(card.innerHTML).not.toMatch(/token|session|ana/i);
  });

  it("adapts the link to Android and computers, always towards /install", () => {
    setMe({ user, legacy_admin_key: false });
    device(UA.android);
    const { unmount } = render(<HomeInstallCard />);
    expect(
      screen.getByRole("link", { name: "Instalar en Android" }),
    ).toHaveAttribute("href", "/install");
    unmount();
    device(UA.windows);
    render(<HomeInstallCard />);
    expect(
      screen.getByRole("link", { name: "Instalar en la PC" }),
    ).toHaveAttribute("href", "/install");
  });

  it("does not run the installation itself: that lives only in /install", () => {
    device(UA.android);
    setMe({ user, legacy_admin_key: false });
    render(<HomeInstallCard />);
    act(() => {
      window.dispatchEvent(offer("accepted").event);
    });
    expect(screen.queryByRole("button")).toBeNull();
    expect(
      screen.getByRole("link", { name: "Instalar en Android" }),
    ).toBeInTheDocument();
  });

  it("is hidden inside the installed app", () => {
    displayMode(true);
    setMe({ user, legacy_admin_key: false });
    render(<HomeInstallCard />);
    expect(screen.queryByText("Smash Hub en tu celular")).toBeNull();
  });

  it("is hidden once the browser confirms installation", () => {
    setMe({ user, legacy_admin_key: false });
    render(<HomeInstallCard />);
    expect(screen.getByText("Smash Hub en tu celular")).toBeInTheDocument();
    act(() => {
      window.dispatchEvent(new Event("appinstalled"));
    });
    expect(screen.queryByText("Smash Hub en tu celular")).toBeNull();
  });

  it("is hidden when Chromium reports the app already installed", async () => {
    stop();
    Object.defineProperty(navigator, "getInstalledRelatedApps", {
      value: () => Promise.resolve([{ platform: "webapp" }]),
      configurable: true,
    });
    try {
      stop = startInstallListener();
      setMe({ user, legacy_admin_key: false });
      render(<HomeInstallCard />);
      await waitFor(() =>
        expect(screen.queryByText("Smash Hub en tu celular")).toBeNull(),
      );
    } finally {
      delete (navigator as unknown as Record<string, unknown>)
        .getInstalledRelatedApps;
    }
  });

  it("sits inside the home intro, after the title and description", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("{}", { status: 404 }))),
    );
    setMe({ user, legacy_admin_key: false });
    const { container } = render(<Home />);
    const intro = container.querySelector(".home-intro") as HTMLElement;
    const card = within(intro).getByRole("region", {
      name: "Smash Hub en tu celular",
    });
    expect(intro.lastElementChild).toBe(card);
    expect(
      within(intro).getByRole("heading", {
        level: 1,
        name: "Smash Club Paraguay",
      }),
    ).toBeInTheDocument();
    // Only one install card on the home page.
    expect(container.querySelectorAll(".install-card")).toHaveLength(1);
  });

  it("keeps the intro's layout on phones and makes room for the card", () => {
    const css = readFileSync(join(__dirname, "../src/app/globals.css"), "utf8");
    const section = css.slice(css.indexOf("SH-PWA-02"));
    expect(section).toMatch(
      /\.home-intro \{\s*grid-template-columns: auto minmax\(0, 1fr\) auto;/,
    );
    expect(section).toMatch(/width: clamp\(240px, 24vw, 280px\)/);
    // Phones: one column again, the card under the title, never wider than 360px.
    expect(section).toMatch(
      /@media \(max-width: 580px\) \{[^}]*\.home-intro \{\s*grid-template-columns: 1fr;/,
    );
    expect(section).toMatch(/max-width: 360px/);
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

  it("puts the install button first, before the benefits", () => {
    device(UA.android);
    render(<InstallGuide />);
    act(() => {
      window.dispatchEvent(offer("accepted").event);
    });
    const button = screen.getByRole("button", { name: "Instalar Smash Hub" });
    const benefits = screen.getByText(/Sin APK/);
    expect(
      button.compareDocumentPosition(benefits) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(screen.getByRole("status")).toHaveTextContent(
      "permite instalar Smash Hub con un toque",
    );
  });

  it("waits for Chrome's offer, then falls back to the menu steps", () => {
    vi.useFakeTimers();
    try {
      device(UA.android);
      render(<InstallGuide />);
      expect(screen.getByRole("status")).toHaveTextContent(
        "Comprobando si tu navegador permite instalar",
      );
      expect(screen.queryByRole("button", { name: /Instalar/ })).toBeNull();
      act(() => {
        vi.advanceTimersByTime(OFFER_WAIT_MS);
      });
      expect(screen.getByRole("status")).toHaveTextContent(
        "todavía no ofrece la instalación directa",
      );
      expect(
        screen.getByRole("heading", { name: "Cómo instalar" }),
      ).toBeInTheDocument();
      // The detected device comes first and open; the rest stay available.
      const guides = Array.from(document.querySelectorAll("details"));
      expect(
        guides.map((d) => d.querySelector("summary")?.textContent),
      ).toEqual(["Android", "iPhone y iPad", "Computadora"]);
      expect(guides.map((d) => d.open)).toEqual([true, false, false]);
      expect(guides[0]).toHaveTextContent("Instalar aplicación");
      expect(guides[0]).toHaveTextContent("Abrir en Chrome");
      // A late offer still brings the button back.
      act(() => {
        window.dispatchEvent(offer("accepted").event);
      });
      expect(
        screen.getByRole("button", { name: "Instalar Smash Hub" }),
      ).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not wait for a dialog that Firefox never offers", () => {
    device(UA.androidFirefox);
    render(<InstallGuide />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "no ofrece instalación directa",
    );
  });

  it("gives Safari's Share → Add to Home Screen steps on iPhone", () => {
    device(UA.iphone);
    render(<InstallGuide />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "En iPhone se instala desde Safari, en tres pasos",
    );
    const first = document.querySelector("details")!;
    expect(first.querySelector("summary")).toHaveTextContent("iPhone");
    expect(first).toHaveTextContent("Compartir");
    expect(first).toHaveTextContent("Agregar a pantalla de inicio");
    expect(first).not.toHaveTextContent("Abrí esta página en Safari");
    expect(screen.queryByRole("button", { name: /Instalar/ })).toBeNull();
  });

  it("asks for Safari in other iPhone browsers", () => {
    device(UA.iphoneChrome);
    render(<InstallGuide />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "abrí esta página ahí",
    );
    expect(screen.getByText(/Abrí esta página en/)).toBeInTheDocument();
  });

  it("offers to open Chrome from WhatsApp, Instagram or Facebook on Android", () => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn(() => Promise.resolve()) },
      configurable: true,
    });
    try {
      for (const ua of [UA.androidWhatsApp, UA.androidInstagram]) {
        device(ua);
        const { unmount } = render(<InstallGuide />);
        expect(screen.getByRole("status")).toHaveTextContent(
          "dentro de otra app",
        );
        expect(
          screen.getByRole("link", { name: "Abrir en Chrome" }),
        ).toHaveAttribute(
          "href",
          openInChromeUrl("https://smashclubpy.com/install"),
        );
        expect(
          screen.getByRole("button", { name: "Copiar enlace" }),
        ).toBeInTheDocument();
        unmount();
      }
    } finally {
      delete (navigator as unknown as Record<string, unknown>).clipboard;
    }
  });

  it("on iPhone in-app browsers asks for Safari, without a Chrome intent", () => {
    device(UA.iphoneInstagram);
    render(<InstallGuide />);
    expect(screen.getByRole("status")).toHaveTextContent("dentro de otra app");
    expect(screen.queryByRole("link", { name: "Abrir en Chrome" })).toBeNull();
    expect(screen.getByText(/Abrir en el navegador/)).toBeInTheDocument();
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
    expect(document.querySelector("details")).toBeNull();
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

  it("says when the app is already installed instead of asking again", async () => {
    stop();
    Object.defineProperty(navigator, "getInstalledRelatedApps", {
      value: () => Promise.resolve([{ platform: "webapp" }]),
      configurable: true,
    });
    try {
      stop = startInstallListener();
      device(UA.android);
      render(<InstallGuide />);
      await waitFor(() =>
        expect(screen.getByRole("status")).toHaveTextContent(
          "ya está instalada en este dispositivo",
        ),
      );
      expect(document.querySelector("details")).toBeNull();
    } finally {
      delete (navigator as unknown as Record<string, unknown>)
        .getInstalledRelatedApps;
    }
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
