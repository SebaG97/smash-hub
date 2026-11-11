import { apiBase } from "./og";

/**
 * The organizer's own credentials, passed on to the API: the session cookie (ADR-021)
 * or, during the transition, the legacy shared key. The API decides; this only relays.
 */
export function organizerHeaders(
  request: Request,
): Record<string, string> | null {
  const cookie = request.headers.get("cookie");
  const authorization = request.headers.get("authorization");
  if (!cookie && !authorization) return null;
  return {
    ...(cookie ? { Cookie: cookie } : {}),
    ...(authorization
      ? {
          Authorization: authorization,
          "X-Admin-Name": request.headers.get("x-admin-name") ?? "",
        }
      : {}),
  };
}

/** GET an admin API path as the organizer, for images of drafts. */
export async function adminJson<T>(request: Request, path: string) {
  const headers = organizerHeaders(request);
  if (!headers)
    return new Response("Ingresá con una cuenta de organizador.", {
      status: 401,
    });
  const r = await fetch(`${apiBase(request)}/${path}`, { headers }).catch(
    () => null,
  );
  if (!r)
    return new Response("No se pudo contactar a la API.", { status: 502 });
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    return new Response(
      typeof body?.detail === "string" ? body.detail : "No se pudo leer.",
      { status: r.status },
    );
  }
  return (await r.json()) as T;
}
