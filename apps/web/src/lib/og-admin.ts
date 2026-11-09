import { apiBase } from "./og";

/** GET an admin API path with the organizer's own key, for images of drafts. */
export async function adminJson<T>(request: Request, path: string) {
  const authorization = request.headers.get("authorization");
  if (!authorization)
    return new Response("Necesitás la clave de organizador.", { status: 401 });
  const r = await fetch(`${apiBase(request)}/${path}`, {
    headers: {
      Authorization: authorization,
      "X-Admin-Name": request.headers.get("x-admin-name") ?? "",
    },
  }).catch(() => null);
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
