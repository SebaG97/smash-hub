import { describe, expect, it } from "vitest";
import { crc32, zip, zipBytes } from "../src/lib/zip";

describe("zip", () => {
  it("computes the standard CRC-32", () => {
    expect(crc32(new TextEncoder().encode("abc"))).toBe(0x352441c2);
  });

  it("stores every file with its name and an end record", () => {
    const data = new TextEncoder().encode("hola");
    const files = [
      { name: "01-podio.png", data },
      { name: "02-final.png", data },
    ];
    const bytes = zipBytes(files);
    const view = new DataView(bytes.buffer);
    expect(view.getUint32(0, true)).toBe(0x04034b50);
    const end = bytes.length - 22;
    expect(view.getUint32(end, true)).toBe(0x06054b50);
    expect(view.getUint16(end + 10, true)).toBe(2);
    const text = new TextDecoder().decode(bytes);
    expect(text).toContain("01-podio.png");
    expect(text).toContain("02-final.png");
    expect(bytes.length).toBe(2 * (30 + 12 + 4) + 2 * (46 + 12) + 22);
    expect(zip(files).type).toBe("application/zip");
  });
});
