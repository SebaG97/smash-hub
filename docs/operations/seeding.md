# Seeding de eventos (Misión 05)

La página `/seeding/<slug>` muestra la propuesta de seeds de un evento de start.gg, con el porqué de cada puesto, los datos analizados y el período. Con la clave de administración se puede mover jugadores, recalcular, bajar datos nuevos de start.gg y exportar. La subida a start.gg se hace con un comando.

## Configuración

En `.env` (nunca en `NEXT_PUBLIC_*`):

- `ADMIN_TOKEN`: clave compartida de los organizadores, al menos 24 caracteres. Sin ella la página es de solo lectura. Generar una con `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- `STARTGG_API_TOKEN`: necesario para crear proyectos, bajar datos nuevos y subir seeds. Para subir, el token debe ser de una cuenta administradora del torneo.

Después de cambiar `.env`, reiniciar la API (`docker compose up -d api`).

## Crear un proyecto

Desde la raíz del repo, con el stack levantado y migrado:

```powershell
docker compose run --rm api python -m app.cli.seeding create --slug center-stage-2026 --event-slug tournament/center-stage-2026-1/event/ultimate-singles --event-date 2026-11-14T00:00:00-03:00 --window-start 2025-11-14T00:00:00-03:00
```

La salida lista las fases del evento con su ID. Luego hay dos formas de cargar datos:

- **Desde start.gg:** en la página, entrar como organizador, marcar «Bajar datos nuevos de start.gg» y pulsar Recalcular. Tarda de 5 a 10 minutos (unas 300 consultas, por debajo del límite de start.gg).
- **Desde los CSV de la Fase 2** (`.cache/seeding`), sin consultar start.gg:

```powershell
docker compose run --rm -v "${PWD}/.cache/seeding:/seeding:ro" api python -m app.cli.seeding load-phase2 --slug center-stage-2026 --dir /seeding --cutoff 2026-10-21T16:58:48-03:00
```

## Fusiones e inscripciones duplicadas

Se aprueban una por una y se aplican en el siguiente cálculo:

```powershell
docker compose run --rm api python -m app.cli.seeding merge --slug center-stage-2026 --from 5363782 --to 5570394
docker compose run --rm api python -m app.cli.seeding duplicate --slug center-stage-2026 --player 5509432 --keep 5570394
docker compose run --rm api python -m app.cli.seeding recalculate --slug center-stage-2026
```

## Ajustes manuales

En la página: flechas ↑/↓ o, al abrir un jugador, «Mover al seed» con un motivo. «Quitar ajuste manual» lo devuelve al puesto del método. Recalcular conserva los ajustes. Todo queda en el registro (`GET /api/v1/seeding/<slug>/audit` con la clave).

## Exportar y subir a start.gg

«Exportar CSV» descarga el orden final con métricas, alertas y explicaciones.

Para escribir los seeds en start.gg:

```powershell
docker compose run --rm api python -m app.cli.seeding push --slug center-stage-2026
```

Sin `--confirm` solo simula: muestra la fase (por defecto la primera, por ejemplo «Pools»), cuántos seeds se asignan y qué inscritos no coinciden. Para escribir, repetir con `--confirm`. Con `--phase-id` se elige otra fase. Los inscritos que estén en start.gg y no en el seeding quedan al final en su orden actual.

## Producción

La guía completa está en [digitalocean-first-deploy.md](digitalocean-first-deploy.md). En resumen: `ADMIN_TOKEN` y `STARTGG_API_TOKEN` son secretos del servicio API (sin `ADMIN_TOKEN` la página es de solo lectura), el job de migraciones aplica exactamente la revisión aprobada (`APPROVED_MIGRATION=0005`), y los comandos se corren desde la consola de la app con `python -m app.runtime seeding --allow-production ...`. Sin `--allow-production` la CLI rechaza escrituras en producción.

## Métodos de cálculo

Cada cálculo puntúa a todos con seis métodos: combinado (el de siempre), Glicko-2, Elo, Bradley-Terry, puntos por posición y % de victorias (Wilson). En la página, **Ver con el método** muestra cómo quedaría el orden con cualquiera de ellos, con la explicación de cada puesto; es solo una vista previa. Con la clave, **Usar como método oficial** lo fija: el seeding oficial, la exportación y los ajustes manuales pasan a usar ese método, y se mantiene al bajar datos nuevos.

## Ranking paraguayo

Un ranking usa el mismo motor con todos los sets de los torneos presenciales de Ultimate Singles jugados en un país:

```powershell
docker compose run --rm api python -m app.cli.seeding create-ranking --slug ranking-py-2026 --name "Ranking Paraguay 2026" --country PY --start 2025-11-14T00:00:00-03:00 --end 2026-11-14T00:00:00-03:00
```

Después, en `/rankings/ranking-py-2026`, entrar con la clave y **Recalcular** con «Bajar datos nuevos de start.gg». Para aparecer hacen falta al menos 10 sets en el período (los demás se pueden mostrar con un botón al final). Los rankings no admiten ajustes manuales.

En producción, desde la consola de `api`: `python -m app.runtime seeding --allow-production create-ranking ...` con los mismos argumentos.
