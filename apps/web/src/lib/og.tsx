import { readFile } from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";
import { characterColor, characterKey } from "./characters";
import { render, type RenderWidth } from "./renders";
import { apiBase } from "./origin";

export { apiBase };

/**
 * Square (1080×1080) share images for Instagram and Discord, laid out as a podium:
 * the champion large, 2nd and 3rd medium, 4th to 8th as cards and 9th to 12th in a
 * small row, each with the official render of the player's main and chosen costume.
 */
export type OgRow = {
  place: number;
  tag: string;
  main?: string | null;
  costume?: number;
  detail?: string;
};
// fill: an uploaded photo already cropped to its slot (see og-uploads.ts).
export type Art = {
  src: string;
  width: number;
  height: number;
  fill?: boolean;
} | null;

const CONCRETE = "#26221f";
const SLAB = "#302b27";
const BONE = "#efe9df";
const ASH = "#a2988d";
const INNER = 1000;
const CARD_WIDTH = Math.floor((INNER - 4 * 15) / 5);
const SMALL_WIDTH = Math.floor((INNER - 3 * 16) / 4);

/** Visible size of the picture in each row's slot (inside the colored border). */
export function slotSize(index: number) {
  if (index === 0) return { width: 550, height: 520 };
  if (index < 3) return { width: 416, height: 252 };
  if (index < 8) return { width: CARD_WIDTH, height: 208 };
  return { width: 38, height: 38 };
}

function Photo({ art }: { art: NonNullable<Art> }) {
  return (
    <img
      src={art.src}
      width={art.width}
      height={art.height}
      style={{ position: "absolute", top: 0, left: 0 }}
      alt=""
    />
  );
}

let font: Promise<ArrayBuffer | null> | null = null;
function displayFont() {
  font ??= (async () => {
    try {
      const css = await (
        await fetch(
          "https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800",
        )
      ).text();
      const url = css.match(
        /src: url\((.+?)\) format\(["'](opentype|truetype)["']\)/,
      )?.[1];
      return url ? await (await fetch(url)).arrayBuffer() : null;
    } catch {
      font = null;
      return null;
    }
  })();
  return font;
}

// Image renderers refuse to fetch local addresses, so public files are inlined.
async function inline(file: string) {
  try {
    const data = await readFile(path.join(process.cwd(), "public", file));
    const type = file.endsWith(".svg") ? "image/svg+xml" : "image/jpeg";
    return `data:${type};base64,${data.toString("base64")}`;
  } catch {
    return null;
  }
}

/** Official render of the main in the chosen costume; the stock icon if it fails. */
async function art(row: OgRow, width: RenderWidth): Promise<Art> {
  const key = row.main ? characterKey(row.main) : null;
  if (!key) return null;
  const r = await render(key, row.costume ?? 1, width);
  if (r)
    return {
      src: `data:image/png;base64,${r.data.toString("base64")}`,
      width: r.width,
      height: r.height,
    };
  const icon = await inline(`characters/${key}.svg`);
  return icon ? { src: icon, width: 200, height: 200 } : null;
}

async function stock(row: OgRow): Promise<Art> {
  const key = row.main ? characterKey(row.main) : null;
  const src = key ? await inline(`characters/${key}.svg`) : null;
  return src ? { src, width: 200, height: 200 } : null;
}

function fit(a: NonNullable<Art>, maxWidth: number, maxHeight: number) {
  const scale = Math.min(maxWidth / a.width, maxHeight / a.height);
  return {
    width: Math.round(a.width * scale),
    height: Math.round(a.height * scale),
  };
}

function color(row: OgRow) {
  return (row.main && characterColor(row.main)) || "#5a514a";
}

function placeColor(place: number) {
  if (place === 1) return "#f3a81f";
  if (place <= 3) return "#e5541b";
  return BONE;
}

function Place({ place, size }: { place: number; size: number }) {
  return (
    <div
      style={{
        display: "flex",
        fontSize: size,
        lineHeight: 0.8,
        transform: "skewX(-10deg)",
        color: placeColor(place),
      }}
    >
      {place}
    </div>
  );
}

/** 1st, 2nd and 3rd: full render on the main's color, name on a band at the bottom. */
function PodiumCard({
  row,
  art,
  width,
  height,
  big,
}: {
  row: OgRow;
  art: Art;
  width: number;
  height: number;
  big: boolean;
}) {
  const size = art && fit(art, width - 30, height + (big ? 40 : 20));
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        width,
        height,
        overflow: "hidden",
        background: SLAB,
        borderLeft: `${big ? 10 : 8}px solid ${color(row)}`,
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
          background: `${color(row)}${big ? "55" : "3a"}`,
        }}
      />
      {art?.fill && <Photo art={art} />}
      {art && !art.fill && size && (
        <img
          src={art.src}
          width={size.width}
          height={size.height}
          style={{ position: "absolute", right: 6, bottom: big ? -40 : -20 }}
          alt=""
        />
      )}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          display: "flex",
          alignItems: "flex-end",
          gap: big ? 20 : 14,
          padding: big ? "16px 22px" : "10px 16px",
          background: "rgba(38,34,31,0.95)",
        }}
      >
        <Place place={row.place} size={big ? 110 : 64} />
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{ display: "flex", fontSize: big ? 58 : 38, lineHeight: 1 }}
          >
            {row.tag}
          </div>
          {row.detail && (
            <div
              style={{ display: "flex", fontSize: big ? 26 : 22, color: ASH }}
            >
              {row.detail}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** 4th to 8th: upper body of the render, cropped by the card. */
function Card({ row, art, width }: { row: OgRow; art: Art; width: number }) {
  const height = 214;
  const size = art && fit(art, width + 50, 320);
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        width,
        height,
        overflow: "hidden",
        background: SLAB,
        borderTop: `6px solid ${color(row)}`,
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
          background: `${color(row)}30`,
        }}
      />
      {art?.fill && <Photo art={art} />}
      {art && !art.fill && size && (
        <img
          src={art.src}
          width={size.width}
          height={size.height}
          style={{
            position: "absolute",
            top: 4,
            left: Math.round((width - size.width) / 2),
          }}
          alt=""
        />
      )}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          display: "flex",
          alignItems: "flex-end",
          gap: 10,
          padding: "8px 12px",
          background: "rgba(38,34,31,0.95)",
        }}
      >
        <Place place={row.place} size={44} />
        <div
          style={{
            display: "flex",
            fontSize: 28,
            lineHeight: 1,
            overflow: "hidden",
            whiteSpace: "nowrap",
          }}
        >
          {row.tag}
        </div>
      </div>
    </div>
  );
}

/** 9th to 12th: stock icon (or the uploaded picture), place and tag. */
function Small({ row, art, width }: { row: OgRow; art: Art; width: number }) {
  const size = art && (art.fill ? art : fit(art, 38, 38));
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        width,
        height: 56,
        padding: "0 12px",
        background: SLAB,
        borderLeft: `5px solid ${color(row)}`,
      }}
    >
      <Place place={row.place} size={34} />
      {art && size ? (
        <div
          style={{
            display: "flex",
            width: 38,
            height: 38,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <img
            src={art.src}
            width={size.width}
            height={size.height}
            style={{ borderRadius: art.fill ? 19 : 0 }}
            alt=""
          />
        </div>
      ) : (
        <div style={{ display: "flex", width: 38 }} />
      )}
      <div
        style={{
          display: "flex",
          fontSize: 26,
          overflow: "hidden",
          whiteSpace: "nowrap",
        }}
      >
        {row.tag}
      </div>
    </div>
  );
}

export async function shareImage(
  request: Request,
  {
    title,
    subtitle,
    rows,
    uploads = new Map(),
  }: {
    title: string;
    subtitle: string;
    rows: OgRow[];
    /** Pictures organizers uploaded, by row index; they replace the render. */
    uploads?: Map<number, Art>;
  },
) {
  const pick = (index: number, fallback: () => Promise<Art>) =>
    uploads.get(index) ?? fallback();
  const podium = rows.slice(0, 3);
  const cards = rows.slice(3, 8);
  const small = rows.slice(8, 12);
  const [fontData, logo, podiumArt, cardArt, smallIcons] = await Promise.all([
    displayFont(),
    inline("smashclublogo.jpg"),
    Promise.all(podium.map((r, i) => pick(i, () => art(r, 640)))),
    Promise.all(cards.map((r, i) => pick(i + 3, () => art(r, 320)))),
    Promise.all(small.map((r, i) => pick(i + 8, () => stock(r)))),
  ]);
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: CONCRETE,
        color: BONE,
        padding: 40,
        fontFamily: fontData ? "Display" : undefined,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
        {logo && (
          <img
            src={logo}
            width={84}
            height={84}
            style={{ borderRadius: 42 }}
            alt=""
          />
        )}
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontSize: 56, lineHeight: 1 }}>
            {title}
          </div>
          <div
            style={{ display: "flex", fontSize: 26, color: ASH, marginTop: 6 }}
          >
            {subtitle}
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 16, marginTop: 20, height: 520 }}>
        {podium[0] && (
          <PodiumCard
            row={podium[0]}
            art={podiumArt[0]}
            width={560}
            height={520}
            big
          />
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {podium.slice(1).map((r, i) => (
            <PodiumCard
              key={`${r.place}-${r.tag}`}
              row={r}
              art={podiumArt[i + 1]}
              width={424}
              height={252}
              big={false}
            />
          ))}
        </div>
      </div>
      {cards.length > 0 && (
        <div style={{ display: "flex", gap: 15, marginTop: 16 }}>
          {cards.map((r, i) => (
            <Card
              key={`${r.place}-${r.tag}`}
              row={r}
              art={cardArt[i]}
              width={CARD_WIDTH}
            />
          ))}
        </div>
      )}
      {small.length > 0 && (
        <div style={{ display: "flex", gap: 16, marginTop: 16 }}>
          {small.map((r, i) => (
            <Small
              key={`${r.place}-${r.tag}`}
              row={r}
              art={smallIcons[i]}
              width={SMALL_WIDTH}
            />
          ))}
        </div>
      )}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: "auto",
          fontSize: 24,
          color: ASH,
        }}
      >
        <span>Smash Club Paraguay</span>
        <span>Renders: Super Smash Bros. Ultimate © Nintendo</span>
      </div>
    </div>,
    {
      width: 1080,
      height: 1080,
      fonts: fontData
        ? [{ name: "Display", data: fontData, weight: 800, style: "normal" }]
        : undefined,
      headers: { "Cache-Control": "public, max-age=600" },
    },
  );
}

export type PlayerCardData = {
  tag: string;
  main?: string | null;
  costume?: number;
  ranking?: { name: string; place: number } | null;
  wins?: number;
  losses?: number;
  badges: string[];
  best?: { placement: number; tournament: string; entrants: number | null };
};

/** 1200×630 link preview for a player: render of the main, ranking, record, badges. */
export async function playerCard(data: PlayerCardData) {
  const row: OgRow = {
    place: 0,
    tag: data.tag,
    main: data.main,
    costume: data.costume,
  };
  const [fontData, logo, picture] = await Promise.all([
    displayFont(),
    inline("smashclublogo.jpg"),
    art(row, 640),
  ]);
  const size = picture && fit(picture, 470, 660);
  const sets = (data.wins ?? 0) + (data.losses ?? 0);
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        background: CONCRETE,
        color: BONE,
        fontFamily: fontData ? "Display" : undefined,
      }}
    >
      <div
        style={{
          position: "relative",
          display: "flex",
          width: 480,
          height: 630,
          overflow: "hidden",
          background: SLAB,
          borderRight: `10px solid ${color(row)}`,
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
            background: `${color(row)}55`,
          }}
        />
        {picture && size && (
          <img
            src={picture.src}
            width={size.width}
            height={size.height}
            style={{
              position: "absolute",
              left: Math.round((470 - size.width) / 2),
              top: 30,
            }}
            alt=""
          />
        )}
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: 720,
          padding: "44px 48px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {logo && (
            <img
              src={logo}
              width={52}
              height={52}
              style={{ borderRadius: 26 }}
              alt=""
            />
          )}
          <div style={{ display: "flex", fontSize: 28, color: ASH }}>
            Smash Club Paraguay
          </div>
        </div>
        <div
          style={{
            display: "flex",
            fontSize: data.tag.length > 12 ? 76 : 104,
            lineHeight: 1,
            marginTop: 30,
          }}
        >
          {data.tag}
        </div>
        {data.ranking && (
          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              gap: 14,
              marginTop: 18,
            }}
          >
            <div style={{ display: "flex", fontSize: 32, color: ASH }}>N.º</div>
            <Place place={data.ranking.place} size={72} />
            <div style={{ display: "flex", fontSize: 32, color: ASH }}>
              {`del ${data.ranking.name}`}
            </div>
          </div>
        )}
        {sets > 0 && (
          <div style={{ display: "flex", fontSize: 34, marginTop: 16 }}>
            {`${data.wins}–${data.losses} en sets, ${Math.round(
              (100 * (data.wins ?? 0)) / sets,
            )} % ganados`}
          </div>
        )}
        {data.badges.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 10,
              marginTop: 22,
              width: 624,
            }}
          >
            {data.badges.slice(0, 3).map((b) => (
              <div
                key={b}
                style={{
                  display: "flex",
                  fontSize: 26,
                  padding: "6px 14px",
                  background: SLAB,
                  borderLeft: "5px solid #f3a81f",
                }}
              >
                {b}
              </div>
            ))}
          </div>
        )}
        {data.best && (
          <div
            style={{
              display: "flex",
              marginTop: "auto",
              fontSize: 28,
              color: ASH,
            }}
          >
            {`Mejor resultado: ${data.best.placement}.º en ${data.best.tournament}${
              data.best.entrants ? ` (${data.best.entrants} jugadores)` : ""
            }`}
          </div>
        )}
      </div>
    </div>,
    {
      width: 1200,
      height: 630,
      fonts: fontData
        ? [{ name: "Display", data: fontData, weight: 800, style: "normal" }]
        : undefined,
      headers: { "Cache-Control": "public, max-age=600" },
    },
  );
}

/** Shared look for other share images (og-monthly.tsx). */
export const brand = {
  concrete: CONCRETE,
  slab: SLAB,
  bone: BONE,
  ash: ASH,
  gold: "#f3a81f",
  fire: "#e5541b",
  font: displayFont,
  logo: () => inline("smashclublogo.jpg"),
};

/** Official render of a character (the stock icon if it fails), for other images. */
export function renderArt(
  main: string | undefined,
  costume: number | undefined,
  width: RenderWidth,
) {
  return art({ place: 0, tag: "", main, costume }, width);
}

export const fitArt = fit;

/** Stock icon of a character as a data URI, or null. */
export async function stockIcon(main?: string | null) {
  return (await stock({ place: 0, tag: "", main }))?.src ?? null;
}
