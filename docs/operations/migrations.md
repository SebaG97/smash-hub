# Migraciones y rollback

Revisión inicial: `0001`, 19 tablas del dominio, índices, claves foráneas, checks y cinco constraint triggers diferidos de coherencia competitiva. El esquema Alembic añade su propia tabla `alembic_version`. La revisión está congelada; no usa `Base.metadata.create_all`.

Comandos locales:

```sh
docker compose run --rm api alembic current
docker compose run --rm api alembic upgrade head
docker compose run --rm api alembic check
```

Toda ejecución requiere `MIGRATION_DATABASE_URL` explícita. `DATABASE_URL` es para la aplicación. Se usa un bloqueo asesor transaccional para evitar dos migradores concurrentes. Alembic ejecuta DDL transaccional en PostgreSQL; una migración fallida debe revertir completa.

Para una nueva revisión: editar modelos, generar con `alembic revision --autogenerate -m "..."` en una base local al día y revisar manualmente el SQL. Alembic no detecta automáticamente las funciones ni triggers: deben incluirse y probarse explícitamente. Ejecutar aplicación, reversión y reaplicación en PostgreSQL efímero. No reescribir revisiones publicadas. Adoptar expand/contract para cambios futuros con datos.

`alembic downgrade base` de la revisión inicial elimina las 19 tablas y todos sus datos. Solo se ejecuta automáticamente en pruebas aisladas. No es una estrategia automática de rollback de producción. Si hay datos, preservar backup y preferir una corrección hacia adelante; restaurar en una base alternativa y verificar antes de promoverla.

El job preparado para App Platform está inactivo en un fragmento separado. Solo migra hasta `0001` con `APPROVED_MIGRATION=0001`; no usa `head` ni hace downgrade. Antes de incorporarlo: revisar revisión instalada, SQL, backup, ventana de mantenimiento, permisos y compatibilidad con la versión anterior. Proporcionar secreto del rol migrador por un canal privado. Retirar el fragmento tras el despliegue si no debe ejecutarse en despliegues posteriores. Nunca automatizar migraciones destructivas.

La suite comprueba aplicación, comparación del esquema con modelos, downgrade a base y reaplicación, además de constraints de FK/unique/check y triggers al commit. La guardia de tests solo admite `smashhub_test` en localhost/127.0.0.1/postgres.

## Revisión 0002 — Importador

Migración incremental `0002_startgg.py`, sobre 0001 intacta. Agrega published/status/location/synced_at a tournaments; metadata estructurada a events; placement a event_entrants; external_id scoped único y bloqueo a tournament_participants; bloqueo de tag a players; counts/conflicts a import_jobs; manual_locked a mappings; evidencia original, historial y ranking_eligible a sets. Amplía estado de set con incomplete y permite fechas finales ausentes sin inventarlas. Una restricción exige completed con fecha para ranking_eligible=true. Las funciones diferidas existentes siguen validando los resultados completed/dq/bye.

En desarrollo: `alembic upgrade 0002`, `alembic check`, suite PostgreSQL y roundtrip. En rollback, 0002 rechaza datos incomplete o finales sin fecha porque 0001 no puede representarlos; preferir corrección hacia adelante y backup. No borrar ni convertir resultados para forzar downgrade en una base con historial real. La limpieza de fixtures antes de downgrade solo ocurre en smashhub_test bajo guardia de host/nombre.

El fragmento DigitalOcean permanece aprobado únicamente para 0001. No modificar su objetivo a 0002 ni ejecutarlo sin revisión humana y nueva validación doctl. Esta misión no aplica migraciones a producción.

## Revisión 0003 — Clasificación de sets

Agrega seis columnas: lifecycle_status, resolution, classification_reason, normalization_version, round_number y stats_eligible. Conserva status legado, IDs, scores, ganadores, source_result y funciones congeladas. Cuatro constraints controlan vocabularios y elegibilidad: estadísticas solo para completed/played con formato legado completed; ranking requiere también stats_eligible y las condiciones previas de fecha.

Antes de aplicar, guardar evidencia/backup local. Ejecutar `alembic upgrade 0003`, `alembic check` y reimportar los torneos existentes para enriquecer la evidencia de bracket. El backfill no habilita estadísticas/ranking sin revalidación. Se valida la cola de triggers con SET CONSTRAINTS ALL IMMEDIATE antes del DDL posterior al UPDATE y se devuelve a DEFERRED; no se deshabilitan triggers. Este paso es necesario con datos existentes y está cubierto por test de downgrade 0002/upgrade 0003 y reimportación conservando resultados/UUID de lados.

No se cambian 0001 ni 0002. Downgrade de 0003 elimina metadatos de clasificación, no resultados; conservar backup/historial y preferir una corrección hacia adelante. No se modifica el fragmento de migración DigitalOcean ni se ejecuta producción.
