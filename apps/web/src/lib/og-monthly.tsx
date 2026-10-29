import { ImageResponse } from "next/og";
import { characterColor } from "./characters";
import { brand, stockIcon } from "./og";

export type MonthlyRow = {
  place: number;
  change: number | null;
  new: boolean;
  tag: string;
  prefix?: string | null;
  main?: string | null;
  wins: number;
  losses: number;
};

export type MonthlyData = {
  title: string;
  label: string;
  requirements: string;
  highlights: string;
  rows: MonthlyRow[];
};

const UP = "#4caf50";
const DOWN = "#e05545";
const PER_COLUMN = 32;

function Change({ row }: { row: MonthlyRow }) {
  const [text, tone] = row.new
    ? ["NUEVO", brand.gold]
    : row.change === null || row.change === 0
      ? ["=", brand.ash]
      : row.change > 0
        ? [`+${row.change}`, UP]
        : [`−${-row.change}`, DOWN];
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        width: 58,
        fontSize: row.new ? 15 : 20,
        color: tone,
      }}
    >
      {text}
    </div>
  );
}

function placeColor(place: number) {
  if (place === 1) return brand.gold;
  if (place <= 3) return brand.fire;
  return brand.bone;
}

/**
 * Monthly ranking for social media (1080×1350): every ranked player in two columns, with
 * the change of place against the previous month, the requirements to enter and the
 * month's highlights (Mission 23).
 */
export async function monthlyRankingImage(data: MonthlyData) {
  const rows = data.rows.slice(0, PER_COLUMN * 2);
  const perColumn = Math.max(Math.ceil(rows.length / 2), 1);
  const height = Math.min(44, Math.floor(1000 / perColumn));
  const font = Math.round(height * 0.62);
  const [fontData, logo, icons] = await Promise.all([
    brand.font(),
    brand.logo(),
    Promise.all(rows.map((r) => stockIcon(r.main))),
  ]);
  const columns = [rows.slice(0, perColumn), rows.slice(perColumn)];
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
          <div style={{ display: "flex", fontSize: 54, lineHeight: 1 }}>
            {data.title}
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 28,
              color: brand.gold,
              marginTop: 6,
            }}
          >
            {data.label}
          </div>
        </div>
      </div>
      <div
        style={{
          display: "flex",
          fontSize: 19,
          color: brand.ash,
          marginTop: 12,
        }}
      >
        {data.requirements}
      </div>
      <div style={{ display: "flex", gap: 24, marginTop: 16, flexGrow: 1 }}>
        {columns.map((column, c) => (
          <div
            key={c}
            style={{ display: "flex", flexDirection: "column", width: 488 }}
          >
            {column.map((r, i) => {
              const icon = icons[c * perColumn + i];
              return (
                <div
                  key={`${r.place}-${r.tag}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    height,
                    paddingRight: 10,
                    borderLeft: `6px solid ${(r.main && characterColor(r.main)) || "#5a514a"}`,
                    background: i % 2 ? "transparent" : brand.slab,
                    fontSize: font,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "flex-end",
                      width: 44,
                      color: placeColor(r.place),
                    }}
                  >
                    {r.place}
                  </div>
                  <Change row={r} />
                  <div
                    style={{
                      display: "flex",
                      width: height,
                      justifyContent: "center",
                    }}
                  >
                    {icon && (
                      <img
                        src={icon}
                        width={height - 8}
                        height={height - 8}
                        alt=""
                      />
                    )}
                  </div>
                  <div
                    style={{
                      display: "flex",
                      flexGrow: 1,
                      alignItems: "center",
                      gap: 6,
                      marginLeft: 6,
                      overflow: "hidden",
                    }}
                  >
                    {r.prefix && (
                      <span
                        style={{
                          color: brand.ash,
                          fontSize: Math.round(font * 0.75),
                        }}
                      >
                        {`${r.prefix} |`}
                      </span>
                    )}
                    <span>{r.tag}</span>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      color: brand.ash,
                      fontSize: Math.round(font * 0.8),
                    }}
                  >
                    {`${r.wins}–${r.losses}`}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div
        style={{
          display: "flex",
          fontSize: 21,
          color: brand.bone,
          marginTop: 14,
        }}
      >
        {data.highlights}
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: 8,
          fontSize: 20,
          color: brand.ash,
        }}
      >
        <span>Smash Club Paraguay</span>
        <span>+ subió · − bajó · = igual que el mes anterior</span>
      </div>
    </div>,
    {
      width: 1080,
      height: 1350,
      fonts: fontData
        ? [{ name: "Display", data: fontData, weight: 800, style: "normal" }]
        : undefined,
      headers: { "Cache-Control": "public, max-age=600" },
    },
  );
}

/** The API's monthly ranking (GET /seeding/{slug}/monthly). */
export type Monthly = {
  name: string;
  label: string;
  window_start: string;
  window_end: string;
  method_label: string;
  min_sets: number;
  events: number;
  compared: boolean;
  left: number;
  rows: {
    place: number;
    change: number | null;
    new: boolean;
    gamer_tag: string;
    prefix?: string | null;
    mains?: { character: string }[];
    wins: number;
    losses: number;
  }[];
};

/** What changed in the month, for the line under the table. */
export function highlights(d: Monthly, rows: MonthlyRow[]) {
  if (!d.compared) return "Primer mes del ranking";
  const up = rows
    .filter((r) => (r.change ?? 0) > 0)
    .sort((a, b) => (b.change ?? 0) - (a.change ?? 0))[0];
  const fresh = rows.filter((r) => r.new).map((r) => r.tag);
  return [
    up ? `Mayor subida: ${up.tag} (+${up.change})` : "Sin cambios de puesto",
    fresh.length
      ? `${fresh.length === 1 ? "Entra" : "Entran"}: ${fresh.slice(0, 4).join(", ")}${
          fresh.length > 4 ? ` y ${fresh.length - 4} más` : ""
        }`
      : null,
    d.left === 1
      ? "Sale 1 jugador"
      : d.left
        ? `Salen ${d.left} jugadores`
        : null,
  ]
    .filter(Boolean)
    .join(" · ");
}
