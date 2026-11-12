# Operación de la sincronización con start.gg

Arquitectura: [sincronizacion.md](../architecture/sincronizacion.md). Decisión: [ADR-022](../adr/ADR-022.md).

## Configuración

Todas las variables son del servicio `api`, `RUN_TIME`. Solo `STARTGG_API_TOKEN` es secreta (ya existe).

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `STARTGG_SYNC_ENABLED` | `false` | Enciende el hilo de sincronización. Sin token se ignora (queda un aviso en el log). |
| `STARTGG_SYNC_TICK_SECONDS` | `60` | Cada cuánto se revisa qué toca (15 a 900). |
| `STARTGG_SYNC_REQUEST_INTERVAL` | `1.2` | Segundos entre solicitudes de una sincronización (0,8 a 10). 1,2 s ≈ 50 por minuto de las 80 que permite el token. |
| `STARTGG_SYNC_COUNTRY` | `PY` | País cuyos próximos torneos se siguen solos (calendario). |
| `STARTGG_SYNC_DISCOVERY_SECONDS` | `3600` | Cada cuánto se busca el calendario del país. |
| `STARTGG_SYNC_FAR_SECONDS` | `21600` | Torneos a más de 7 días. |
| `STARTGG_SYNC_WEEK_SECONDS` | `1800` | Entre 7 días y 24 h antes. |
| `STARTGG_SYNC_DAY_SECONDS` | `600` | Últimas 24 h antes (hasta 2 h antes del inicio). |
| `STARTGG_SYNC_LIVE_SECONDS` | `180` | En curso: desde 2 h antes del inicio, o con start.gg en estado activo, hasta 6 h después del fin. |
| `STARTGG_SYNC_FINISHED_SECONDS` | `86400` | Terminados, durante 3 días; después se dejan de sincronizar. |

Valores fuera de rango hacen fallar el arranque de la API (validación de configuración), igual que el resto de la configuración.

## DigitalOcean App Platform

No hace falta ningún componente nuevo (ni worker, ni job, ni base): la sincronización corre dentro del servicio `api` existente. Pasos, después de aprobar el despliegue:

1. Backup de la base y aplicar las migraciones nuevas con el job de migración: `APPROVED_MIGRATION=0022` (aplica `0020`, `0021` y `0022`, todas aditivas). Ver [migrations.md](migrations.md).
2. Desplegar la versión nueva del servicio `api` y de `web`. Con `STARTGG_SYNC_ENABLED` sin definir, todo sigue funcionando como antes.
3. En el servicio `api`, cambiar `STARTGG_SYNC_ENABLED` a `true` (el spec `infra/digitalocean/app.yaml` la declara en `"false"`). Las demás variables solo si se quieren cambiar los valores por defecto. Cambiar una variable redespliega el servicio.
4. Verificar en `/admin` → **Sincronización con start.gg** que aparezca un descubrimiento completado y, al minuto siguiente, los torneos del calendario sincronizándose.

Consideraciones:

- **Conexiones**: el hilo usa el mismo pool de la API (`DB_POOL_SIZE=3`, `DB_MAX_OVERFLOW=2`), una conexión a la vez y por poco tiempo. No cambia el presupuesto de conexiones.
- **Memoria y CPU**: una sincronización mantiene en memoria solo las respuestas de un evento (cientos de filas). Entra en `apps-s-1vcpu-0.5gb`.
- **Varias instancias**: si se sube `instance_count`, cada instancia tiene su hilo, pero el advisory lock deja trabajar a una sola por vez. Igual conviene encenderlo en una sola.
- **Token**: el mismo `STARTGG_API_TOKEN` lo usan las descargas de seeding, la subida de seeds y lo que todavía se lee en vivo. Mientras una descarga de seeding está en curso, la sincronización espera.
- **Despliegues y reinicios**: los datos sincronizados están en PostgreSQL y no se pierden. Si un proceso muere a mitad de una ejecución, esa ejecución queda `running` y deja de bloquear a los 20 minutos (se cierra como `abandoned`).
- **Apagarla**: `STARTGG_SYNC_ENABLED=false`. Las páginas siguen leyendo lo último sincronizado de cada torneo. Para volver a leer todo en vivo habría que dejar de seguir los torneos y esperar a que pierdan vigencia; no hace falta borrar nada.

## Sincronización manual

Desde `/admin` (cuenta de administrador) o la API:

```http
POST /api/v1/sync/tournaments      {"tournament": "https://www.start.gg/tournament/<slug>"}
POST /api/v1/sync/discover
PUT  /api/v1/sync/tournaments/<slug>/tracking   {"tracked": false}
GET  /api/v1/sync
```

Una sincronización manual empieza a seguir el torneo (`tracked = true`). Responde 409 si ya hay otra en curso, una descarga de seeding o una importación. Funciona aunque `STARTGG_SYNC_ENABLED` esté apagada.

## Errores frecuentes

| Código | Qué significa |
| --- | --- |
| `startgg_tournament_not_found` | start.gg no encuentra el slug (borrado, privado o mal escrito). Los torneos de seedings se reintentan cada hora. |
| `startgg_incomplete_pagination` | Una lista cambió o llegó incompleta mientras se paginaba. No se retira nada; se reintenta. |
| `startgg_rate_limited`, `startgg_http_error`, `startgg_transport_error` | start.gg no respondió bien tras cuatro intentos. Backoff de 5 min en adelante. |
| `startgg_graphql_error` | start.gg devolvió errores GraphQL (posible cambio de esquema). Revisar el documento `sync_*` afectado. |
| `abandoned` | El proceso murió con la ejecución en curso (despliegue o reinicio). |

Advertencias (`warnings` de cada ejecución): `empty_entrants_kept:<evento>` (start.gg devolvió cero inscripciones donde había, y no se retiró a nadie).
