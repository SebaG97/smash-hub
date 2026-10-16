# Smash PY Hub

Fundación técnica de una plataforma comunitaria de esports. Primera comunidad: Smash Paraguay; primer juego: Super Smash Bros. Ultimate. El dominio admite otros juegos, países, comunidades y tamaños de equipo.

Misión 01: web pública, API de estado, PostgreSQL, migraciones, bootstrap explícito, CI y configuración de despliegue. Sin importador, autenticación, rankings calculados ni resultados publicados.

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
  adr/                  Cinco decisiones iniciales
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

No existen rutas públicas de escritura.

## Documentación

- [Arquitectura](docs/architecture/overview.md) y [módulos](docs/architecture/modules.md).
- [Modelo ER y diccionario](docs/database/schema.md).
- [Contratos](docs/api/contracts.md) y [seguridad](docs/security/security.md).
- [Desarrollo local](docs/operations/local-development.md), [migraciones](docs/operations/migrations.md) y [DigitalOcean](docs/operations/digitalocean-deployment.md).
- [Informe de validación](docs/operations/mission-01-report.md).

DigitalOcean se entrega como plantilla validable, con el repositorio `SebaG97/smash-hub` configurado y pendiente de los datos de la base existente. No se creó ningún recurso ni se conectó a producción. Revisar los datos pendientes antes de cualquier despliegue.

Siguiente misión propuesta, sujeta a aprobación: importación de torneos desde start.gg con fixtures, reconciliación de identidades, reintentos e idempotencia transaccional. No está implementada.
