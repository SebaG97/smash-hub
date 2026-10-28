import { afterEach, expect, it, vi } from "vitest";
import { apiBase, publicOrigin } from "../src/lib/origin";

afterEach(() => vi.unstubAllEnvs());

it("uses the forwarded public host behind a proxy", () => {
  const request = new Request("http://0.0.0.0:3000/og/tournament/t1", {
    headers: {
      "x-forwarded-host": "smash.example.org",
      "x-forwarded-proto": "https, http",
    },
  });
  vi.stubEnv("API_INTERNAL_URL", "");
  expect(publicOrigin(request)).toBe("https://smash.example.org");
  expect(apiBase(request)).toBe("https://smash.example.org/api/v1");
});

it("falls back to the Host header and then to the request URL", () => {
  vi.stubEnv("API_INTERNAL_URL", "");
  const withHost = new Request("http://0.0.0.0:3000/x", {
    headers: { host: "localhost:3000" },
  });
  expect(publicOrigin(withHost)).toBe("http://localhost:3000");
  expect(publicOrigin(new Request("http://localhost:3000/x"))).toBe(
    "http://localhost:3000",
  );
});

it("prefers the internal API URL when it is configured", () => {
  vi.stubEnv("API_INTERNAL_URL", "http://api:8000/api/v1/");
  expect(apiBase(new Request("http://0.0.0.0:3000/x"))).toBe(
    "http://api:8000/api/v1",
  );
});
