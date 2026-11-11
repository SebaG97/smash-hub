import Link from "next/link";
// Only the types module: the rule text never reaches the previa's bundle.
import {
  revisedText,
  sectionId,
  type RuleBlock,
  type RuleSection,
  type Rulebook,
  type RulebookSummary,
} from "../lib/rulebooks/types";

type Meta = Pick<
  RulebookSummary,
  "id" | "version" | "revised" | "pdf" | "filename" | "pages"
>;

function Revision({ book }: { book: Meta }) {
  return (
    <>
      Versión {book.version} · Revisado por última vez el{" "}
      <time dateTime={book.revised}>{revisedText(book.revised)}</time>
    </>
  );
}

/** The official PDF: open it (in a new tab) or download it. */
function PdfLinks({ book }: { book: Meta }) {
  return (
    <>
      <a
        className="secondary-button"
        href={book.pdf}
        target="_blank"
        rel="noopener"
      >
        Abrir el PDF oficial
        <span className="visually-hidden"> (se abre en otra pestaña)</span>
      </a>
      <a className="secondary-button" href={book.pdf} download={book.filename}>
        Descargar PDF <small>({book.pages} págs.)</small>
      </a>
    </>
  );
}

/** The Reglamento tab of /previa/[slug]. */
export function RulebookPanel({ rules }: { rules: RulebookSummary }) {
  const reader = `/reglamentos/${rules.id}`;
  return (
    <section className="rulebook-panel" aria-labelledby="rulebook-title">
      <h2 id="rulebook-title">{rules.title}</h2>
      <p className="seeding-lead">
        <Revision book={rules} />.
      </p>
      <p className="seeding-actions">
        <Link className="primary-button" href={reader}>
          Leer el reglamento
        </Link>
        <PdfLinks book={rules} />
      </p>
      <nav className="rulebook-nav" aria-label="Capítulos del reglamento">
        <h3>Capítulos</h3>
        <ol className="rulebook-index">
          {rules.index.map((s) => (
            <li key={s.id} className={s.sub ? "sub" : undefined}>
              <Link href={`${reader}#${s.id}`}>
                <span className="rule-number">{s.number}</span> {s.title}
              </Link>
            </li>
          ))}
        </ol>
      </nav>
    </section>
  );
}

function Block({ block }: { block: RuleBlock }) {
  switch (block.kind) {
    case "p":
      return <p>{block.text}</p>;
    case "list":
      return (
        <ul>
          {block.items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      );
    case "terms":
      return (
        <dl className="rule-terms">
          {block.items.map(([term, definition]) => (
            <div key={term}>
              <dt>{term}:</dt> <dd>{definition}</dd>
            </div>
          ))}
        </dl>
      );
    case "notes":
      return (
        <ul className="rule-notes">
          {block.items.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </ul>
      );
  }
}

function Section({ s, depth }: { s: RuleSection; depth: number }) {
  // Chapters are h2; 3.23 is h3, 3.23.1 is h4, 3.24.3.1 is h5.
  const Heading = `h${Math.min(depth + 2, 6)}` as "h2";
  const id = sectionId(s);
  return (
    <section
      id={id}
      className={depth === 0 ? "rule-chapter" : "rule-section"}
      aria-labelledby={`${id}-title`}
    >
      <Heading id={`${id}-title`}>
        <span className="rule-number">
          {depth === 0 ? `${s.number}.` : s.number}
        </span>{" "}
        {s.title}
      </Heading>
      {s.blocks?.map((b, i) => (
        <Block key={i} block={b} />
      ))}
      {s.sections?.map((c) => (
        <Section key={c.number} s={c} depth={depth + 1} />
      ))}
    </section>
  );
}

/** /reglamentos/[id]: the whole document, readable on a phone. */
export function RulebookReader({
  book,
  index,
  back,
}: {
  book: Rulebook;
  index: RulebookSummary["index"];
  back?: { href: string; label: string };
}) {
  return (
    <div className="competition-page rulebook" id="inicio">
      <p>
        {back ? (
          <Link href={back.href}>← {back.label}</Link>
        ) : (
          <Link href="/">← Inicio</Link>
        )}
      </p>
      <h1>{book.title}</h1>
      <p className="seeding-lead">
        <Revision book={book} />.
      </p>
      <p className="rulebook-official">
        Transcripción textual del documento oficial. Ante cualquier diferencia,
        vale el PDF.
      </p>
      <p className="seeding-actions">
        <PdfLinks book={book} />
      </p>
      <div className="rulebook-layout">
        <nav
          className="rulebook-nav rulebook-toc"
          aria-label="Índice del reglamento"
        >
          <h2 id="indice">Índice</h2>
          <ol className="rulebook-index">
            {index.map((s) => (
              <li key={s.id} className={s.sub ? "sub" : undefined}>
                <a href={`#${s.id}`}>
                  <span className="rule-number">{s.number}</span> {s.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <article className="rulebook-text">
          {book.chapters.map((c) => (
            <Section key={c.number} s={c} depth={0} />
          ))}
        </article>
      </div>
      {/* Always at hand on a phone: back to the index, or to the official PDF. */}
      <nav
        className="rulebook-nav rulebook-bar"
        aria-label="Accesos del reglamento"
      >
        <a href="#indice">Índice</a>
        <a href={book.pdf} target="_blank" rel="noopener">
          PDF oficial
        </a>
        <a href="#inicio">↑ Arriba</a>
      </nav>
    </div>
  );
}
