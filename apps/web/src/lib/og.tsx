import { readFile } from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";
import { characterColor, characterIcon } from "./characters";

/**
 * Square (1080×1080) share images for Instagram and Discord, in the hub's style:
 * concrete background, slanted place numbers and each player's main color.
 */
export type OgRow = {
  place: number;
  tag: string;
  main?: string | null;
  detail?: string;
};

export function apiBase(request: Request) {
  // Inside Docker the web server reaches the API by service name; in production the
  // API lives under the same domain.
  return (
    process.env.API_INTERNAL_URL || `${new URL(request.url).origin}/api/v1`
  ).replace(/\/$/, "");
}

async function displayFont() {
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
    return null;
  }
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

function placeColor(place: number) {
  if (place === 1) return "#f3a81f";
  if (place <= 3) return "#e5541b";
  return "#efe9df";
}

export async function shareImage(
  request: Request,
  { title, subtitle, rows }: { title: string; subtitle: string; rows: OgRow[] },
) {
  const [font, logo, icons] = await Promise.all([
    displayFont(),
    inline("smashclublogo.jpg"),
    Promise.all(
      rows.map((r) => {
        const icon = r.main ? characterIcon(r.main) : null;
        return icon ? inline(icon.slice(1)) : null;
      }),
    ),
  ]);
  const big = rows.length <= 8;
  const iconSize = big ? 64 : 56;
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "#26221f",
        color: "#efe9df",
        padding: "56px 64px",
        fontFamily: font ? "Display" : undefined,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
        {logo && (
          <img
            src={logo}
            width={120}
            height={120}
            style={{ borderRadius: 60 }}
            alt=""
          />
        )}
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontSize: 64, lineHeight: 1 }}>
            {title}
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 30,
              color: "#a2988d",
              marginTop: 10,
            }}
          >
            {subtitle}
          </div>
        </div>
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          marginTop: 40,
          gap: big ? 10 : 8,
        }}
      >
        {rows.map((r, i) => {
          const icon = icons[i];
          const color = (r.main && characterColor(r.main)) || "#3d3631";
          return (
            <div
              key={`${r.place}-${r.tag}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 24,
                padding: big ? "6px 20px" : "6px 18px",
                borderLeft: `10px solid ${color}`,
                background:
                  r.place === 1 ? `${color}33` : "rgba(48,43,39,0.85)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  width: 90,
                  fontSize: big ? 64 : 56,
                  lineHeight: 1,
                  transform: "skewX(-10deg)",
                  color: placeColor(r.place),
                }}
              >
                {r.place}
              </div>
              {icon ? (
                <img src={icon} width={iconSize} height={iconSize} alt="" />
              ) : (
                <div style={{ width: iconSize }} />
              )}
              <div
                style={{
                  display: "flex",
                  fontSize: big ? 50 : 42,
                  flexGrow: 1,
                }}
              >
                {r.tag}
              </div>
              {r.detail && (
                <div
                  style={{ display: "flex", fontSize: 28, color: "#a2988d" }}
                >
                  {r.detail}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div
        style={{
          display: "flex",
          marginTop: "auto",
          fontSize: 28,
          color: "#a2988d",
        }}
      >
        Smash Club Paraguay
      </div>
    </div>,
    {
      width: 1080,
      height: 1080,
      fonts: font
        ? [{ name: "Display", data: font, weight: 800, style: "normal" }]
        : undefined,
      headers: { "Cache-Control": "public, max-age=600" },
    },
  );
}
