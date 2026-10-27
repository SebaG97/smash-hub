import sharp from "sharp";

/**
 * Official fighter renders from smashbros.com (8 costumes each), trimmed and resized
 * on the server and kept in memory. Used by share images and the costume picker.
 */
export const RENDER_WIDTHS = [160, 320, 640] as const;
export type RenderWidth = (typeof RENDER_WIDTHS)[number];
export type Render = { data: Buffer; width: number; height: number };

// Our icon file names (start.gg names) where the official site uses internal names.
const SITE_NAMES: Record<string, string> = {
  bowser: "koopa",
  bowser_jr: "koopa_jr",
  corrin: "kamui",
  dark_pit: "black_pit",
  greninja: "gekkouga",
  ice_climbers: "ice_climber",
  isabelle: "shizue",
  jigglypuff: "purin",
  king_dedede: "dedede",
  mega_man: "rockman",
  olimar: "pikmin_and_olimar",
  rob: "robot",
  robin: "reflet",
  rosalina_and_luma: "rosetta_and_chiko",
  villager: "murabito",
};
const MAX_ENTRIES = 300;
const cache = new Map<string, Promise<Render | null>>();

export function officialRenderUrl(key: string, costume: number) {
  const name = SITE_NAMES[key] ?? key;
  return `https://www.smashbros.com/assets_v2/img/fighter/${name}/main${costume > 1 ? costume : ""}.png`;
}

async function load(key: string, costume: number, width: RenderWidth) {
  const get = (n: number) =>
    fetch(officialRenderUrl(key, n), { signal: AbortSignal.timeout(15000) });
  let response = await get(costume);
  // Some fighters (the Miis) only have the default costume on the site.
  if (!response.ok && costume > 1) response = await get(1);
  if (!response.ok) return null;
  const { data, info } = await sharp(Buffer.from(await response.arrayBuffer()))
    .trim()
    .resize({ width, height: width, fit: "inside", withoutEnlargement: true })
    .png({ compressionLevel: 9 })
    .toBuffer({ resolveWithObject: true });
  return { data, width: info.width, height: info.height };
}

export function render(
  key: string,
  costume: number,
  width: RenderWidth,
): Promise<Render | null> {
  const id = `${key}/${costume}/${width}`;
  let entry = cache.get(id);
  if (!entry) {
    entry = load(key, costume, width).catch(() => null);
    // Failures are not kept, so the next request tries again.
    entry.then((r) => r ?? cache.delete(id));
    if (cache.size >= MAX_ENTRIES) cache.delete(cache.keys().next().value!);
    cache.set(id, entry);
  }
  return entry;
}
