/** A player's approved team or prefix ("BG"), shown before the tag (Mission 22). */
export function Prefix({ prefix }: { prefix?: string | null }) {
  if (!prefix) return null;
  return <span className="tag-prefix">{prefix}</span>;
}
