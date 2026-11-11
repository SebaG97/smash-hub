import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RulebookReader } from "../../../components/rulebook";
import { preview } from "../../../lib/previews";
import { revisedText, rulebook, rulebookIndex } from "../../../lib/rulebooks";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const book = rulebook((await params).id);
  if (!book) return { title: "Reglamento" };
  return preview({
    title: book.title,
    description: `Versión ${book.version}, revisado el ${revisedText(book.revised)}. Leelo en el hub o descargá el PDF oficial.`,
    path: `/reglamentos/${book.id}`,
    image: "/smashclublogo.jpg",
    square: true,
  });
}

/** Public, no sign-in: the official rulebook of a tournament. */
export default async function Page({ params }: Props) {
  const book = rulebook((await params).id);
  if (!book) notFound();
  const slug = book.tournaments[0];
  return (
    <RulebookReader
      book={book}
      index={rulebookIndex(book)}
      back={
        slug
          ? { href: `/previa/${slug}#reglamento`, label: "Previa del torneo" }
          : undefined
      }
    />
  );
}
