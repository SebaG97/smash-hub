"use client";

import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useState } from "react";
import {
  type Platform,
  detectPlatform,
  installUrl,
  isInAppBrowser,
  isIosSafari,
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
      width="36"
      height="36"
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
  ios: "Cómo instalar en iPhone",
  android: "Instalar en Android",
  desktop: "Instalar en esta computadora",
};

type Outcome = "accepted" | "dismissed" | "unavailable" | null;

/** The browser's own install dialog, when it offers one. */
function useInstall() {
  const { prompt, installed } = useInstallState();
  const [outcome, setOutcome] = useState<Outcome>(null);
  return {
    canPrompt: prompt !== null,
    installed,
    outcome,
    install: async () => setOutcome(await promptInstall()),
  };
}

/**
 * Home block for signed-in visitors: a QR for the phone and a link that fits this
 * device. Hidden inside the installed app and once the browser confirms installation.
 */
export function HomeInstallCard() {
  const me = useMe();
  const standalone = useStandalone();
  const platform = useDevice(detectPlatform);
  const { canPrompt, installed, outcome, install } = useInstall();
  if (!me?.user || standalone || installed) return null;
  const url = installUrl();
  return (
    <section className="install-card" aria-labelledby="install-card-title">
      <PhoneIcon />
      <div className="install-card-text">
        <h2 id="install-card-title">Smash Hub en tu celular</h2>
        <p>
          Se instala desde el navegador y queda en tu pantalla de inicio, sin
          descargar un APK.
        </p>
        <p className="install-card-actions">
          {canPrompt ? (
            <button type="button" className="primary-button" onClick={install}>
              Instalar ahora
            </button>
          ) : (
            <Link className="primary-button" href="/install">
              {platform ? LINK_LABEL[platform] : "Instalar la app"}
            </Link>
          )}
          {canPrompt && <Link href="/install">Otras formas de instalar</Link>}
        </p>
        {outcome === "accepted" && (
          <p role="status">Instalando… el navegador avisa cuando termina.</p>
        )}
      </div>
      <figure className="install-qr">
        <QRCodeSVG
          value={url}
          size={76}
          marginSize={2}
          bgColor="#efe9df"
          fgColor="#1c1210"
          title={`Código QR para abrir ${url}`}
          role="img"
          aria-label={`Código QR para abrir ${url}`}
        />
        <figcaption>Escaneá con el celular</figcaption>
      </figure>
    </section>
  );
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
    <ol>
      <li>
        En Chrome, tocá el menú <strong>⋮</strong>.
      </li>
      <li>
        Elegí <strong>Instalar aplicación</strong> o{" "}
        <strong>Agregar a la pantalla principal</strong>.
      </li>
      <li>
        Confirmá. En Samsung Internet: menú → Agregar página a → Pantalla de
        inicio.
      </li>
    </ol>
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

/** Public /install page body. */
export function InstallGuide() {
  const standalone = useStandalone();
  const platform = useDevice(detectPlatform);
  const safari = useDevice(isIosSafari);
  const inApp = useDevice(isInAppBrowser);
  const { canPrompt, installed, outcome, install } = useInstall();
  // The detected device goes first and open; the others stay one tap away.
  const guides = platform
    ? [...GUIDES].sort(
        (a, b) =>
          Number(b.platform === platform) - Number(a.platform === platform),
      )
    : GUIDES;

  let status: string | null = null;
  if (standalone) status = "Ya estás usando Smash Hub instalada.";
  else if (installed)
    status =
      "Listo: el navegador confirmó la instalación. Buscá Smash Hub entre tus aplicaciones.";
  else if (outcome === "accepted")
    status = "Instalando… el navegador avisa cuando termina.";
  else if (outcome === "dismissed")
    status =
      "Se canceló la instalación. Podés hacerlo cuando quieras con los pasos de abajo.";

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

      <ul className="install-benefits">
        {BENEFITS.map((b) => (
          <li key={b}>{b}</li>
        ))}
      </ul>

      <div className="install-actions">
        {!standalone && !installed && canPrompt && (
          <button type="button" className="primary-button" onClick={install}>
            Instalar Smash Hub
          </button>
        )}
        <Link
          href="/"
          className={standalone ? "primary-button" : "secondary-button"}
        >
          {standalone ? "Ir al inicio" : "Entrar sin instalar"}
        </Link>
      </div>
      <p role="status" className="install-status">
        {status}
      </p>

      {!standalone && (
        <section aria-labelledby="install-steps-title">
          <h2 id="install-steps-title">
            {canPrompt ? "Otras formas de instalar" : "Cómo instalar"}
          </h2>
          {inApp && (
            <p className="install-note">
              Estás en el navegador de otra app (Instagram, Facebook…), que no
              permite instalar. Abrí{" "}
              <strong>{installUrl().replace(/^https?:\/\//, "")}</strong> en
              Chrome o Safari.
            </p>
          )}
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
