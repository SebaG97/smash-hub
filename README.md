# Smash PY Hub

Fundación técnica de una plataforma comunitaria de esports. Primera comunidad: Smash Paraguay; primer juego: Super Smash Bros. Ultimate. El dominio admite otros juegos, países, comunidades y tamaños de equipo.

Misión 03: estadísticas competitivas e historial Head-to-Head sobre resultados locales elegibles, con filtros por juego, modalidad, torneo, comunidad y período. Conserva el importador start.gg y la clasificación de Misiones 02/02.1. Sin ratings, seeding ni rankings calculados; revisión del responsable pendiente.

Misión 05: página de seeding por evento (`/seeding`) con propuesta explicada (Glicko-2 de la Misión 04 + posiciones), ajustes manuales auditados, recálculo, descarga de datos de start.gg, exportación CSV y subida a start.gg por comando (ADR-011).

Misión 05.1: seis métodos de cálculo comparables en la misma página (combinado, Glicko-2, Elo, Bradley-Terry, puntos por posición y % de victorias Wilson), con vista previa y método oficial; ranking del circuito paraguayo en `/rankings` con los torneos presenciales de start.gg (ADR-012).

## Inicio local

Requisitos: Git, Docker Desktop con motor Linux y Docker Compose v2. Puertos predeterminados: web 3000 y API 8000. PostgreSQL no publica puertos.

```powershell
Copy-Item .env.example .env
./scripts/dev.ps1 install
./scripts/dev.ps1 migrate
./scripts/dev.ps1 bootstrap
./scripts/dev.ps1 up
```

En Linux/macOS: `cp .env.example .env` y `sh scripts/dev.sh install`, `migrate`, `bootstrap`, `up`.

Abrir http://localhost:3000 y http://localhost:8000/api/docs. Detener sin borrar datos: `./scripts/dev.ps1 down`. El bootstrap puede repetirse. Las migraciones no se ejecutan al arrancar la API.

`docker compose up -d --build --wait` también inicia los tres servicios; para una base recién creada, ejecutar luego `docker compose run --rm api alembic upgrade head` y `docker compose run --rm api python -m app.bootstrap` explícitamente.

`.env` contiene solo credenciales locales al copiar el ejemplo. Nunca utilizar credenciales de producción. Si se cambian los puertos, ajustar `NEXT_PUBLIC_API_URL` y `CORS_ORIGINS`.

## Verificaciones

```powershell
./scripts/dev.ps1 test
cd apps/web
npm ci
npm run lint
npm run format:check
npm test
npm run build
npm run typecheck
```

Para desarrollo nativo: Python 3.13, Node según `apps/web/.nvmrc`; `python -m venv .venv`, activar el entorno, `pip install -r apps/api/requirements-dev.txt`. En `apps/api`: `ruff check .`, `ruff format --check .`, `pytest -q`. Sin `TEST_DATABASE_URL`, las pruebas PostgreSQL se omiten; la suite Compose y CI no las omiten. No apuntar los tests a una base existente.

Las dependencias Python directas están en `.in`, las resoluciones transitivas fijadas en `.txt`; npm usa versiones exactas y `package-lock.json`. Al actualizar, resolver en un entorno limpio y validar Python/Linux y frontend antes de aceptar el cambio.

## Estructura

```text
apps/
  api/                  FastAPI, módulos, Alembic y Pytest
  web/                  Next.js App Router, Tailwind y Vitest
infra/
  docker/               Imágenes y rol local de aplicación
  digitalocean/         App Spec y fragmento inactivo de migración
docs/
  adr/                  Diez decisiones de arquitectura
  architecture/         Arquitectura y responsabilidades
  database/             ER y diccionario de las 19 tablas
  api/                  Contratos y OpenAPI
  security/             Controles y riesgos
  operations/           Desarrollo, despliegue y migraciones
.github/workflows/      CI en PR y main
scripts/                Comandos locales y composición del App Spec
compose.yaml            Desarrollo con volumen persistente
compose.test.yaml       Tests con PostgreSQL efímero independiente
.env.example            Variables locales sin secretos reales
```

## API

| GET | Respuesta |
| --- | --- |
| `/api/v1/health/live` | 200, proceso vivo; no abre conexión |
| `/api/v1/health/ready` | 200 si PostgreSQL responde; 503 si no |
| `/api/v1/meta` | Nombre, versión y capacidades disponibles |
| `/api/openapi.json` | Contrato OpenAPI |
| `/api/docs`, `/api/redoc` | Documentación interactiva |

Las únicas escrituras son las de seeding (`/api/v1/seeding`), protegidas con `ADMIN_TOKEN`; sin esa variable la API es de solo lectura. Ver [docs/operations/seeding.md](docs/operations/seeding.md).

## Documentación

- [Arquitectura](docs/architecture/overview.md) y [módulos](docs/architecture/modules.md).
- [Modelo ER y diccionario](docs/database/schema.md).
- [Contratos](docs/api/contracts.md) y [seguridad](docs/security/security.md).
- [Desarrollo local](docs/operations/local-development.md), [migraciones](docs/operations/migrations.md) y [DigitalOcean](docs/operations/digitalocean-deployment.md).
- [Informe de validación](docs/operations/mission-01-report.md).

DigitalOcean se entrega como plantilla validable, con el repositorio `SebaG97/smash-hub` configurado y pendiente de los datos de la base existente. No se creó ningún recurso ni se conectó a producción. Revisar los datos pendientes antes de cualquier despliegue.

## Importar un torneo

Después de migrar y hacer bootstrap, configurar `STARTGG_API_TOKEN` solo en el entorno privado de API:

```sh
docker compose run --rm api python -m app.cli.import_tournament --slug nombre-del-torneo --dry-run
docker compose run --rm api python -m app.cli.import_tournament --slug nombre-del-torneo
```

No hay escritura HTTP. Sin token, el sitio sigue funcionando y la CLI informa un error claro. La CLI bloquea producción en esta misión. Ver [integración](docs/integrations/startgg.md), [runbook](docs/operations/tournament-import.md) e [informe Misión 02](docs/operations/mission-02-report.md) y [plan de validación corregido](docs/operations/mission-02-validation-plan.md).

Vistas: `/tournaments`, `/tournaments/[id]`, `/events/[id]`, `/players`, `/players/[id]`. `/torneos` y `/jugadores` redirigen a las nuevas rutas. Listados paginados, búsqueda y resultados persistidos; sin datos ficticios ni rankings. La API añade GET `/api/v1/tournaments`, `/{id}`, `/{id}/events`, `/api/v1/events/{id}`, `/{id}/entrants`, `/{id}/sets`, `/api/v1/players` y `/{id}`. Ver contratos para parámetros.

La revisión incremental 0002 conserva 0001 sin cambios. Consolidación Git y continuación a Misión 03 autorizadas por el responsable; sin autorización de push ni despliegue.

Auditoría Misión 02.1: clasificación de estado/resolución/elegibilidad, migración 0003 y separación de entradas del bracket en API y web. Ver [informe y matrices](docs/operations/mission-02-1-report.md).

## Estadísticas y Head-to-Head — Misión 03

Desde `/players`, abrir un perfil para consultar estadísticas, rivales frecuentes y últimos resultados; un rival enlaza a `/players/[id]/vs/[opponentId]`. `/estadisticas` muestra los récords de la comunidad (Misión 13). La web ofrece filtros de juego/modalidad y período, carga, errores, vacío y paginación. No calcula métricas competitivas.

Nuevos GET bajo `/api/v1/players/{id}`: `/statistics`, `/matches`, `/opponents`, `/placements`, `/head-to-head/{opponent_id}`. Requieren `game_id`; `mode=singles|doubles`, torneo, comunidad y timestamps con offset opcionales. `PlayerDetail.scopes` proporciona los ámbitos disponibles. Win rate sin sets es `null`; DQ/BYE/bracket no generan victorias jugadas. Sin nuevas migraciones ni servicios.

Ver [definiciones y reglas](docs/statistics.md), [ADR-010](docs/adr/ADR-010.md), [contratos](docs/api/contracts.md) e [informe de Misión 03](docs/operations/mission-03-report.md). Validación local reproducible en solo lectura:

```powershell
docker compose run --rm --no-deps -T api python -m app.cli.validate_statistics --slugs gg-fest-x-eon game-over-sep super-smash-burgame-7
```

Misiones 02/02.1 consolidadas en `d402e64`. Misión 03 queda sin commit, push ni despliegue para revisión. No se inicia Misión 04.

Misión 06: importación de torneos de Paraguay desde la web (`/tournaments`, con clave de organizadores) y personajes por partida desde start.gg; el listado y la ficha de cada jugador muestran sus mains (ADR-013).

Misión 07: casilla «Cuenta para el ranking» por torneo importado (los desmarcados no cuentan en los rankings) e íconos de los mains junto al nombre de cada jugador en jugadores, seeding y ranking.

Misión 08: vista pública limpia (seedings como borradores hasta publicarlos, ranking sin datos internos) y acceso único de organizadores en `/admin`, con la protección también en la API.

Misión 13: emblemas y récords en la ficha de cada jugador, récords y jugador del mes en `/estadisticas` y la portada, resumen de cada torneo, calendario de próximos torneos desde start.gg e imágenes para redes del top de torneos y rankings (ADR-014).

Misión 14: la imagen para redes pasa a ser un podio con los renders oficiales de los mains y el traje que elige el organizador para cada jugador (ADR-015, migración 0011). Opcionalmente, el organizador puede subir sus propias imágenes para cualquier puesto antes de generarla; no se guardan.

Misión 15: página de personajes de la escena (`/personajes`), matchups contra cada personaje en la ficha y vistas previas con imagen al compartir links de jugadores, torneos y rankings.

Misión 16: previa de los próximos torneos (`/previa/{slug}`, desde la portada): inscritos de start.gg, rachas y rivalidades; los seeds, favoritos y cruces probables aparecen al publicar el seeding oficial del hub.

Misión 17: casilla de organizadores «Seeding mal hecho» por torneo: sus seeds no cuentan para sorpresas, emblemas ni «rindió por encima de su seed» (migración 0012).

Misión 18: en la previa, los inscritos sin resultados en el hub (extranjeros o debutantes) muestran a pedido su último año en start.gg: récord, torneos, mains y mejores resultados.

Misión 19: logos y banners de start.gg en torneos, previas y calendarios (migración 0013). Para los torneos ya importados, el botón de organizadores «Traer logos y banners de start.gg» en `/tournaments`.

Misión 20: eventos principales y secundarios (amateur, ladder, pre) por torneo: solo los principales suman para el ranking y los títulos; pestañas por evento y casilla de organizadores (migración 0014).

Misión 21: jugador del mes por rendimiento (posición según tamaño, superar el seed y sorpresas) y por región, Gran Asunción y Ciudad del Este, con historial mes por mes (ADR-016).

Misión 22: prefijos de start.gg («BG | Wesker») y página de equipos (`/equipos`); los organizadores aprueban, unen u ocultan cada prefijo antes de que se muestre (migración 0015).

Misión 23: imagen mensual del ranking completo para redes, con requisitos y el cambio de puesto de cada jugador respecto al mes anterior.

Misión 24: el ranking pide 2 torneos presenciales (uno en los últimos 6 meses) en vez de 10 sets, y muestra las listas «Por entrar» e «Inactivos» (ADR-017).

Misión 25: bracket de cada evento en la página del torneo (fases, personajes partida por partida) y bracket proyectado en la previa cuando el seeding del hub está publicado.

Misión 26: el jugador del mes premia superar lo esperado: la posición pesa poco y pesan los escalones sobre el seed y las sorpresas (ADR-018).

Misión 27: página en vivo (`/en-vivo/{slug}`) con bracket y posiciones leídos de start.gg mientras se juega, e imagen del top apenas termina la gran final.

Misión 28: imagen para redes de los jugadores del mes, con los datos que explican por qué ganaron.
