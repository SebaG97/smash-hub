/* global process */
// Builds the installable-app icons (SH-PWA-01) from the official club logo.
// Run from apps/web: `node scripts/generate-pwa-icons.mjs`. The output is committed.
import sharp from "sharp";

const source = "public/smashclublogo.jpg";
const out = "public/icons";

async function square(size, file) {
  await sharp(source)
    .resize(size, size, { fit: "cover" })
    .png({ compressionLevel: 9 })
    .toFile(`${out}/${file}`);
}

// Maskable: launchers crop to a circle of 80 % of the side (radius 40 %). The emblem's
// ring has a radius of about 42 % of the logo, so the logo is shrunk to 90 % and the
// margin is filled by mirroring its own concrete texture: no visible seam or new art.
async function maskable(size, file) {
  const inner = Math.round(size * 0.9);
  const before = Math.floor((size - inner) / 2);
  const after = size - inner - before;
  await sharp(source)
    .resize(inner, inner)
    .extend({
      top: before,
      bottom: after,
      left: before,
      right: after,
      extendWith: "mirror",
    })
    .png({ compressionLevel: 9 })
    .toFile(`${out}/${file}`);
}

await square(192, "icon-192.png");
await square(512, "icon-512.png");
await maskable(512, "icon-maskable-512.png");
await square(180, "apple-touch-icon.png");
process.stdout.write(`PWA icons written to ${out}\n`);
