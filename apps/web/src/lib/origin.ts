/**
 * Public origin of a request. Behind a proxy (DigitalOcean) request.url carries the
 * server's own bind address (http://0.0.0.0:3000), so the forwarded host is used.
 */
export function originFromHeaders(headers: Headers, fallback: string) {
  const host = headers.get("x-forwarded-host") ?? headers.get("host");
  if (!host) return fallback;
  const proto =
    headers.get("x-forwarded-proto")?.split(",")[0].trim() ||
    new URL(fallback).protocol.replace(":", "");
  return `${proto}://${host.split(",")[0].trim()}`;
}

export function publicOrigin(request: Request) {
  return originFromHeaders(request.headers, new URL(request.url).origin);
}

export function apiFor(origin: string) {
  // Inside Docker the web server reaches the API by service name; in production the
  // API lives under the same public domain.
  return (process.env.API_INTERNAL_URL || `${origin}/api/v1`).replace(
    /\/$/,
    "",
  );
}

export function apiBase(request: Request) {
  return apiFor(publicOrigin(request));
}
