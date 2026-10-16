# Desarrollo local

Desde la raíz, copiar `.env.example` a `.env`. Docker Compose v2 utiliza exclusivamente PostgreSQL local; no necesita DigitalOcean. Construir con `docker compose build`.

Primera ejecución recomendada:

```sh
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.bootstrap
docker compose up -d --build --wait
```

`run` inicia PostgreSQL y espera su healthcheck. El bootstrap se puede ejecutar dos veces; los UUID de las referencias se conservan. El servidor no aplica migraciones ni hace bootstrap al arrancar.

Web: http://localhost:3000. API: http://localhost:8000/api/v1/meta. Estado: `/api/v1/health/live` y `/api/v1/health/ready`. OpenAPI: http://localhost:8000/api/docs.

La API usa bind mount y `uvicorn --reload`; Next usa bind mount y `next dev`. Los módulos npm y `.next` quedan en volúmenes de desarrollo independientes del host. Tras modificar `package-lock.json`, reconstruir la imagen y actualizar el volumen de módulos con `docker compose run --rm --no-deps web npm ci` antes de reiniciar web.

`WEB_PORT` y `API_PORT` se configuran en `.env`. Si web deja de usar 3000, cambiar `CORS_ORIGINS`; si API deja de usar 8000, cambiar `NEXT_PUBLIC_API_URL`. Esta URL se resuelve en el navegador, por tanto no usar `http://api:8000` en ella. La base no publica puertos. Para desarrollo nativo, usar un PostgreSQL local propio y nunca la base Managed; ajustar URLs al host real.

Estado y logs: `docker compose ps`, `docker compose logs --tail=100 api web`. Detener: `docker compose down` conserva datos. No usar `down -v` en desarrollo salvo que se quiera borrar explícitamente toda la base local. Las variables de inicialización de roles solo se procesan en un volumen nuevo.

Pruebas integradas, con base efímera y nombre/proyecto distinto:

```sh
docker compose -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from api
docker compose -f compose.test.yaml down -v
```

Los wrappers `scripts/dev.ps1 test` y `sh scripts/dev.sh test` hacen la limpieza del entorno de pruebas incluso si falla la suite. No usar `-v` con el compose de desarrollo al limpiar pruebas. CI repite Pytest con PostgreSQL y ejecuta lint, formato, tests, build y TypeScript de frontend.

## Misión 02

Aplicar 0002 en PostgreSQL local y repetir bootstrap. STARTGG_API_TOKEN puede quedar vacío; web y consultas no lo requieren. Configurarlo de manera privada en `.env` para usar la CLI, sin agregarlo a NEXT_PUBLIC_* ni pasarlo como argumento. Procedimiento y preview: [tournament-import](tournament-import.md). Las pruebas HTTP usan MockTransport y fixtures; la suite completa usa PostgreSQL efímero, nunca necesita token real. El contenedor de tests incluye el snapshot OpenAPI para comparar contratos.
