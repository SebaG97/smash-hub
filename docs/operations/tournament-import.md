# Operación de importaciones

Ejecutar desde un entorno local con revisión Alembic 0002 y bootstrap aplicados. No usar PostgreSQL Managed ni credenciales de producción. La CLI rechaza ENVIRONMENT=production en esta misión.

```sh
docker compose run --rm api alembic upgrade 0002
docker compose run --rm api python -m app.bootstrap
# Configurar STARTGG_API_TOKEN en el entorno privado de API; nunca en argumentos.
docker compose run --rm api python -m app.cli.import_tournament --slug nombre-del-torneo --dry-run
docker compose run --rm api python -m app.cli.import_tournament --slug https://www.start.gg/tournament/nombre-del-torneo
```

Equivalente nativo desde apps/api: `python -m app.cli.import_tournament --slug nombre-del-torneo`. La CLI acepta `--community` (por defecto smash-paraguay) para asignación organizativa explícita; la ubicación del torneo nunca se usa para decidir su comunidad. Acepta slug simple, tournament/slug o URL HTTPS start.gg/www.start.gg sin credenciales y con puerto 443 opcional. Query y fragmento se ignoran. Otros dominios, rutas de eventos, esquemas y URLs arbitrarias se rechazan; no se hace HTTP al enlace recibido.

`--dry-run` descarga y valida estructura, paginación, referencias y rosters sin abrir PostgreSQL ni crear jobs. Informa cantidades, no es un plan exacto de escrituras ni detecta conflictos con datos locales. Salida JSON: completed/validated y resumen; código 0 para éxito, 1 para fallo operativo/proveedor, 2 para configuración inválida o argumentos inválidos. Conflictos no fatales se reportan con códigos y IDs externos administrativos, jamás en API pública.

## Confirmaciones y repetición

1. Adquirir bloqueo de sesión por slug y bloqueo del proveedor. Si hay otra ejecución activa, salir sin publicar. El bloqueo del proveedor evita carreras de identidades y sumar tasas de varias importaciones persistentes.
2. Confirmar job running con clave slug:UUID; cada ejecución conserva una fila independiente. Bootstrap y comunidad deben existir previamente.
3. Descargar y validar todas las páginas antes de comenzar escrituras competitivas.
4. En una única transacción, reconciliar identidades, upsert por mappings, actualizar rosters/resultados, marcar published y confirmar job completed. Constraints diferidos verifican estado final al commit. El público continúa viendo la versión anterior hasta ese commit.
5. Ante fallo, rollback total competitivo y confirmar job failed por separado, con conteos confirmados en cero y código fijo. Liberar locks al cerrar. Volver a ejecutar el mismo comando es seguro; no se elimina historial ausente ni se publica una importación parcial.

Los conteos created/updated/skipped cubren entidades mapeadas, jugadores, participantes y aliases; no representan cada INSERT auxiliar de rosters/sides ni actualizaciones de timestamps. Reimportar el mismo snapshot da created=updated=0, conserva UUID, scores e identidades; actualiza tiempos de sincronización y agrega solo el nuevo intento administrativo.

Si el proceso muere abruptamente, PostgreSQL revierte su transacción y libera los locks al cerrarse la conexión, pero el job puede quedar running. Una repetición crea un nuevo intento; revisar el antiguo administrativamente como interrumpido cuando no exista proceso dueño. No hay reanudación de páginas: se repite toda la descarga.

## Correcciones y conflictos

`sets.source_result` conserva la selección original del proveedor; `result_history` conserva previous/replacement y fecha de observación en cambios aceptados. Se rechazan revisiones anteriores a source_updated_at. En ausencia de timestamp de revisión, la última lectura validada tiene prioridad. Un cambio idéntico no añade historia.

Antes de una corrección manual, activar `sets.manual_locked` o `external_mappings.manual_locked` en la misma transacción administrativa que la corrección. El segundo protege metadatos de torneo/evento, entrants, roster o sets según mapping. No existe UI/HTTP de correcciones en esta misión. Los candidatos bloqueados no sobrescriben datos: quedan como conflictos en el job, con proposed_result para sets. Player.manual_locked conserva el tag elegido manualmente. No modificar identidades externas automáticamente ante contradicciones.

El tag histórico de un participante se conserva desde la primera importación: una diferencia posterior genera historical_tag_preserved y agrega evidencia de alias, sin reescribir historia. Player.tag cambia solo ante evidencia de un torneo cronológicamente posterior, salvo bloqueo manual. Aliases representan tags observados; no se inventa una línea temporal exclusiva ni se cierran intervalos por importar torneos fuera de orden.

Revisar conflictos con acceso SQL administrativo de solo lectura a import_jobs; no imprimir payloads en logs compartidos. identity_conflict requiere revisión de la persona responsable y una transacción explícita antes de repetir. No resolver fusionando por tag. Hacer backup antes de cualquier corrección operativa futura.

## Diagnóstico

- startgg_token_missing: configurar secreto servidor; sitio público sigue disponible.
- startgg_incomplete_pagination / incomplete_entrant_list: repetir cuando el proveedor esté estable.
- startgg_graphql_error: comprobar documentos contra esquema oficial; no aceptar data parcial.
- unknown_team_size / unsupported_variable_roster: revisar modalidad; requiere ampliación explícita del modelo.
- tournament_import_already_running / startgg_import_busy: esperar que termine la ejecución local.
- import_validation_or_storage_error: revisar integridad y versión de migración sin volcar secretos.

La integración real de singles se ejecutó con los tres torneos autorizados, incluyendo comparación de fuente e idempotencia; ver informe y matriz de evidencia. Los fixtures no se cargan en desarrollo o producción. No se despliega, no se inicia Misión 03 y no se calculan rankings.

## Torneos reales autorizados

El responsable confirmó singles en `gg-fest-x-eon`, `game-over-sep` y `super-smash-burgame-7`. La validación real debe cubrir los tres, su identidad compartida y reimportación, comparando entrants/placements/sets con el proveedor. El token se configuró privadamente y se completaron importación, comparación y reimportación de los tres torneos; ver informe para conteos y limitaciones. Dobles se valida con fixtures, sin bloquear aprobación por falta de torneos reales de esa modalidad. Ver [plan actualizado](mission-02-validation-plan.md).

## Misión 02.1 — Revalidación de sets

Después de migrar a 0003, repetir las importaciones para enriquecer slots/dependencias y versionar clasificación. La primera repetición puede actualizar clasificación y descubrir resets omitidos, sin modificar resultados. Repetir nuevamente para comprobar idempotencia con la versión nueva. No esperar created=0 en la primera lectura si aparecen IDs externos antes omitidos: verificar que sean nuevos y únicos; en la segunda lectura estable debe dar created=updated=0.

La huella incluye clasificación y versión, no solo payload del proveedor. El historial diferencia evidencia anterior/nueva con sus clasificaciones; una reclasificación no implica que start.gg haya corregido el score. Los mismos lados conservan sus UUID si no cambiaron valores. Para auditoría pública usar sets?view=all; el listado predeterminado separa placeholders y resets no disputados. Ver informe Misión 02.1 para matrices reales y límites.
