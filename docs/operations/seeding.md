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

`infra/digitalocean/app.yaml` no define `ADMIN_TOKEN`, así que el hub publicado queda de solo lectura. Para habilitar la edición, agregarla como secreto del servicio API (y `STARTGG_API_TOKEN` si se quiere la descarga), revisar ADR-011 y aplicar la migración 0005 con el job de migraciones. La CLI rechaza escrituras con `ENVIRONMENT=production`.
