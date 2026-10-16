# Informe final — Misión 01

Fecha: 16 de octubre de 2026. Entrega implementada y verificada localmente; sin commit, push, despliegue ni operaciones sobre producción. Los tres servicios de desarrollo quedan activos para revisión.

## Resultado

Monorepo Git nuevo con Next.js 16.4.2, React 19.3.1, TypeScript 5.9.3 y Tailwind 4.3.3; API FastAPI 0.128.0, Pydantic 2.12.5, SQLAlchemy 2.0.45, Alembic 1.18.1 y psycopg 3.3.5. PostgreSQL local 17.7. Dependencias directas y transitivas fijadas. Docker usa Python 3.13.12 y Node 22.22.0; la comprobación nativa de frontend también pasó con Node 22.14.0.

La web ofrece portada pública responsive, navegación, cuatro módulos con estados vacíos y comprobación de backend con timeout y reintento. No publica jugadores, torneos ni resultados ficticios. La API ofrece salud, metadatos y OpenAPI, sin escrituras públicas. Integraciones y rankings solo tienen contratos.

## Árbol final de entrega

```text
smashHubpy/
├── .github/workflows/ci.yml
├── .dockerignore
├── .env.example
├── .gitattributes
├── .gitignore
├── README.md
├── compose.yaml
├── compose.test.yaml
├── apps/
│   ├── api/
│   │   ├── .python-version
│   │   ├── alembic.ini
│   │   ├── pyproject.toml
│   │   ├── requirements{,-dev}.{in,txt}
│   │   ├── app/
│   │   │   ├── main.py, bootstrap.py, runtime.py
│   │   │   ├── core/          config.py, errors.py, logging.py
│   │   │   ├── database/      base.py, session.py, models.py
│   │   │   ├── health/        router.py
│   │   │   ├── communities/   models.py, service.py
│   │   │   ├── games/         models.py
│   │   │   ├── players/       models.py
│   │   │   ├── competitions/  models.py
│   │   │   ├── integrations/  models.py, contracts.py
│   │   │   └── rankings/      contracts.py
│   │   ├── migrations/
│   │   │   ├── env.py, script.py.mako
│   │   │   └── versions/0001_initial.py
│   │   └── tests/             conftest.py, test_config.py, test_health.py, test_postgres.py
│   └── web/
│       ├── package.json, package-lock.json
│       ├── .nvmrc, .prettierignore
│       ├── next.config.ts, next-env.d.ts, tsconfig.json
│       ├── eslint.config.mjs, postcss.config.mjs, vitest.config.ts
│       ├── src/app/           layout.tsx, page.tsx, globals.css, error.tsx, not-found.tsx
│       │   └── [module]/page.tsx
│       ├── src/components/backend-status.tsx
│       ├── src/lib/modules.ts
│       └── tests/             setup.ts, home.test.tsx
├── infra/
│   ├── docker/               api.Dockerfile, web.Dockerfile, init-db.sh
│   └── digitalocean/         app.yaml, migration-job.yaml
├── scripts/
│   ├── dev.ps1, dev.sh
│   ├── combine_app_spec.py
│   └── generate_schema_docs.py
└── docs/
    ├── adr/                  ADR-001.md … ADR-005.md
    ├── architecture/         overview.md, modules.md
    ├── database/schema.md
    ├── api/                  contracts.md, openapi.json
    ├── security/security.md
    └── operations/           local-development.md, digitalocean-deployment.md,
                             migrations.md, mission-01-report.md
```

Los `__init__.py` completan los paquetes Python. `.env`, `.venv`, cachés, `node_modules`, `.next` y logs son locales y están excluidos de Git.

## Tablas y migración

Revisión `0001_initial.py`: 19 tablas, índices/FK/unique/check, cinco triggers diferidos y cuatro funciones auxiliares. `alembic_version` es una tabla adicional de infraestructura.

| Grupo | Tablas |
| --- | --- |
| Geografía | countries, regions |
| Comunidades y juegos | communities, games, characters, community_games |
| Identidad | players, player_aliases, external_identities |
| Competiciones | tournaments, tournament_participants, events, event_entrants, entrant_members, sets, set_sides |
| Integraciones | data_sources, import_jobs, external_mappings |

`tournament_participants` se agrega para separar persona, inscripción al torneo y entrant al evento (ADR-004). El modelo usa UUID y timestamps con zona horaria; admite distintos juegos/comunidades y rosters de 1, 2 o más personas. Las restricciones impiden lados de otro evento, miembros de otro torneo, rosters incorrectos, resultados incoherentes y duplicación de un set externo mediante su mapping.

El bootstrap local, ejecutado dos veces, dejó exactamente: Paraguay 1, Smash Paraguay 1, SSBU 1, start.gg 1 y community_games 1; players 0 y tournaments 0.

## Endpoints disponibles

| Método | Ruta | Resultado local |
| --- | --- | --- |
| GET | /api/v1/health/live | 200, alive |
| GET | /api/v1/health/ready | 200, ready; consulta PostgreSQL |
| GET | /api/v1/meta | 200, versión 0.1.0 y capacidades |
| GET | /api/openapi.json | 200, OpenAPI 3.1.0 |
| GET | /api/docs | Swagger UI |
| GET | /api/redoc | ReDoc |

Web: http://localhost:3000. API: http://localhost:8000/api/docs. Las rutas `/`, `/jugadores`, `/torneos`, `/rankings` y `/estadisticas` devolvieron HTML con HTTP 200.

## Comandos y verificaciones ejecutadas

| Comando / comprobación | Resultado |
| --- | --- |
| git init -b main | Repositorio inicializado; sin commit ni remoto inventado |
| Instalación npm con versiones exactas y resolución Python en .venv | Completadas; lockfiles incluidos |
| docker compose config --quiet | Válido usando variables locales |
| docker compose run --rm api alembic upgrade head | Revisión 0001 aplicada en PostgreSQL local |
| docker compose run --rm api python -m app.bootstrap (dos ejecuciones) | Sin duplicados; conserva UUID |
| docker compose up -d --build --wait | postgres, api y web saludables |
| docker compose -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from api | **30 passed**, sin omisiones |
| docker compose -f compose.test.yaml down -v | Entorno de pruebas retirado; desarrollo conservado |
| ruff check apps/api | Aprobado |
| ruff format --check apps/api | 34 archivos conformes |
| npm run lint | Aprobado |
| npm run format:check | Aprobado |
| npm test | **3 passed** |
| npm run build | Aprobado; portada y cuatro módulos generados |
| npm run typecheck | Aprobado |
| npm audit durante instalación final | 0 vulnerabilidades reportadas |
| doctl apps spec validate --schema-only app.yaml | Aprobado con doctl 2.0.0, sin token |
| Misma validación del spec compuesto con job | Aprobado |
| Peticiones HTTP locales a portada, cuatro módulos y API | Aprobadas |
| Consulta de rol real de API | smash_app; CREATE en public = false |

La suite PostgreSQL aplica, compara con metadata, revierte y reaplica la migración; comprueba bootstrap, salud real, singles/dobles/rosters mayores, varios juegos y comunidades, resultados válidos y rechazo de inconsistencias/duplicados. La prueba de errores inesperados comprueba que no se expongan secretos ni en HTTP ni en logs. Los datos competitivos de prueba existen únicamente en la base efímera.

Se corrigieron durante la validación: colisión de nombres de restricciones compuestas, finales CRLF de un script Linux, incompatibilidades entre herramientas npm y una cadena de dependencias de lint vulnerable. La suite final pasa. Permanece un warning de deprecación de Starlette/AnyIO en TestClient; no afecta ejecución ni resultados. Vitest avisa sobre un futuro cambio del cargador de configuración; el test actual pasa.

## Instalación y ejecución para revisión

Con `.env` local ya creado:

```powershell
./scripts/dev.ps1 up
./scripts/dev.ps1 test
./scripts/dev.ps1 down
```

En un checkout nuevo:

```powershell
Copy-Item .env.example .env
./scripts/dev.ps1 install
./scripts/dev.ps1 migrate
./scripts/dev.ps1 bootstrap
./scripts/dev.ps1 up
```

Los equivalentes POSIX están en `scripts/dev.sh`. `down` conserva la base. No ejecutar `down -v` sobre desarrollo salvo que se quiera eliminar explícitamente su información.

## DigitalOcean y límites de verificación

App Spec y fragmento de migración preparados y validados contra el esquema de la herramienta oficial. [Referencia oficial](https://docs.digitalocean.com/products/app-platform/reference/app-spec/). El job está inactivo por defecto, requiere credencial separada y aprobación explícita de revisión 0001. No hay jobs programados activos. CI utiliza doctl con `no_auth: true` y no contiene pasos de despliegue.

Pendientes de configuración antes de desplegar: repositorio GitHub real, rama, clúster/base/usuario existentes, región y tamaño de instancias, Trusted Sources, VPC si corresponde, secreto de migración y backup. La validación de esquema no verifica estos recursos, permisos ni conectividad real. No se accedió a una cuenta ni a PostgreSQL Managed.

GitHub Actions está escrito para cada PR y push a main; la ejecución en GitHub queda pendiente de publicar el repositorio. Sus comprobaciones principales se ejecutaron localmente. No se pudo hacer revisión visual interactiva porque la herramienta no encontró ningún navegador conectado; se verificaron render HTML por HTTP, estructura accesible, tests y compilación. Conviene revisar visualmente móvil/escritorio durante la revisión humana.

No se usaron ni incorporaron credenciales reales. Los secretos presentes en ejemplos son exclusivamente contraseñas desechables locales/de prueba. Antes de habilitar escrituras o importaciones, quedan para futuras misiones autenticación/autorización, auditoría, reconciliación de identidades y políticas operativas de publicación de resultados.

## Documentación actualizada

README, arquitectura general, responsabilidades de módulos, ER/diccionario, contratos/OpenAPI, seguridad, desarrollo local, migraciones/rollback, despliegue DigitalOcean y cinco ADRs. Los detalles se enlazan desde README.

## Próxima misión propuesta

Diseñar e implementar una importación controlada de start.gg con fixtures, pruebas de reconciliación, upserts transaccionales, trazabilidad y reintentos. Su alcance y permisos deberán revisarse primero. No se avanzó a Misión 02.
