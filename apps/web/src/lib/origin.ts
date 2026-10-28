/**
 * Public origin of the request. Behind a proxy (DigitalOcean) request.url carries the
 * server's own bind address (http://0.0.0.0:3000), so the forwarded host is used.
 */
export function publicOrigin(request: Request) {
  const host =
    request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  if (!host) return new URL(request.url).origin;
  const proto =
    request.headers.get("x-forwarded-proto")?.split(",")[0].trim() ||
    new URL(request.url).protocol.replace(":", "");
  return `${proto}://${host.split(",")[0].trim()}`;
}

export function apiBase(request: Request) {
  // Inside Docker the web server reaches the API by service name; in production the
  // API lives under the same public domain.
  return (
    process.env.API_INTERNAL_URL || `${publicOrigin(request)}/api/v1`
  ).replace(/\/$/, "");
}
