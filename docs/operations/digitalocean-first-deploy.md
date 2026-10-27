# Primer despliegue en DigitalOcean (paso a paso)

Guía para publicar el hub con la Misión 05 (seeding) en App Platform con una base PostgreSQL administrada. Complementa [digitalocean-deployment.md](digitalocean-deployment.md) (decisiones de seguridad) y [seeding.md](seeding.md).

Costo aproximado: base de datos desde ~15 USD/mes, más dos servicios básicos (web y API) de ~5 USD/mes cada uno.

> Nada de esta guía se ejecuta solo. Cada paso lo hace una persona con acceso a la cuenta. Los valores secretos (contraseñas, claves, tokens) **nunca** se suben a Git.

## 0. Código en GitHub

App Platform despliega la rama `main` de `SebaG97/smash-hub`. Tiene que contener las Misiones 02 a 05 (hoy están en `feature/mission-05-seeding`):

```powershell
git checkout main
git merge --ff-only feature/mission-05-seeding
git push origin main
```

## 1. Crear la base de datos

En el panel: **Databases → Create Database Cluster**.

- Motor: **PostgreSQL 17**.
- Región: **New York (NYC3)**, la más cercana a Paraguay. Usar la misma región para la app.
- Plan: el más chico (1 vCPU, 1 GB) alcanza.
- Nombre del clúster: por ejemplo `smash-py-db`. Anotarlo: es `cluster_name` en el paso 4.

Cuando el clúster esté listo, en la pestaña **Users & Databases**:

1. Crear la base `smashhub`.
2. Crear los usuarios `smash_migrator` (dueño del esquema, solo para migraciones) y `smash_app` (el que usa la API). El panel genera las contraseñas.

## 2. Permisos

En **Overview → Connection details**, elegir el usuario `doadmin`, la base `defaultdb` y el formato **Connection string**. Conectarse desde la PC con Docker (no hace falta instalar psql). Antes, agregar tu IP en **Settings → Trusted sources**:

```powershell
docker run --rm -it postgres:17.7-alpine psql "PEGAR_CONNECTION_STRING_DE_DOADMIN"
```

Dentro de psql, pegar:

```sql
GRANT smash_migrator TO doadmin;
ALTER DATABASE smashhub OWNER TO smash_migrator;
\c smashhub
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE smashhub TO smash_app;
GRANT USAGE ON SCHEMA public TO smash_app;
ALTER DEFAULT PRIVILEGES FOR ROLE smash_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO smash_app;
\q
```

Así las tablas que cree el migrador quedan disponibles para `smash_app`, que no puede crear ni borrar tablas. Después se puede quitar tu IP de Trusted sources.

## 3. Conectar GitHub

En **Apps → Create App → GitHub**, autorizar a DigitalOcean a leer el repositorio `SebaG97/smash-hub`. Si el asistente ofrece crear la app, cancelarlo: la creamos con el spec del paso 5.

## 4. Preparar el spec privado

Generar una copia privada (la carpeta `.cache/` está ignorada por Git):

```powershell
python scripts/combine_app_spec.py > .cache/app-private.yaml
```

Editar `.cache/app-private.yaml`:

1. Debajo de `name: smash-py-hub`, agregar `region: nyc`.
2. En `databases`: `cluster_name: smash-py-db` (el del paso 1), `db_name: smashhub`, `db_user: smash_app`.
3. En el servicio `api`, completar los dos secretos (quitar el comentario no hace falta):

   ```yaml
   - key: ADMIN_TOKEN
     scope: RUN_TIME
     type: SECRET
     value: "CLAVE_DE_ORGANIZADORES"   # >= 24 caracteres
   - key: STARTGG_API_TOKEN
     scope: RUN_TIME
     type: SECRET
     value: "TOKEN_DE_START_GG"
   ```

   Generar la clave con `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Es la que van a usar los organizadores en la página; conviene que sea distinta de la local.

4. En el job `migrate`, agregar al final de sus `envs`:

   ```yaml
   - key: MIGRATION_DATABASE_URL
     scope: RUN_TIME
     type: SECRET
     value: "postgresql://smash_migrator:CONTRASEÑA@HOST:25060/smashhub?sslmode=require"
   - key: APPROVED_MIGRATION
     scope: RUN_TIME
     value: "0005"
   ```

   El host y el puerto están en **Connection details** del clúster (usuario `smash_migrator`, base `smashhub`). El job aplica exactamente hasta la revisión 0005 antes de cada despliegue y nunca hace downgrade.

Validar el archivo:

```powershell
.cache/doctl/doctl.exe apps spec validate --schema-only .cache/app-private.yaml
```

## 5. Crear la app

Con `doctl` (crear un token en **API → Generate New Token**):

```powershell
.cache/doctl/doctl.exe auth init
.cache/doctl/doctl.exe apps create --spec .cache/app-private.yaml
```

Después, **borrar `.cache/app-private.yaml`**: DigitalOcean ya guardó los secretos cifrados.

Esperar a que el despliegue termine (en el panel: **Activity**). Orden esperado: build de web y API → job `migrate` → servicios activos. Si el job falla, revisar sus logs; lo más común es la contraseña o los permisos del paso 2.

Luego, en el clúster de base de datos, **Settings → Trusted sources**: agregar la app `smash-py-hub` (sin esto la API no conecta).

## 6. Comprobar

Con la URL que muestra el panel (`https://smash-py-hub-xxxxx.ondigitalocean.app`):

- `/api/v1/health/ready` → `{"status":"ready"}`.
- `/` muestra el hub y `/seeding` dice que todavía no hay seedings.

## 7. Datos de referencia y el seeding de CENTER STAGE

En el panel de la app: **Console** del componente `api`. Los comandos pasan por `app.runtime`, que prepara el certificado de la base.

```sh
python -m app.runtime bootstrap --allow-production

python -m app.runtime seeding --allow-production create --slug center-stage-2026 \
  --event-slug tournament/center-stage-2026-1/event/ultimate-singles \
  --event-date 2026-11-14T00:00:00-03:00 --window-start 2025-11-14T00:00:00-03:00 \
  --name "CENTER STAGE 2026 · Ultimate Singles"

for pair in 5363782:5570394 5485348:5504518 5492313:5512649 5091548:4803003 5208244:4803003 \
            5455095:4803003 5091546:4803021 5208245:4803021 5132433:5207491; do
  python -m app.runtime seeding --allow-production merge --slug center-stage-2026 \
    --from "${pair%%:*}" --to "${pair##*:}"
done
python -m app.runtime seeding --allow-production duplicate --slug center-stage-2026 \
  --player 5509432 --keep 5570394
```

Después, en `https://<app>/seeding/center-stage-2026`:

1. Entrar como organizador con la clave del paso 4.
2. Marcar **Bajar datos nuevos de start.gg** y pulsar **Recalcular** (5 a 10 minutos).
3. Volver a aplicar los ajustes manuales acordados: Chag al seed 1 y Pocketo al 14, con su motivo.

## Después del primer despliegue

- **Nuevas migraciones:** cambiar `APPROVED_MIGRATION` en el job (panel → componente `migrate` → Environment Variables) a la nueva revisión, después de un backup.
- **Actualizar el código:** `deploy_on_push` está desactivado. Tras hacer push a `main`, desplegar con **Deploy** en el panel o `doctl apps create-deployment <app-id>`.
- **Rotar la clave de organizadores:** cambiar `ADMIN_TOKEN` en el componente `api`; la app se redespliega sola.
- **Subir seeds a start.gg:** no está habilitado desde la web. Se decidió hacerlo todo en el hub.

## Actualización a la Misión 05.1 (métodos y ranking)

Este código necesita la migración **0006** antes de arrancar. Antes de desplegarlo:

1. En la app, componente **`migrate`** → **Settings → Environment Variables**: cambiar `APPROVED_MIGRATION` de `0005` a `0006` y guardar.
2. Desplegar (**Actions → Deploy**). El job aplica 0006 y luego arrancan `web` y `api`.
3. Crear el ranking desde la consola de `api`:

```sh
python -m app.runtime seeding --allow-production create-ranking --slug ranking-py-2026 \
  --name "Ranking Paraguay 2026" --country PY \
  --start 2025-11-14T00:00:00-03:00 --end 2026-11-14T00:00:00-03:00
```

4. En `/rankings/ranking-py-2026`, entrar con la clave y recalcular con «Bajar datos nuevos de start.gg».

## Actualización a la Misión 06 (jugadores, mains e importación)

1. Componente **`migrate`** → *Environment Variables*: `APPROVED_MIGRATION` = `0007`.
2. **Actions → Force rebuild and deploy**. El job debe mostrar `Running upgrade 0006 -> 0007`.
3. En `/tournaments`, «Organizadores: importar torneos desde start.gg» → entrar con la clave → elegir el período → **Importar todos los de Paraguay**. Son ~30 torneos y tarda entre 10 y 20 minutos. No redesplegar mientras corre; si se corta, repetirlo es seguro.
4. Revisar `/players`: cada jugador muestra su main y la ficha los porcentajes.

## Actualización a la Misión 07 (marca de ranking e íconos)

1. `migrate` → `APPROVED_MIGRATION` = `0008`.
2. **Force rebuild and deploy** (`Running upgrade 0007 -> 0008`).
3. Para bajar los íconos de personajes, lanzar cualquier importación desde `/tournaments`: puede ser la de todos los torneos de Paraguay o un solo link. El catálogo de personajes se sincroniza al empezar.
4. En `/tournaments`, con la clave, desmarcar «Cuenta para el ranking» en los torneos que no deben contar. Los rankings se recalculan solos.
