"use client";

import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useState } from "react";
import {
  type Platform,
  detectBrowser,
  detectPlatform,
  installUrl,
  isIosSafari,
  offersInstallDialog,
  openInChromeUrl,
} from "../lib/install";
import {
  promptInstall,
  startInstallListener,
  useDevice,
  useInstallState,
  useStandalone,
} from "../lib/pwa";
import { useMe } from "../lib/session";
import { Logo } from "./logo";

/** Mounted once in the root layout so the browser's install offer is never missed. */
export function InstallListener() {
  useEffect(() => startInstallListener(), []);
  return null;
}

function PhoneIcon() {
  return (
    <svg
      className="install-phone"
      viewBox="0 0 24 24"
      width="22"
      height="22"
      aria-hidden="true"
      focusable="false"
    >
      <rect
        x="6"
        y="2"
        width="12"
        height="20"
        rx="2.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="M10.5 18.5h3"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

const LINK_LABEL: Record<Platform, string> = {
  ios: "Instalar en iPhone",
  android: "Instalar en Android",
  desktop: "Instalar en la PC",
};

/**
 * Home: a compact card beside the intro for signed-in visitors, with a QR for the phone
 * and a link to /install, the only place that runs the installation. Hidden inside the
 * installed app and when the browser says it is already installed.
 */
export function HomeInstallCard() {
  const me = useMe();
  const standalone = useStandalone();
  const platform = useDevice(detectPlatform);
  const { installed } = useInstallState();
  if (!me?.user || standalone || installed) return null;
  const url = installUrl();
  return (
    <section className="install-card" aria-labelledby="install-card-title">
      <h2 id="install-card-title">
        <PhoneIcon />
        Smash Hub en tu celular
      </h2>
      <div className="install-card-body">
        <QRCodeSVG
          value={url}
          size={68}
          marginSize={2}
          bgColor="#efe9df"
          fgColor="#1c1210"
          title={`Código QR para abrir ${url}`}
          role="img"
          aria-label={`Código QR para abrir ${url}`}
        />
        <div>
          <p>Instalá Smash Hub gratis.</p>
          <Link className="install-card-link" href="/install">
            {platform ? LINK_LABEL[platform] : "Instalar"}
          </Link>
        </div>
      </div>
    </section>
  );
}

/** How long a Chromium browser gets to offer its install dialog before we say it did not. */
export const OFFER_WAIT_MS = 6000;

export type InstallPhase =
  | "standalone"
  | "installed"
  | "installing"
  | "available"
  | "waiting"
  | "unavailable";

/** One answer for the whole page: what the person can do right now. */
function useInstallPhase() {
  const standalone = useStandalone();
  const { prompt, installed } = useInstallState();
  const capable = useDevice(offersInstallDialog);
  const [outcome, setOutcome] = useState<
    "accepted" | "dismissed" | "unavailable" | null
  >(null);
  const [waited, setWaited] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setWaited(true), OFFER_WAIT_MS);
    return () => clearTimeout(timer);
  }, []);
  let phase: InstallPhase;
  if (standalone) phase = "standalone";
  else if (installed) phase = "installed";
  else if (outcome === "accepted") phase = "installing";
  else if (prompt) phase = "available";
  else if (capable && !waited && outcome === null) phase = "waiting";
  else phase = "unavailable";
  return {
    phase,
    installed,
    dismissed: outcome === "dismissed",
    install: async () => setOutcome(await promptInstall()),
  };
}

const BENEFITS = [
  "Se abre desde la pantalla de inicio, como cualquier app.",
  "Pantalla completa, sin la barra del navegador.",
  "Sin APK ni tienda de aplicaciones: no ocupa casi espacio.",
  "Siempre al día: es la misma web, se actualiza sola.",
];

function IosSteps({ safari }: { safari: boolean | null }) {
  return (
    <>
      {safari === false && (
        <p className="install-note">
          Abrí esta página en <strong>Safari</strong>: es el navegador que
          permite agregarla en iPhone.
        </p>
      )}
      <ol>
        <li>
          Tocá <strong>Compartir</strong> (el cuadrado con la flecha hacia
          arriba).
        </li>
        <li>
          Elegí <strong>Agregar a pantalla de inicio</strong>. Si no aparece,
          deslizá hacia abajo en el menú.
        </li>
        <li>
          Tocá <strong>Agregar</strong>.
        </li>
      </ol>
      <p className="install-note">
        En iPhone la app guarda su propia sesión: puede pedirte ingresar otra
        vez la primera vez que la abras.
      </p>
    </>
  );
}

function AndroidSteps() {
  return (
    <>
      <ol>
        <li>
          En Chrome, tocá el menú <strong>⋮</strong>.
        </li>
        <li>
          Elegí <strong>Instalar aplicación</strong> o{" "}
          <strong>Agregar a la pantalla principal</strong>.
        </li>
        <li>
          Tocá <strong>Instalar</strong>.
        </li>
      </ol>
      <p className="install-note">
        Si la abriste desde la cámara o el lector de QR y el menú muestra{" "}
        <strong>Abrir en Chrome</strong>, tocalo primero. En Samsung Internet:
        menú → Agregar página a → Pantalla de inicio. En Firefox: menú ⋮ →
        Instalar.
      </p>
    </>
  );
}

function DesktopSteps() {
  return (
    <ol>
      <li>
        En Chrome o Edge, usá el ícono de instalar en la barra de direcciones, o
        el menú → <strong>Instalar Smash Hub</strong>.
      </li>
      <li>
        En Safari para Mac: <strong>Archivo → Agregar al Dock</strong>.
      </li>
      <li>Firefox para computadora no instala sitios: usá otro navegador.</li>
    </ol>
  );
}

const GUIDES: { platform: Platform; title: string }[] = [
  { platform: "android", title: "Android" },
  { platform: "ios", title: "iPhone y iPad" },
  { platform: "desktop", title: "Computadora" },
];

/** Copy the install address, for browsers that cannot open Chrome on their own. */
function CopyLink({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  if (typeof navigator === "undefined" || !navigator.clipboard) return null;
  return (
    <button
      type="button"
      className="secondary-button"
      onClick={() =>
        navigator.clipboard.writeText(url).then(
          () => setCopied(true),
          () => setCopied(false),
        )
      }
    >
      {copied ? "Enlace copiado" : "Copiar enlace"}
    </button>
  );
}

/** Public /install page body. */
export function InstallGuide() {
  const platform = useDevice(detectPlatform);
  const browser = useDevice(detectBrowser);
  const safari = useDevice(isIosSafari);
  const { phase, installed, dismissed, install } = useInstallPhase();
  const url = installUrl();
  const inApp = browser === "inapp";
  // The detected device goes first and open; the others stay one tap away.
  const guides = platform
    ? [...GUIDES].sort(
        (a, b) =>
          Number(b.platform === platform) - Number(a.platform === platform),
      )
    : GUIDES;

  let status: string;
  switch (phase) {
    case "standalone":
      status = "Ya estás usando Smash Hub instalada.";
      break;
    case "installed":
      status =
        installed === "event"
          ? "Listo: el navegador confirmó la instalación. Buscá Smash Hub entre tus aplicaciones."
          : "Smash Hub ya está instalada en este dispositivo. Abrila desde tu pantalla de inicio o tus aplicaciones.";
      break;
    case "installing":
      status = "Instalando… el navegador avisa cuando termina.";
      break;
    case "available":
      status = "Tu navegador permite instalar Smash Hub con un toque.";
      break;
    case "waiting":
      status = "Comprobando si tu navegador permite instalar…";
      break;
    default:
      if (dismissed)
        status =
          "Se canceló la instalación. Podés hacerlo cuando quieras con los pasos de abajo.";
      else if (inApp)
        status =
          "Este navegador está dentro de otra app (WhatsApp, Instagram, Facebook…) y no permite instalar.";
      else if (platform === "ios")
        status = safari
          ? "En iPhone se instala desde Safari, en tres pasos."
          : "En iPhone se instala desde Safari: abrí esta página ahí.";
      else if (browser === "chrome" || browser === "edge")
        status =
          "El navegador todavía no ofrece la instalación directa. Podés instalarla desde su menú, con los pasos de abajo.";
      else
        status =
          "Este navegador no ofrece instalación directa: seguí los pasos de abajo.";
  }

  return (
    <div className="install-page">
      <header className="install-hero">
        <Logo size={112} />
        <div>
          <h1>Smash Hub</h1>
          <p>
            Ranking, torneos, Prode y logros de la escena de Smash en Paraguay,
            instalados en tu celular o computadora.
          </p>
        </div>
      </header>

      <section
        className="install-panel"
        data-phase={phase}
        aria-label="Instalación"
        aria-busy={phase === "waiting"}
      >
        <p role="status" className="install-status">
          {status}
        </p>
        <div className="install-actions">
          {phase === "available" && (
            <button
              type="button"
              className="primary-button install-main"
              onClick={install}
            >
              Instalar Smash Hub
            </button>
          )}
          {phase === "unavailable" && inApp && platform === "android" && (
            <a
              className="primary-button install-main"
              href={openInChromeUrl(url)}
            >
              Abrir en Chrome
            </a>
          )}
          {phase === "unavailable" && inApp && <CopyLink url={url} />}
          <Link
            href="/"
            className={
              phase === "standalone" || phase === "installed"
                ? "primary-button"
                : "secondary-button"
            }
          >
            {phase === "standalone"
              ? "Ir al inicio"
              : phase === "installed"
                ? "Seguir en el navegador"
                : "Entrar sin instalar"}
          </Link>
        </div>
        {inApp && phase === "unavailable" && (
          <p className="install-note">
            También podés tocar el menú de la app (⋮ o …) y elegir{" "}
            <strong>Abrir en el navegador</strong>, o copiar{" "}
            <strong>{url.replace(/^https?:\/\//, "")}</strong> en Chrome o
            Safari.
          </p>
        )}
      </section>

      <ul className="install-benefits">
        {BENEFITS.map((b) => (
          <li key={b}>{b}</li>
        ))}
      </ul>

      {phase !== "standalone" && phase !== "installed" && (
        <section aria-labelledby="install-steps-title">
          <h2 id="install-steps-title">
            {phase === "available"
              ? "Otras formas de instalar"
              : "Cómo instalar"}
          </h2>
          {guides.map((g) => (
            <details
              key={g.platform}
              className="install-guide"
              open={platform === null || g.platform === platform}
            >
              <summary>{g.title}</summary>
              {g.platform === "ios" ? (
                <IosSteps safari={platform === "ios" ? safari : null} />
              ) : g.platform === "android" ? (
                <AndroidSteps />
              ) : (
                <DesktopSteps />
              )}
            </details>
          ))}
        </section>
      )}
    </div>
  );
}
