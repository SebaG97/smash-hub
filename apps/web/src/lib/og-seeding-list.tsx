import { ImageResponse } from "next/og";
import { characterColor } from "./characters";
import { brand, stockIcon } from "./og";

/**
 * Seeding as a list for social media (Mission 31): the top seeds (1080×1350) or every
 * pool side by side (1920×1080), each row with the seed, the flag of the circuit where the
 * player competes most, the main's stock icon, the approved prefix and the tag.
 */

export type ListRow = {
  seed: number;
  /** Place inside a pool, shown small next to the seed. */
  pool_seed?: number | null;
  tag: string;
  prefix?: string | null;
  main?: string | null;
  /** Country code of the circuit ("PY", "AR"…), "ONLINE" or null. */
  circuit?: string | null;
};

const flags = new Map<string, Promise<string | null>>();

/** Flag of a circuit as a data URI (flagcdn.com), kept in memory; null if unknown. */
export function flag(code?: string | null) {
  const key = (code || "").toLowerCase();
  if (!/^[a-z]{2}$/.test(key)) return Promise.resolve(null);
  if (!flags.has(key))
    flags.set(
      key,
      fetch(`https://flagcdn.com/w80/${key}.png`)
        .then(async (r) =>
          r.ok
            ? `data:image/png;base64,${Buffer.from(await r.arrayBuffer()).toString("base64")}`
            : null,
        )
        .catch(() => {
          flags.delete(key);
          return null;
        }),
    );
  return flags.get(key)!;
}

function seedColor(seed: number) {
  if (seed === 1) return brand.gold;
  if (seed <= 4) return brand.fire;
  return brand.bone;
}

type Art = { flag: string | null; icon: string | null };

function Row({
  row,
  art,
  height,
  wide,
}: {
  row: ListRow;
  art: Art;
  height: number;
  wide: boolean;
}) {
  const font = Math.round(height * (wide ? 0.6 : 0.54));
  const flagHeight = Math.round(height * 0.46);
  const icon = Math.round(height * 0.68);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        height,
        gap: Math.round(height * 0.22),
        paddingRight: 12,
        background: brand.slab,
        borderLeft: `${Math.max(4, Math.round(height / 8))}px solid ${
          (row.main && characterColor(row.main)) || "#5a514a"
        }`,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "center",
          width: Math.round(height * 0.95),
          fontSize: Math.round(font * 1.05),
          color: seedColor(row.seed),
        }}
      >
        {row.seed}
      </div>
      {art.flag ? (
        <img
          src={art.flag}
          width={Math.round(flagHeight * 1.5)}
          height={flagHeight}
          style={{ borderRadius: 3 }}
          alt=""
        />
      ) : (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: Math.round(flagHeight * 1.5),
            height: flagHeight,
            borderRadius: 3,
            background: "#4a433d",
            color: brand.ash,
            fontSize: Math.round(flagHeight * 0.42),
          }}
        >
          {row.circuit === "ONLINE" ? "ONLINE" : ""}
        </div>
      )}
      {art.icon ? (
        <img src={art.icon} width={icon} height={icon} alt="" />
      ) : (
        <div style={{ display: "flex", width: icon }} />
      )}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 8,
          fontSize: font,
          whiteSpace: "nowrap",
        }}
      >
        {row.prefix && (
          <div
            style={{
              display: "flex",
              fontSize: Math.round(font * 0.62),
              color: brand.ash,
            }}
          >
            {row.prefix} |
          </div>
        )}
        {row.tag}
      </div>
    </div>
  );
}

async function arts(rows: ListRow[]): Promise<Art[]> {
  return Promise.all(
    rows.map(async (r) => ({
      flag: await flag(r.circuit),
      icon: await stockIcon(r.main),
    })),
  );
}

function Header({
  logo,
  title,
  subtitle,
  size,
}: {
  logo: string | null;
  title: string;
  subtitle: string;
  size: number;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
      {logo && (
        <img
          src={logo}
          width={size}
          height={size}
          style={{ borderRadius: size / 2 }}
          alt=""
        />
      )}
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", fontSize: size * 0.66, lineHeight: 1 }}>
          {title}
        </div>
        <div
          style={{
            display: "flex",
            fontSize: size * 0.32,
            color: brand.gold,
            marginTop: 4,
          }}
        >
          {subtitle}
        </div>
      </div>
    </div>
  );
}

function Footer() {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        marginTop: "auto",
        fontSize: 20,
        color: brand.ash,
      }}
    >
      <div style={{ display: "flex" }}>Smash Club Paraguay</div>
      <div style={{ display: "flex" }}>
        Bandera: país del jugador o circuito donde más compite
      </div>
    </div>
  );
}

function options(font: ArrayBuffer | null, width: number, height: number) {
  return {
    width,
    height,
    fonts: font
      ? [
          {
            name: "Display",
            data: font,
            weight: 800 as const,
            style: "normal" as const,
          },
        ]
      : undefined,
  };
}

/** Top seeds in two columns (1080×1350). */
export async function seedListImage(data: {
  title: string;
  subtitle: string;
  rows: ListRow[];
}) {
  const rows = data.rows.slice(0, 64);
  const perColumn = Math.max(Math.ceil(rows.length / 2), 1);
  const gap = 6;
  // Rows grow when there are few, so a top 16 fills the image too.
  const height = Math.min(
    100,
    Math.floor((1350 - 72 - 92 - 26 - 50 - gap * perColumn) / perColumn),
  );
  const [font, logo, art] = await Promise.all([
    brand.font(),
    brand.logo(),
    arts(rows),
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
        fontFamily: font ? "Display" : undefined,
      }}
    >
      <Header
        logo={logo}
        title={data.title}
        subtitle={data.subtitle}
        size={92}
      />
      <div style={{ display: "flex", gap: 24, marginTop: 26 }}>
        {columns.map((column, c) => (
          <div
            key={c}
            style={{
              display: "flex",
              flexDirection: "column",
              gap,
              flex: 1,
              minWidth: 0,
            }}
          >
            {column.map((row, i) => (
              <Row
                key={row.seed}
                row={row}
                art={art[c * perColumn + i]}
                height={height}
                wide={false}
              />
            ))}
          </div>
        ))}
      </div>
      <Footer />
    </div>,
    options(font, 1080, 1350),
  );
}

/** Every pool side by side (1920×1080), each one in seed order. */
export async function poolsImage(data: {
  title: string;
  subtitle: string;
  pools: { name: string; rows: ListRow[] }[];
}) {
  const pools = data.pools.slice(0, 8);
  const longest = Math.max(1, ...pools.map((p) => p.rows.length));
  const gap = 4;
  const height = Math.min(
    52,
    Math.floor((1080 - 60 - 80 - 70 - 40 - gap * longest) / longest),
  );
  const [font, logo, art] = await Promise.all([
    brand.font(),
    brand.logo(),
    Promise.all(pools.map((p) => arts(p.rows))),
  ]);
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: brand.concrete,
        color: brand.bone,
        padding: "30px 36px",
        fontFamily: font ? "Display" : undefined,
      }}
    >
      <Header
        logo={logo}
        title={data.title}
        subtitle={data.subtitle}
        size={80}
      />
      <div style={{ display: "flex", gap: 18, marginTop: 18 }}>
        {pools.map((pool, p) => (
          <div
            key={pool.name}
            style={{
              display: "flex",
              flexDirection: "column",
              gap,
              flex: 1,
              minWidth: 0,
            }}
          >
            <div
              style={{
                display: "flex",
                fontSize: 34,
                color: brand.gold,
                marginBottom: 4,
              }}
            >
              {pool.name}
            </div>
            {pool.rows.map((row, i) => (
              <Row
                key={row.seed}
                row={row}
                art={art[p][i]}
                height={height}
                wide
              />
            ))}
          </div>
        ))}
      </div>
      <Footer />
    </div>,
    options(font, 1920, 1080),
  );
}
