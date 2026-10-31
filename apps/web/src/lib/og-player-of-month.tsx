import { ImageResponse } from "next/og";
import { characterColor } from "./characters";
import { brand, renderArt, fitArt, type Art } from "./og";

type Win = { tag: string | null; seed: number | null };

export type MonthResult = {
  tournament: string;
  placement: number;
  entrants: number | null;
  seed: number | null;
  upsets: number;
  wins?: Win[];
};

export type MonthWinner = {
  tag: string | null;
  prefix?: string | null;
  points: number;
  results: MonthResult[];
  mains?: { character: string; costume?: number }[];
};

export type MonthRegion = {
  name: string;
  winner: MonthWinner | null;
  runners: { tag: string | null; points: number }[];
};

export type MonthData = {
  label: string;
  in_progress: boolean;
  regions: MonthRegion[];
};

const WIDTH = 1080;
const HEIGHT = 1350;
const PICTURE = { width: 520, height: 540 };

/** Size of the picture beside each player; uploaded photos are cropped to it. */
export const pictureSlot = () => PICTURE;

const points = (value: number) => value.toLocaleString("es-PY");

function list(items: string[]) {
  return items.length < 2
    ? items.join("")
    : `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

/** What the player did at one tournament, in words the community can check. */
export function resultLines(r: MonthResult) {
  const size = r.entrants ? ` de ${r.entrants}` : "";
  const facts = [];
  if (r.seed) facts.push(`Era seed ${r.seed}`);
  if (r.upsets)
    facts.push(r.upsets === 1 ? "1 sorpresa" : `${r.upsets} sorpresas`);
  const beaten = (r.wins ?? [])
    .filter((w) => w.tag)
    .map((w) => (w.seed ? `${w.tag} (seed ${w.seed})` : `${w.tag}`));
  return {
    title: `${r.placement}.º${size} en ${r.tournament}`,
    facts: facts.join(" · "),
    beaten: beaten.length ? `Le ganó a ${list(beaten)}` : "",
  };
}

function Panel({
  region,
  art,
  height,
}: {
  region: MonthRegion;
  art: Art;
  height: number;
}) {
  const w = region.winner!;
  const solo = height > 700; // only one region had tournaments: the panel fills the image
  const main = w.mains?.[0]?.character;
  const tone = (main && characterColor(main)) || "#5a514a";
  const size =
    art && !art.fill && fitArt(art, solo ? 760 : 560, solo ? 760 : height + 30);
  const tag = w.tag ?? "";
  const crowded = w.results.length > 2;
  const big = solo ? 42 : crowded ? 27 : 32;
  const small = solo ? 33 : crowded ? 22 : 26;
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        height,
        overflow: "hidden",
        borderLeft: `12px solid ${tone}`,
        backgroundImage: `linear-gradient(100deg, ${brand.slab} 48%, ${tone}99 100%)`,
      }}
    >
      {art &&
        (art.fill ? (
          <img
            src={art.src}
            width={art.width}
            height={art.height}
            style={{ position: "absolute", top: 0, right: 0 }}
            alt=""
          />
        ) : (
          size && (
            <img
              src={art.src}
              width={size.width}
              height={size.height}
              style={{
                position: "absolute",
                top: solo
                  ? height - size.height - 24
                  : Math.round((height - size.height) / 2),
                right: solo
                  ? -30
                  : Math.round((PICTURE.width - size.width) / 2) - 20,
              }}
              alt=""
            />
          )
        ))}
      <div
        style={{
          position: "relative",
          display: "flex",
          flexDirection: "column",
          width: 640,
          padding: "26px 0 22px 30px",
        }}
      >
        <div
          style={{
            display: "flex",
            fontSize: 28,
            color: brand.gold,
            letterSpacing: 2,
          }}
        >
          {region.name.toUpperCase()}
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 14,
            marginTop: 2,
          }}
        >
          {w.prefix && (
            <div style={{ display: "flex", fontSize: 40, color: brand.ash }}>
              {w.prefix} |
            </div>
          )}
          <div
            style={{
              display: "flex",
              fontSize: solo ? 124 : tag.length > 11 ? 66 : 88,
              lineHeight: 1.05,
            }}
          >
            {tag}
          </div>
        </div>
        <div
          style={{
            display: "flex",
            fontSize: 32,
            color: brand.fire,
            marginTop: 2,
          }}
        >
          {points(w.points)} puntos
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            marginTop: 12,
          }}
        >
          {w.results.slice(0, 3).map((r) => {
            const line = resultLines(r);
            return (
              <div
                key={r.tournament}
                style={{ display: "flex", flexDirection: "column" }}
              >
                <div style={{ display: "flex", fontSize: big }}>
                  {line.title}
                </div>
                <div
                  style={{ display: "flex", fontSize: small, color: brand.ash }}
                >
                  {line.facts}
                </div>
                {line.beaten && (
                  <div
                    style={{
                      display: "flex",
                      fontSize: small,
                      color: brand.ash,
                    }}
                  >
                    {line.beaten}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        {region.runners.length > 0 && (
          <div
            style={{
              display: "flex",
              marginTop: "auto",
              fontSize: 21,
              color: brand.ash,
            }}
          >
            Le siguen{" "}
            {list(region.runners.map((x) => `${x.tag} (${points(x.points)})`))}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Players of the month for social media (1080×1350): one panel per region with the main's
 * render, the points and what they did, so the community sees why they won (Mission 28).
 */
export async function playerOfMonthImage(
  data: MonthData,
  uploads: Map<number, Art> = new Map(),
) {
  const regions = data.regions.filter((r) => r.winner);
  const [fontData, logo, pictures] = await Promise.all([
    brand.font(),
    brand.logo(),
    Promise.all(
      regions.map(async (r, i) => {
        const main = r.winner!.mains?.[0];
        return uploads.get(i) ?? renderArt(main?.character, main?.costume, 640);
      }),
    ),
  ]);
  const gap = 18;
  const room = HEIGHT - 72 - 112 - 66;
  const height = Math.floor(
    (room - gap * (regions.length - 1)) / regions.length,
  );
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: brand.concrete,
        color: brand.bone,
        padding: "36px 40px",
        fontFamily: fontData ? "Display" : undefined,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 22,
          height: 112,
          marginBottom: 0,
        }}
      >
        {logo && (
          <img
            src={logo}
            width={92}
            height={92}
            style={{ borderRadius: 46 }}
            alt=""
          />
        )}
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontSize: 62, lineHeight: 1 }}>
            {regions.length > 1 ? "Jugadores del mes" : "Jugador del mes"}
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 30,
              color: brand.gold,
              marginTop: 4,
            }}
          >
            {data.label}
            {data.in_progress ? " (en curso)" : ""}
          </div>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap }}>
        {regions.map((r, i) => (
          <Panel key={r.name} region={r} art={pictures[i]} height={height} />
        ))}
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          marginTop: "auto",
          fontSize: 20,
          color: brand.ash,
        }}
      >
        <div style={{ display: "flex", fontSize: 23, color: brand.bone }}>
          Premia superar lo esperado: terminar por encima del seed y ganarle a
          mejores seeds.
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <div style={{ display: "flex" }}>Smash Club Paraguay</div>
          <div style={{ display: "flex" }}>
            Renders: Super Smash Bros. Ultimate © Nintendo
          </div>
        </div>
      </div>
    </div>,
    {
      width: WIDTH,
      height: HEIGHT,
      fonts: fontData
        ? [{ name: "Display", data: fontData, weight: 800, style: "normal" }]
        : undefined,
    },
  );
}
