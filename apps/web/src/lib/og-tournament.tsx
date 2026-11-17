import type { ReactNode } from "react";
import { ImageResponse } from "next/og";
import { characterColor } from "./characters";
import { brand, renderArt, stockIcon, type Art } from "./og";
import {
  FORMATS,
  type CardKey,
  type Format,
  type ImpactRow,
  type Ref,
  type Social,
  type SocialSet,
} from "./tournament-social";

/**
 * Social media images of a tournament (SH-SOCIAL-01), in the look of the site and of
 * the top 12 image: concrete background, slabs, the main's color on each player and
 * the official render in the costume they chose. Every image fits four formats.
 */

const NEUTRAL = "#5a514a";
const RARITY: Record<string, string> = {
  comun: brand.ash,
  raro: "#4f9fd9",
  epico: "#b16ee0",
  legendario: brand.gold,
};

type Box = { width: number; height: number };
type Ctx = { format: Format; wide: boolean; body: Box; under: boolean };

const main = (ref?: { mains?: Ref["mains"] } | null) => ref?.mains?.[0];
const tone = (ref?: { mains?: Ref["mains"] } | null) =>
  (main(ref) && characterColor(main(ref)!.character)) || NEUTRAL;
const toneOf = (character?: string | null) =>
  (character && characterColor(character)) || NEUTRAL;

function portrait(
  ref: { mains?: Ref["mains"] } | null | undefined,
  width: 160 | 320 | 640,
) {
  const m = main(ref);
  return m ? renderArt(m.character, m.costume, width) : Promise.resolve(null);
}

function icon(ref: { mains?: Ref["mains"] } | null | undefined) {
  return stockIcon(main(ref)?.character);
}

const ordinal = (n: number) => `${n}.º`;
const months = (days: number) =>
  days < 365
    ? `${Math.round(days / 30.4)} meses`
    : `${(days / 365).toFixed(1).replace(".0", "").replace(".", ",")} años`;

/** Scale a font size down for long names so they fit in `width`. */
function fitText(text: string, size: number, width: number) {
  const guess = text.length * size * 0.5; // the display font is narrow
  return guess > width
    ? Math.max(Math.floor(width / (text.length * 0.5)), 14)
    : size;
}

// ---------------------------------------------------------------- pieces

function Place({
  place,
  size,
  color,
}: {
  place: number | string;
  size: number;
  color?: string;
}) {
  const n = typeof place === "number" ? place : 99;
  return (
    <div
      style={{
        display: "flex",
        fontSize: size,
        lineHeight: 0.85,
        transform: "skewX(-10deg)",
        color:
          color ?? (n === 1 ? brand.gold : n <= 3 ? brand.fire : brand.bone),
      }}
    >
      {String(place)}
    </div>
  );
}

function Name({
  who,
  size,
  width,
  color = brand.bone,
}: {
  who: { tag: string | null; prefix?: string | null };
  size: number;
  width: number;
  color?: string;
}) {
  const tag = who.tag ?? "?";
  const prefix = who.prefix ? `${who.prefix} |` : "";
  const fontSize = fitText(prefix + tag, size, width);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        maxWidth: width,
        overflow: "hidden",
        whiteSpace: "nowrap",
        fontSize,
        lineHeight: 1,
        color,
      }}
    >
      {prefix && (
        <span
          style={{
            color: brand.ash,
            fontSize: Math.round(fontSize * 0.7),
            marginRight: Math.round(fontSize * 0.25),
          }}
        >
          {prefix}
        </span>
      )}
      <span>{tag}</span>
    </div>
  );
}

function Icon({ src, size }: { src: string | null; size: number }) {
  return (
    <div
      style={{
        display: "flex",
        width: size,
        height: size,
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      {src && <img src={src} width={size} height={size} alt="" />}
    </div>
  );
}

function Chip({
  text,
  color,
  size = 24,
  dark = false,
}: {
  text: string;
  color: string;
  size?: number;
  dark?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexShrink: 0,
        fontSize: size,
        lineHeight: 1,
        padding: `${Math.round(size * 0.3)}px ${Math.round(size * 0.5)}px`,
        background: color,
        color: dark ? brand.concrete : brand.bone,
      }}
    >
      {text}
    </div>
  );
}

/**
 * A render cropped to the upper body over the main's color, like the cards of the top
 * image. `fade` dims it (the loser of a set).
 */
function Cut({
  art,
  box,
  color,
  fade = false,
  children,
  border = "left",
}: {
  art: Art;
  box: Box;
  color: string;
  fade?: boolean;
  children?: ReactNode;
  border?: "left" | "top" | "none";
}) {
  // Tall boxes show the upper body; wide ones the whole render on the right.
  const landscape = box.width > box.height * 1.3;
  const scale = art
    ? landscape
      ? (box.height * 1.15) / art.height
      : Math.max(box.width / art.width, (box.height * 1.12) / art.height)
    : 1;
  const size = art && {
    width: Math.round(art.width * scale),
    height: Math.round(art.height * scale),
  };
  const left = size
    ? landscape
      ? box.width - size.width - Math.round(box.width * 0.04)
      : Math.round((box.width - size.width) / 2)
    : 0;
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        width: box.width,
        height: box.height,
        flexShrink: 0,
        overflow: "hidden",
        background: brand.slab,
        ...(border === "left" ? { borderLeft: `8px solid ${color}` } : {}),
        ...(border === "top" ? { borderTop: `8px solid ${color}` } : {}),
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: "flex",
          backgroundImage: `linear-gradient(160deg, ${color}66 0%, ${color}22 60%, ${brand.slab} 100%)`,
        }}
      />
      {art && size && (
        <img
          src={art.src}
          width={size.width}
          height={size.height}
          style={{
            position: "absolute",
            top: Math.round(box.height * 0.02),
            left,
            opacity: fade ? 0.45 : 1,
          }}
          alt=""
        />
      )}
      {children}
    </div>
  );
}

/** Name band at the bottom of a Cut. */
function Band({
  children,
  padding = "12px 18px",
}: {
  children: ReactNode;
  padding?: string;
}) {
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        display: "flex",
        alignItems: "flex-end",
        gap: 14,
        padding,
        background: "rgba(38,34,31,0.94)",
      }}
    >
      {children}
    </div>
  );
}

/** Text over a Cut: a band at the bottom, or a shaded left half in a wide box. */
function Side({
  landscape,
  children,
}: {
  landscape: boolean;
  children: ReactNode;
}) {
  if (!landscape) return <Band padding="18px 24px">{children}</Band>;
  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        bottom: 0,
        left: 0,
        width: "70%",
        display: "flex",
        alignItems: "flex-end",
        padding: "24px 28px",
        backgroundImage:
          "linear-gradient(90deg, rgba(38,34,31,0.96) 45%, rgba(38,34,31,0) 100%)",
      }}
    >
      {children}
    </div>
  );
}

function Section({ title, size = 30 }: { title: string; size?: number }) {
  return (
    <div
      style={{
        display: "flex",
        fontSize: size,
        color: brand.fire,
        letterSpacing: 2,
        textTransform: "uppercase",
      }}
    >
      {title}
    </div>
  );
}

function Row({
  height,
  color,
  children,
  shade = true,
}: {
  height: number;
  color: string;
  children: ReactNode;
  shade?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        height,
        flexShrink: 0,
        padding: "0 18px",
        background: shade ? brand.slab : "transparent",
        borderLeft: `6px solid ${color}`,
      }}
    >
      {children}
    </div>
  );
}

function Muted({ text, size }: { text: string; size: number }) {
  return (
    <div
      style={{
        display: "flex",
        fontSize: size,
        color: brand.ash,
        whiteSpace: "nowrap",
        overflow: "hidden",
      }}
    >
      {text}
    </div>
  );
}

/** Split items into columns for the wide format. */
function columns<T>(items: T[], count: number) {
  const per = Math.ceil(items.length / count);
  return Array.from({ length: count }, (_, i) =>
    items.slice(i * per, (i + 1) * per),
  ).filter((c) => c.length);
}

/** Height of each of `n` rows in `space`, between `min` and `max`. */
function rowHeight(space: number, n: number, gap: number, max: number) {
  return Math.max(Math.min(Math.floor((space - gap * (n - 1)) / n), max), 40);
}

/** How many rows of at least `min` height fit in `space`. */
function fitting(space: number, min: number, gap: number) {
  return Math.max(Math.floor((space + gap) / (min + gap)), 1);
}

// ---------------------------------------------------------------- 1. top 8

async function podio(d: Social, c: Ctx) {
  const top = d.summary.top.slice(0, 8);
  const { width, height } = c.body;
  const gap = 16;
  const heroW = c.wide ? Math.round(width * 0.58) : width;
  const heroH = c.wide ? height : Math.round(height * 0.6);
  const firstW = Math.round(heroW * 0.58);
  const sideW = heroW - firstW - gap;
  const sideH = Math.round((heroH - gap) / 2);
  const rest = top.slice(3);
  const [first, second, third, restArt, restIcons] = await Promise.all([
    portrait(top[0], 640),
    portrait(top[1], 640),
    portrait(top[2], 640),
    Promise.all(rest.map((r) => portrait(r, 320))),
    Promise.all(rest.map((r) => icon(r))),
  ]);
  const podiumCard = (
    r: (typeof top)[number],
    art: Art,
    box: Box,
    big: boolean,
  ) => (
    <Cut key={r.id} art={art} box={box} color={tone(r)}>
      <Band padding={big ? "16px 22px" : "10px 16px"}>
        <Place place={r.placement} size={big ? 110 : 64} />
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <Name who={r} size={big ? 58 : 38} width={box.width - 140} />
          {r.seed && <Muted text={`seed ${r.seed}`} size={big ? 26 : 22} />}
        </div>
      </Band>
    </Cut>
  );
  const restHeight = height - heroH - gap;
  const cardW = Math.floor((width - gap * 4) / 5);
  return (
    <div
      style={{
        display: "flex",
        gap,
        width,
        height,
        flexDirection: c.wide ? "row" : "column",
      }}
    >
      <div style={{ display: "flex", gap, height: heroH }}>
        {top[0] &&
          podiumCard(top[0], first, { width: firstW, height: heroH }, true)}
        <div style={{ display: "flex", flexDirection: "column", gap }}>
          {top[1] &&
            podiumCard(top[1], second, { width: sideW, height: sideH }, false)}
          {top[2] &&
            podiumCard(top[2], third, { width: sideW, height: sideH }, false)}
        </div>
      </div>
      {rest.length > 0 &&
        (c.wide ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 12,
              width: width - heroW - gap,
            }}
          >
            {rest.map((r, i) => (
              <Row
                key={r.id}
                height={rowHeight(height, rest.length, 12, 130)}
                color={tone(r)}
              >
                <Place place={r.placement} size={52} />
                <Icon src={restIcons[i]} size={56} />
                <Name who={r} size={44} width={width - heroW - 260} />
                <div style={{ display: "flex", marginLeft: "auto" }}>
                  <Muted text={r.seed ? `seed ${r.seed}` : ""} size={24} />
                </div>
              </Row>
            ))}
          </div>
        ) : (
          <div style={{ display: "flex", gap }}>
            {rest.map((r, i) => (
              <Cut
                key={r.id}
                art={restArt[i]}
                box={{ width: cardW, height: restHeight }}
                color={tone(r)}
                border="top"
              >
                <Band padding="8px 12px">
                  <Place place={r.placement} size={44} />
                  <Name who={r} size={28} width={cardW - 70} />
                </Band>
              </Cut>
            ))}
          </div>
        ))}
    </div>
  );
}

// ---------------------------------------------------------------- 2. champion's path

async function campeon(d: Social, c: Ctx) {
  const champion = d.champion!;
  const path = d.champion_path;
  const { width, height } = c.body;
  const gap = 14;
  const heroBox = c.wide
    ? { width: Math.round(width * 0.38), height }
    : { width, height: Math.min(Math.round(height * 0.36), 470) };
  const listW = c.wide ? width - heroBox.width - 24 : width;
  const listH = c.wide ? height : height - heroBox.height - 24;
  const [art, icons] = await Promise.all([
    portrait(champion, 640),
    Promise.all(path.map((p) => icon(p.opponent))),
  ]);
  const won = path.filter((p) => p.won).length;
  const fromLosers = path.some((p) => !p.won);
  const seed = d.summary.top[0]?.seed;
  const h = rowHeight(listH, path.length, gap, 104);
  const font = Math.min(Math.round(h * 0.42), 40);
  return (
    <div
      style={{
        display: "flex",
        gap: 24,
        flexDirection: c.wide ? "row" : "column",
        width,
        height,
      }}
    >
      <Cut art={art} box={heroBox} color={tone(champion)}>
        <Side landscape={heroBox.width > heroBox.height * 1.3}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex" }}>
              <Chip text="CAMPEÓN" color={brand.gold} dark size={24} />
            </div>
            <Name
              who={champion}
              size={84}
              width={Math.round(heroBox.width * 0.55)}
            />
            <Muted
              text={[
                seed ? `Seed ${seed}` : null,
                `${won}-${path.length - won} en sets`,
                fromLosers ? "Ganó desde losers" : "Invicto",
              ]
                .filter(Boolean)
                .join(" · ")}
              size={28}
            />
          </div>
        </Side>
      </Cut>
      <div
        style={{ display: "flex", flexDirection: "column", gap, width: listW }}
      >
        {path.map((p, i) => (
          <Row key={i} height={h} color={p.won ? brand.gold : brand.fire}>
            <Chip
              text={p.won ? "G" : "P"}
              color={p.won ? brand.gold : brand.fire}
              dark={p.won}
              size={Math.round(font * 0.7)}
            />
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 4,
                width: listW - 330,
              }}
            >
              <Muted
                text={`${p.round ?? ""}${p.factor ? ` · sorpresa de ${p.factor}` : ""}`}
                size={Math.round(font * 0.6)}
              />
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Icon src={icons[i]} size={Math.round(font * 1.1)} />
                <Name who={p.opponent} size={font} width={listW - 420} />
                {p.opponent.seed && (
                  <Muted
                    text={`(seed ${p.opponent.seed})`}
                    size={Math.round(font * 0.6)}
                  />
                )}
              </div>
            </div>
            <div
              style={{
                display: "flex",
                marginLeft: "auto",
                fontSize: Math.round(font * 1.3),
                color: p.won ? brand.gold : brand.fire,
              }}
            >
              {p.score ?? (p.won ? "G" : "P")}
            </div>
          </Row>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- shared: one set side by side

function oriented(set: SocialSet, left: Ref) {
  const leftWon = set.winner.id === left.id;
  const [w, l] = (set.score ?? "").split("-");
  return {
    leftWon,
    score: set.score
      ? leftWon
        ? `${w}-${l}`
        : `${l}-${w}`
      : leftWon
        ? "G-P"
        : "P-G",
    games: set.games.map((g) => ({
      left: leftWon ? g.winner : g.loser,
      right: leftWon ? g.loser : g.winner,
      leftWon: g.won === null ? null : leftWon ? g.won : !g.won,
    })),
  };
}

async function versus(
  a: Ref,
  b: Ref,
  box: Box,
  middle: ReactNode,
  fadeB: boolean,
) {
  const mid = 260;
  const side = Math.round((box.width - mid) / 2);
  const [artA, artB] = await Promise.all([portrait(a, 640), portrait(b, 640)]);
  const card = (who: Ref, art: Art, fade: boolean) => (
    <Cut
      art={art}
      box={{ width: side, height: box.height }}
      color={tone(who)}
      fade={fade}
      border="top"
    >
      <Band padding="12px 18px">
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <Name who={who} size={52} width={side - 40} />
          {who.seed ? <Muted text={`seed ${who.seed}`} size={24} /> : null}
        </div>
      </Band>
    </Cut>
  );
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        width: box.width,
        height: box.height,
      }}
    >
      {card(a, artA, false)}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          width: mid,
          gap: 8,
        }}
      >
        {middle}
      </div>
      {card(b, artB, fadeB)}
    </div>
  );
}

// ---------------------------------------------------------------- 3. grand final

/** Mark beside the character that won the game (a blank of the same width if not). */
function Winner({ show }: { show: boolean }) {
  return (
    <div style={{ display: "flex", width: 92, justifyContent: "center" }}>
      {show && <Chip text="GANÓ" color={brand.gold} dark size={20} />}
    </div>
  );
}

async function final(d: Social, c: Ctx) {
  const sets = d.grand_final;
  const last = sets[sets.length - 1];
  const left = last.winner;
  const right = last.loser;
  const { width, height } = c.body;
  const lines = sets.map((s) => ({ set: s, ...oriented(s, left) }));
  const games = lines.flatMap((l, n) =>
    l.games.map((g, i) => ({
      ...g,
      label: `${sets.length > 1 && n ? "Reset · " : ""}Game ${i + 1}`,
    })),
  );
  const hasGames = games.some((g) => g.left || g.right);
  const vsH = hasGames ? Math.round(height * (c.wide ? 0.62 : 0.55)) : height;
  const middle = (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
      }}
    >
      <div style={{ display: "flex" }}>
        <Chip text="CAMPEÓN" color={brand.gold} dark size={22} />
      </div>
      {lines.map((l, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          <div
            style={{
              display: "flex",
              fontSize: i === lines.length - 1 ? 110 : 64,
              lineHeight: 1,
              color: brand.gold,
            }}
          >
            {l.score}
          </div>
          {lines.length > 1 && (
            <Muted text={i ? "Reset" : "Primer set"} size={22} />
          )}
        </div>
      ))}
    </div>
  );
  const vs = await versus(left, right, { width, height: vsH }, middle, true);
  if (!hasGames) return vs;
  const icons = await Promise.all(
    games.flatMap((g) => [stockIcon(g.left), stockIcon(g.right)]),
  );
  const listH = height - vsH - 20;
  const shown = games.slice(0, c.wide ? 10 : fitting(listH, 54, 8));
  const cols = c.wide ? columns(shown, 2) : [shown];
  const colW = Math.floor((width - 16 * (cols.length - 1)) / cols.length);
  const h = rowHeight(listH, cols[0].length, 8, 80);
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 20,
        width,
        height,
      }}
    >
      {vs}
      <div style={{ display: "flex", gap: 16 }}>
        {cols.map((col, ci) => (
          <div
            key={ci}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
              width: colW,
            }}
          >
            {col.map((g) => {
              const i = games.indexOf(g);
              return (
                <Row
                  key={i}
                  height={h}
                  color={g.leftWon ? tone(left) : tone(right)}
                >
                  <Muted text={g.label} size={24} />
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 18,
                      marginLeft: "auto",
                    }}
                  >
                    <Winner show={g.leftWon === true} />
                    <Icon src={icons[2 * i]} size={h - 16} />
                    <Muted text="vs" size={24} />
                    <Icon src={icons[2 * i + 1]} size={h - 16} />
                    <Winner show={g.leftWon === false} />
                  </div>
                </Row>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 4 & 6. sets as rows

async function setRows(sets: SocialSet[], box: Box, kind: "upset" | "close") {
  const gap = 12;
  const shown = sets.slice(0, fitting(box.height, 92, gap));
  const icons = await Promise.all(
    shown.flatMap((s) => [icon(s.winner), icon(s.loser)]),
  );
  const h = rowHeight(box.height, shown.length, gap, 180);
  const font = Math.min(Math.round(h * 0.34), 42);
  const nameW = Math.round((box.width - 330) / 2);
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap,
        width: box.width,
      }}
    >
      {shown.map((s, i) => (
        <Row key={i} height={h} color={tone(s.winner)}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
              flexGrow: 1,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Icon src={icons[2 * i]} size={Math.round(font * 1.2)} />
              <Name who={s.winner} size={font} width={nameW} />
              <Muted text="le ganó a" size={Math.round(font * 0.6)} />
              <Icon src={icons[2 * i + 1]} size={Math.round(font * 1.2)} />
              <Name who={s.loser} size={font} width={nameW} color={brand.ash} />
            </div>
            <Muted
              text={[
                kind === "upset" && s.winner.seed && s.loser.seed
                  ? `seed ${s.winner.seed} vs seed ${s.loser.seed}`
                  : null,
                s.round,
                s.comeback ? "remontada" : null,
              ]
                .filter(Boolean)
                .join(" · ")}
              size={Math.round(font * 0.58)}
            />
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-end",
              gap: 4,
            }}
          >
            <div
              style={{
                display: "flex",
                fontSize: Math.round(font * 1.3),
                color: brand.gold,
                lineHeight: 1,
              }}
            >
              {kind === "upset" ? `+${s.factor}` : (s.score ?? "")}
            </div>
            {kind === "upset" && s.score && <Muted text={s.score} size={22} />}
          </div>
        </Row>
      ))}
    </div>
  );
}

async function sorpresas(d: Social, c: Ctx) {
  const [first, ...rest] = d.upsets;
  const { width, height } = c.body;
  const heroBox = c.wide
    ? { width: Math.round(width * 0.5), height }
    : { width, height: rest.length ? Math.round(height * 0.5) : height };
  const middle = (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
      }}
    >
      <Muted text="sorpresa de" size={22} />
      <div
        style={{
          display: "flex",
          fontSize: 110,
          lineHeight: 1,
          color: brand.gold,
        }}
      >{`+${first.factor}`}</div>
      <Muted text={first.score ?? ""} size={40} />
      <Muted text={first.round ?? ""} size={20} />
    </div>
  );
  const hero = await versus(first.winner, first.loser, heroBox, middle, true);
  if (!rest.length) return hero;
  const list = await setRows(
    rest,
    c.wide
      ? { width: width - heroBox.width - 24, height }
      : { width, height: height - heroBox.height - 24 },
    "upset",
  );
  return (
    <div
      style={{
        display: "flex",
        flexDirection: c.wide ? "row" : "column",
        gap: 24,
        width,
        height,
      }}
    >
      {hero}
      {list}
    </div>
  );
}

async function peleados(d: Social, c: Ctx) {
  return setRows(d.close_sets, c.body, "close");
}

// ---------------------------------------------------------------- 5. seed performance

async function seeds(d: Social, c: Ctx) {
  const { width, height } = c.body;
  const gap = 16;
  const lead = d.over.slice(0, 3);
  const rest = d.over.slice(3);
  const under = c.under ? d.under.slice(0, 3) : [];
  const leadH = c.wide
    ? height
    : Math.round(height * (rest.length || under.length ? 0.5 : 1));
  const leadW = c.wide ? Math.round(width * 0.62) : width;
  const cardW = Math.floor((leadW - gap * (lead.length - 1)) / lead.length);
  const [arts, restIcons, underIcons] = await Promise.all([
    Promise.all(lead.map((p) => portrait(p, 640))),
    Promise.all(rest.map((p) => icon(p))),
    Promise.all(under.map((p) => icon(p))),
  ]);
  const listW = c.wide ? width - leadW - 24 : width;
  const listH = c.wide ? height : height - leadH - 24;
  const rows = [
    ...rest.map((p, i) => ({ p, src: restIcons[i], up: true })),
    ...under.map((p, i) => ({ p, src: underIcons[i], up: false })),
  ];
  const h = rows.length
    ? rowHeight(listH - (under.length ? 50 : 0), rows.length, 10, 100)
    : 0;
  const font = Math.min(Math.round(h * 0.42), 38);
  return (
    <div
      style={{
        display: "flex",
        flexDirection: c.wide ? "row" : "column",
        gap: 24,
        width,
        height,
      }}
    >
      <div style={{ display: "flex", gap, width: leadW }}>
        {lead.map((p, i) => (
          <Cut
            key={p.id}
            art={arts[i]}
            box={{ width: cardW, height: leadH }}
            color={tone(p)}
            border="top"
          >
            <div
              style={{
                position: "absolute",
                top: 16,
                right: 16,
                display: "flex",
              }}
            >
              <Chip text={`+${p.tiers}`} color={brand.gold} dark size={34} />
            </div>
            <Band padding="12px 16px">
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <Name
                  who={p}
                  size={lead.length > 2 ? 40 : 52}
                  width={cardW - 40}
                />
                <div
                  style={{ display: "flex", alignItems: "baseline", gap: 10 }}
                >
                  <Muted text={`seed ${p.seed} →`} size={26} />
                  <Place place={ordinal(p.placement)} size={44} />
                </div>
              </div>
            </Band>
          </Cut>
        ))}
      </div>
      {rows.length > 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            width: listW,
          }}
        >
          {rows.map(({ p, src, up }, i) => (
            <div
              key={p.id}
              style={{ display: "flex", flexDirection: "column", gap: 10 }}
            >
              {!up && (i === 0 || rows[i - 1].up) && (
                <Section title="Por debajo de su seed" size={26} />
              )}
              <Row height={h} color={tone(p)}>
                <Icon src={src} size={Math.round(font * 1.3)} />
                <Name who={p} size={font} width={listW - 380} />
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    gap: 12,
                    marginLeft: "auto",
                  }}
                >
                  <Muted
                    text={`seed ${p.seed} → ${ordinal(p.placement)}`}
                    size={Math.round(font * 0.7)}
                  />
                  <Chip
                    text={up ? `+${p.tiers}` : `${p.tiers}`}
                    color={up ? brand.gold : brand.fire}
                    dark={up}
                    size={Math.round(font * 0.7)}
                  />
                </div>
              </Row>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- 7. numbers

async function numeros(d: Social, c: Ctx) {
  const n = d.numbers;
  const { width, height } = c.body;
  const tiles = [
    { value: n.entrants ?? 0, label: "jugadores" },
    { value: n.sets, label: "sets jugados" },
    { value: n.games, label: "games" },
    { value: n.full_length, label: "sets al último game" },
    { value: n.sweeps, label: "barridas (sin perder un game)" },
    { value: n.comebacks, label: "remontadas tras perder el game 1" },
    { value: n.upsets, label: "sorpresas según el seed" },
    ...(n.characters
      ? [{ value: n.characters, label: "personajes distintos" }]
      : []),
  ].filter((t) => t.value || t.label === "jugadores");
  const art = n.top_character ? await renderArt(n.top_character, 1, 640) : null;
  const gap = 16;
  const per = c.wide ? 4 : 2;
  const grid = Array.from({ length: Math.ceil(tiles.length / per) }, (_, r) =>
    tiles.slice(r * per, r * per + per),
  );
  const rows = Math.ceil(tiles.length / per) + (art ? 1 : 0);
  const tileH = Math.floor((height - gap * (rows - 1)) / rows);
  const tileW = Math.floor((width - gap * (per - 1)) / per);
  const big = Math.min(Math.round(tileH * 0.55), 130);
  return (
    <div
      style={{ display: "flex", flexDirection: "column", gap, width, height }}
    >
      {grid.map((row, r) => (
        <div key={r} style={{ display: "flex", gap }}>
          {row.map((t) => (
            <div
              key={t.label}
              style={{
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                width: tileW,
                height: tileH,
                padding: "0 28px",
                background: brand.slab,
                borderLeft: `8px solid ${brand.fire}`,
              }}
            >
              <div
                style={{
                  display: "flex",
                  fontSize: big,
                  lineHeight: 1,
                  color: brand.gold,
                }}
              >
                {t.value.toLocaleString("es-PY")}
              </div>
              <Muted
                text={t.label}
                size={Math.min(Math.round(big * 0.3), 30)}
              />
            </div>
          ))}
        </div>
      ))}
      {art && n.top_character && (
        <Cut
          art={art}
          box={{ width, height: tileH }}
          color={toneOf(n.top_character)}
        >
          <div
            style={{
              position: "absolute",
              left: 28,
              top: 0,
              bottom: 0,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              gap: 6,
              padding: "14px 24px",
              background: "rgba(38,34,31,0.88)",
            }}
          >
            <Muted text="personaje más usado" size={26} />
            <div
              style={{
                display: "flex",
                fontSize: Math.min(Math.round(tileH * 0.4), 72),
                lineHeight: 1,
              }}
            >
              {n.top_character}
            </div>
          </div>
        </Cut>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- 8. characters

async function personajes(d: Social, c: Ctx) {
  const { width, height } = c.body;
  const items = d.characters.items;
  const cols = c.wide ? columns(items, 2) : [items];
  const gap = 12;
  const note = 40;
  const colW = Math.floor((width - 24 * (cols.length - 1)) / cols.length);
  const h = rowHeight(height - note, cols[0].length, gap, 150);
  const arts = await Promise.all(
    items.map((i) => renderArt(i.character, 1, 320)),
  );
  const top = Math.max(...items.map((i) => i.share));
  const font = Math.min(Math.round(h * 0.34), 44);
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        width,
        height,
      }}
    >
      <div style={{ display: "flex", gap: 24 }}>
        {cols.map((col, ci) => (
          <div
            key={ci}
            style={{
              display: "flex",
              flexDirection: "column",
              gap,
              width: colW,
            }}
          >
            {col.map((item) => {
              const i = items.indexOf(item);
              const color = toneOf(item.character);
              const barW = colW - h - 260;
              return (
                <div
                  key={item.character}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 18,
                    height: h,
                    background: brand.slab,
                    borderLeft: `6px solid ${color}`,
                  }}
                >
                  <Cut
                    art={arts[i]}
                    box={{ width: h, height: h }}
                    color={color}
                    border="none"
                  />
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                      width: barW,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        fontSize: fitText(item.character, font, barW),
                        lineHeight: 1,
                      }}
                    >
                      {item.character}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        height: Math.max(Math.round(h * 0.1), 8),
                        width: Math.max(
                          Math.round((barW * item.share) / top),
                          8,
                        ),
                        background: color,
                      }}
                    />
                    <Muted
                      text={`${item.games} games · ${item.players} ${item.players === 1 ? "jugador" : "jugadores"}`}
                      size={Math.round(font * 0.6)}
                    />
                  </div>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-end",
                      marginLeft: "auto",
                      paddingRight: 18,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        fontSize: Math.round(font * 1.2),
                        color: brand.gold,
                        lineHeight: 1,
                      }}
                    >{`${item.win_rate} %`}</div>
                    <Muted text="ganados" size={20} />
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <Muted
        text={`${d.characters.games} games con personajes reportados${
          d.characters.coverage !== null
            ? ` (${d.characters.coverage} % del torneo)`
            : ""
        } · % ganados = games ganados con ese personaje`}
        size={22}
      />
    </div>
  );
}

// ---------------------------------------------------------------- 9. debuts and returns

async function debutantes(d: Social, c: Ctx) {
  const { width, height } = c.body;
  const { debuts, returns, debut_count } = d.newcomers;
  const sections = [
    debuts.length ? "debuts" : null,
    returns.length ? "returns" : null,
  ].filter(Boolean);
  const [debutIcons, returnArts] = await Promise.all([
    Promise.all(debuts.map((p) => icon(p))),
    Promise.all(returns.map((p) => portrait(p, 320))),
  ]);
  const gap = 24;
  const debutCols = c.wide || debuts.length <= 4 ? 1 : 2;
  const perCol = Math.ceil(debuts.length / debutCols);
  const each = c.wide
    ? { width: Math.floor((width - gap) / sections.length), height }
    : {
        width,
        height: Math.floor(
          (height - gap * (sections.length - 1)) / sections.length,
        ),
      };
  // Stacked, the list takes what its rows need and the returns get the rest.
  const listH =
    !c.wide && sections.length > 1
      ? Math.min(110 + perCol * 110, Math.round(height * 0.6))
      : each.height;
  const returnsH =
    !c.wide && sections.length > 1 ? height - listH - gap : each.height;
  const debutH = rowHeight(listH - 100, perCol, 10, 100);
  const colW = Math.floor((each.width - 16 * (debutCols - 1)) / debutCols);
  const shownReturns = returns.slice(0, c.wide ? 4 : 3);
  const cardW = Math.floor(
    (each.width - 16 * (shownReturns.length - 1)) /
      Math.max(shownReturns.length, 1),
  );
  return (
    <div
      style={{
        display: "flex",
        flexDirection: c.wide ? "row" : "column",
        gap,
        width,
        height,
      }}
    >
      {debuts.length > 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 14,
            width: each.width,
            height: listH,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <Section title="Primer torneo en el hub" />
            <Chip
              text={String(debut_count)}
              color={brand.gold}
              dark
              size={26}
            />
          </div>
          <div style={{ display: "flex", gap: 16 }}>
            {columns(debuts, debutCols).map((col, ci) => (
              <div
                key={ci}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                  width: colW,
                }}
              >
                {col.map((p) => (
                  <Row key={p.id} height={debutH} color={tone(p)}>
                    <Icon
                      src={debutIcons[debuts.indexOf(p)]}
                      size={Math.round(debutH * 0.6)}
                    />
                    <Name
                      who={p}
                      size={Math.min(Math.round(debutH * 0.45), 40)}
                      width={colW - 230}
                    />
                    <div style={{ display: "flex", marginLeft: "auto" }}>
                      <Place
                        place={ordinal(p.placement)}
                        size={Math.min(Math.round(debutH * 0.5), 44)}
                      />
                    </div>
                  </Row>
                ))}
              </div>
            ))}
          </div>
          {debut_count > debuts.length && (
            <Muted text={`y ${debut_count - debuts.length} más`} size={24} />
          )}
        </div>
      )}
      {shownReturns.length > 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 14,
            width: each.width,
            height: returnsH,
          }}
        >
          <Section title="Volvieron" />
          <div style={{ display: "flex", gap: 16 }}>
            {shownReturns.map((p, i) => (
              <Cut
                key={p.id}
                art={returnArts[i]}
                box={{ width: cardW, height: returnsH - 60 }}
                color={tone(p)}
                border="top"
              >
                <Band padding="10px 16px">
                  <div
                    style={{ display: "flex", flexDirection: "column", gap: 4 }}
                  >
                    <Name who={p} size={40} width={cardW - 40} />
                    <Muted
                      text={`después de ${months(p.days ?? 0)} · ${ordinal(p.placement)}`}
                      size={22}
                    />
                  </div>
                </Band>
              </Cut>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- 10. ranking impact

async function ranking(d: Social, c: Ctx) {
  const r = d.ranking!;
  const { width, height } = c.body;
  const groups = [
    { title: "Subieron", rows: r.up, color: brand.gold },
    { title: "Entraron al ranking", rows: r.entered, color: brand.bone },
    { title: "Bajaron", rows: r.down, color: brand.fire },
  ].filter((g) => g.rows.length);
  const icons = await Promise.all(
    groups.map((g) =>
      Promise.all(g.rows.map((row) => stockIcon(row.mains?.[0]?.character))),
    ),
  );
  const total = groups.reduce((n, g) => n + g.rows.length, 0);
  const cols = c.wide ? Math.min(groups.length, 3) : 1;
  const colW = Math.floor((width - 24 * (cols - 1)) / cols);
  const headers = c.wide ? 1 : groups.length;
  const perCol = c.wide ? Math.max(...groups.map((g) => g.rows.length)) : total;
  const h = rowHeight(height - 70 - headers * 48, perCol, 10, 96);
  const font = Math.min(Math.round(h * 0.42), 40);
  const change = (row: ImpactRow) =>
    row.previous === null
      ? `entra ${ordinal(row.place)}`
      : `${ordinal(row.previous)} → ${ordinal(row.place)}`;
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 18,
        width,
        height,
      }}
    >
      <Muted
        text={`Ranking oficial: ${r.name}, antes y después de este torneo`}
        size={28}
      />
      <div
        style={{
          display: "flex",
          flexDirection: c.wide ? "row" : "column",
          gap: c.wide ? 24 : 18,
        }}
      >
        {groups.map((g, gi) => (
          <div
            key={g.title}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 10,
              width: colW,
            }}
          >
            <Section title={g.title} size={28} />
            {g.rows.map((row, i) => (
              <Row
                key={row.player_id}
                height={h}
                color={toneOf(row.mains?.[0]?.character)}
              >
                <Icon src={icons[gi][i]} size={Math.round(font * 1.3)} />
                <Name
                  who={{ tag: row.gamer_tag }}
                  size={font}
                  width={colW - 400}
                />
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 14,
                    marginLeft: "auto",
                  }}
                >
                  <Muted text={change(row)} size={Math.round(font * 0.7)} />
                  {row.change !== null && (
                    <Chip
                      text={
                        row.change > 0 ? `+${row.change}` : String(row.change)
                      }
                      color={g.color}
                      dark={row.change > 0}
                      size={Math.round(font * 0.7)}
                    />
                  )}
                </div>
              </Row>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 11. achievements

async function logros(d: Social, c: Ctx) {
  const { width, height } = c.body;
  const cols = c.wide ? 2 : 1;
  const gap = 14;
  const fit = fitting(height, 120, gap) * cols;
  const items = d.achievements.slice(0, fit);
  const groups = columns(items, cols);
  const colW = Math.floor((width - 24 * (cols - 1)) / cols);
  const h = rowHeight(
    height - (d.achievements.length > items.length ? 40 : 0),
    groups[0].length,
    gap,
    250,
  );
  const font = Math.min(Math.round(h * 0.26), 56);
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 10,
        width,
        height,
      }}
    >
      <div style={{ display: "flex", gap: 24 }}>
        {groups.map((col, ci) => (
          <div
            key={ci}
            style={{
              display: "flex",
              flexDirection: "column",
              gap,
              width: colW,
            }}
          >
            {col.map((a) => {
              const color = RARITY[a.rarity] ?? brand.ash;
              const names = a.players.map((p) => p.tag);
              const who =
                names.length > 4
                  ? `${names.slice(0, 4).join(", ")} y ${names.length - 4} más`
                  : names.join(", ");
              return (
                <div
                  key={a.id}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "center",
                    gap: 8,
                    height: h,
                    padding: "0 22px",
                    background: brand.slab,
                    borderLeft: `8px solid ${color}`,
                  }}
                >
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 14 }}
                  >
                    <div
                      style={{
                        display: "flex",
                        fontSize: fitText(a.name, font, colW - 260),
                        lineHeight: 1,
                      }}
                    >
                      {a.name}
                    </div>
                    <div style={{ display: "flex", marginLeft: "auto" }}>
                      <Chip
                        text={a.rarity_name}
                        color={color}
                        dark
                        size={Math.round(font * 0.5)}
                      />
                    </div>
                  </div>
                  <Muted text={a.description} size={Math.round(font * 0.55)} />
                  <div
                    style={{
                      display: "flex",
                      fontSize: Math.round(font * 0.62),
                      color: brand.gold,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                    }}
                  >
                    {who}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {d.achievements.length > items.length && (
        <Muted
          text={`y ${d.achievements.length - items.length} logros más en el hub`}
          size={24}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------- 12. Prode

async function prode(d: Social, c: Ctx) {
  const p = d.prode!;
  const { width, height } = c.body;
  const statsH = 150;
  const rows = p.ranking.slice(0, fitting(height - statsH - 20, 70, 10));
  const h = rowHeight(height - statsH - 20, rows.length, 10, 110);
  const font = Math.min(Math.round(h * 0.42), 46);
  const tile = (value: string, label: string) => (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        flexGrow: 1,
        height: statsH,
        padding: "0 26px",
        background: brand.slab,
        borderLeft: `8px solid ${brand.fire}`,
      }}
    >
      <div
        style={{
          display: "flex",
          fontSize: 72,
          lineHeight: 1,
          color: brand.gold,
        }}
      >
        {value}
      </div>
      <Muted text={label} size={24} />
    </div>
  );
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 20,
        width,
        height,
      }}
    >
      <div style={{ display: "flex", gap: 16 }}>
        {tile(String(p.participants), "pronosticaron")}
        {p.champion &&
          tile(String(p.champion_hits), `acertaron al campeón (${p.champion})`)}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {rows.map((r, i) => (
          <Row
            key={i}
            height={h}
            color={
              r.rank === 1 ? brand.gold : r.rank <= 3 ? brand.fire : NEUTRAL
            }
          >
            <div style={{ display: "flex", width: 70 }}>
              <Place place={r.rank} size={Math.round(font * 1.2)} />
            </div>
            <Name who={{ tag: r.name }} size={font} width={width - 480} />
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 18,
                marginLeft: "auto",
              }}
            >
              <Muted
                text={`${r.hits} ${r.hits === 1 ? "acierto" : "aciertos"} · ${r.exact_hits} ${r.exact_hits === 1 ? "exacto" : "exactos"}`}
                size={Math.round(font * 0.55)}
              />
              <div
                style={{
                  display: "flex",
                  fontSize: Math.round(font * 1.1),
                  color: brand.gold,
                }}
              >{`${r.points} pts`}</div>
            </div>
          </Row>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 13. rivalry

async function rivalidad(d: Social, c: Ctx) {
  const r = d.rivalries[0];
  const { width, height } = c.body;
  const listN = r.here.length;
  const vsH = Math.round(height * (c.wide ? 0.6 : 0.62));
  const middle = (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
      }}
    >
      <Muted text="historial" size={22} />
      <div
        style={{
          display: "flex",
          fontSize: 96,
          lineHeight: 1,
          color: brand.gold,
        }}
      >{`${r.after[0]}-${r.after[1]}`}</div>
      <Muted text={`antes: ${r.before[0]}-${r.before[1]}`} size={26} />
    </div>
  );
  const vs = await versus(r.a, r.b, { width, height: vsH }, middle, false);
  const listH = height - vsH - 24;
  const h = rowHeight(listH - 44, listN, 10, 110);
  const font = Math.min(Math.round(h * 0.42), 40);
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 24,
        width,
        height,
      }}
    >
      {vs}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <Section title={`En ${d.tournament.name}`} size={26} />
        {r.here.map((s, i) => (
          <Row key={i} height={h} color={tone(s.winner)}>
            <Name who={s.winner} size={font} width={Math.round(width * 0.35)} />
            <Muted
              text={`le ganó ${s.score ?? ""}`}
              size={Math.round(font * 0.7)}
            />
            <div style={{ display: "flex", marginLeft: "auto" }}>
              <Muted text={s.round ?? ""} size={Math.round(font * 0.6)} />
            </div>
          </Row>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- frame

const BODIES: Record<CardKey, (d: Social, c: Ctx) => Promise<ReactNode>> = {
  podio,
  campeon,
  final,
  sorpresas,
  seeds,
  peleados,
  numeros,
  personajes,
  debutantes,
  ranking,
  logros,
  prode,
  rivalidad,
};

const RENDERS = new Set<CardKey>([
  "podio",
  "campeon",
  "final",
  "sorpresas",
  "seeds",
  "numeros",
  "personajes",
  "debutantes",
  "rivalidad",
]);

function subtitle(d: Social) {
  const date = d.tournament.starts_at
    ? new Date(d.tournament.starts_at).toLocaleDateString("es-PY", {
        timeZone: "America/Asuncion",
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : null;
  return [
    d.summary.main === false ? d.summary.event : null,
    date,
    d.summary.entrants ? `${d.summary.entrants} jugadores` : null,
    d.tournament.city,
  ]
    .filter(Boolean)
    .join(" · ");
}

export async function tournamentCard(
  d: Social,
  key: CardKey,
  title: string,
  format: Format,
  options: { under?: boolean } = {},
) {
  const { width, height } = FORMATS[format];
  const wide = format === "wide";
  // Stories keep clear of the profile bar and the reply box.
  const padY = format === "story" ? 170 : wide ? 52 : 48;
  const padX = wide ? 60 : 48;
  const header = 128;
  const footer = 30;
  const gap = 28;
  const body = {
    width: width - 2 * padX,
    height: height - 2 * padY - header - footer - 2 * gap,
  };
  const [fontData, logo, content] = await Promise.all([
    brand.font(),
    brand.logo(),
    BODIES[key](d, { format, wide, body, under: Boolean(options.under) }),
  ]);
  const name = d.tournament.name;
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        gap,
        padding: `${padY}px ${padX}px`,
        background: brand.concrete,
        backgroundImage: `linear-gradient(180deg, ${brand.concrete} 70%, #1d1a18 100%)`,
        color: brand.bone,
        fontFamily: fontData ? "Display" : undefined,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 24,
          height: header,
        }}
      >
        {logo && (
          <img
            src={logo}
            width={96}
            height={96}
            style={{ borderRadius: 48 }}
            alt=""
          />
        )}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 6,
            width: body.width - 120,
          }}
        >
          <div
            style={{
              display: "flex",
              fontSize: 30,
              color: brand.fire,
              letterSpacing: 3,
              textTransform: "uppercase",
            }}
          >
            {title}
          </div>
          <div
            style={{
              display: "flex",
              fontSize: fitText(name, 58, body.width - 120),
              lineHeight: 1,
              whiteSpace: "nowrap",
              overflow: "hidden",
            }}
          >
            {name}
          </div>
          <Muted text={subtitle(d)} size={26} />
        </div>
      </div>
      <div style={{ display: "flex", width: body.width, height: body.height }}>
        {content}
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          height: footer,
          fontSize: 22,
          color: brand.ash,
        }}
      >
        <span>Smash Club Paraguay · smashclubpy.com</span>
        <span>
          {RENDERS.has(key)
            ? "Renders: Super Smash Bros. Ultimate © Nintendo"
            : ""}
        </span>
      </div>
    </div>,
    {
      width,
      height,
      fonts: fontData
        ? [{ name: "Display", data: fontData, weight: 800, style: "normal" }]
        : undefined,
      headers: { "Cache-Control": "public, max-age=120" },
    },
  );
}
