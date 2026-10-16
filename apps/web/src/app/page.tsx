import Link from "next/link";
import { BackendStatus } from "../components/backend-status";
import { modules } from "../lib/modules";
export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">
            <span /> EL PRÓXIMO CAPÍTULO DE LA ESCENA
          </p>
          <h1>
            La comunidad
            <br />
            nos <em>mueve.</em>
          </h1>
          <p className="hero-description">
            Cada set tiene una historia. Estamos construyendo el lugar donde la
            escena competitiva de Paraguay se encuentra, crece y deja su huella.
          </p>
          <div className="hero-actions">
            <Link href="#explorar" className="primary-button">
              Explorar el hub <span aria-hidden="true">↗</span>
            </Link>
            <span className="development-label">En construcción, juntos.</span>
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <span className="art-coordinate top">25°17′S · 57°38′W</span>
          <div className="cross-mark">
            <span />
            <span />
          </div>
          <span className="art-label">
            PLAYER COMMUNITY
            <br />
            <strong>PARAGUAY</strong>
          </span>
          <span className="art-coordinate bottom">
            PRESS START TO CONNECT ↗
          </span>
        </div>
      </section>
      <div className="scene-strip">
        <span>EL PUNTO DE ENCUENTRO COMPETITIVO</span>
        <span>
          SUPER SMASH BROS. ULTIMATE <b aria-hidden="true">✦</b> PARAGUAY
        </span>
      </div>
      <section id="explorar" className="explore">
        <div className="section-heading">
          <div>
            <p className="eyebrow">TU ESCENA, EN UN SOLO LUGAR</p>
            <h2>Todo empieza por conectar.</h2>
          </div>
          <p>
            Torneos, jugadores e historias.
            <br />
            Resultados disponibles después de cada importación.
          </p>
        </div>
        <div className="module-grid">
          {modules.map((m) => (
            <Link href={`/${m.slug}`} key={m.slug} className="module-card">
              <div className="card-top">
                <span>{m.number} /</span>
                <span aria-hidden="true">↗</span>
              </div>
              <h3>{m.title}</h3>
              <p>{m.description}</p>
              <span className="coming-soon">
                {m.slug === "players" || m.slug === "tournaments"
                  ? "EXPLORAR"
                  : "PRÓXIMAMENTE"}
              </span>
            </Link>
          ))}
        </div>
      </section>
      <section className="foundation">
        <div>
          <p className="eyebrow">CONSTRUIMOS SOBRE UNA BASE FIRME</p>
          <h2>
            Primero la comunidad.
            <br />
            Después, cada posibilidad.
          </h2>
          <p>
            Explorá jugadores, torneos y resultados importados con su contexto
            histórico. Cada registro conserva su procedencia; los rankings
            llegarán en una etapa posterior.
          </p>
        </div>
        <aside>
          <span className="system-label">ESTADO DEL SISTEMA</span>
          <BackendStatus />
          <p>
            Consulta en tiempo real la disponibilidad de la API y su conexión
            con la base de datos.
          </p>
          <a
            href={(process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(
              /\/v1\/?$/,
              "/docs",
            )}
          >
            Documentación de la API ↗
          </a>
        </aside>
      </section>
    </>
  );
}
