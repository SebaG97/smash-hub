# DigitalOcean App Platform

Estado: preparación declarativa; no se creó aplicación, base ni ningún otro recurso, no se gastó en DigitalOcean y no se conectó a producción.

`infra/digitalocean/app.yaml` usa dos servicios del mismo repositorio, con `source_dir` `/apps/web` y `/apps/api`, comandos de build/run explícitos y healthchecks HTTP. Ingress conserva `/api` para FastAPI y dirige `/` a Next. El dominio administrado de App Platform proporciona HTTPS. El frontend compila con `/api/v1`, sin necesitar acceso a la base durante build.

El repositorio `SebaG97/smash-hub` est? configurado en ambos servicios y en el fragmento de migraci?n. Completar la rama si difiere de main, `REPLACE_EXISTING_CLUSTER_NAME`, `REPLACE_EXISTING_DATABASE_NAME` y `REPLACE_LIMITED_APP_USER`. Elegir región, VPC y tamaños de instancia según la base existente y presupuesto. No se inventa un ID de VPC ni un nombre de clúster. `deploy_on_push` permanece desactivado.

En el panel, usar **Attach DigitalOcean database** y seleccionar la Managed Database existente; no seleccionar Create dev database. En el spec se usa `production: true` con `cluster_name` explícito. Verificar que el nombre y usuario correspondan a recursos ya existentes antes de enviar cualquier spec.

La aplicación enlaza `${hub-db.DATABASE_URL}` como secreto de runtime y `${hub-db.CA_CERT}` como CA. `python -m app.runtime` escribe la CA a un archivo temporal privado, cambia sslmode a verify-full y arranca Uvicorn en 8000. No se desactiva validación de hostname. CORS usa `${APP_URL}`. No exponer secretos en variables públicas de Next ni durante build.

Con aplicación y base en la misma VPC, configurar su ID real en `vpc.id` y cambiar el enlace a `${hub-db.DATABASE_PRIVATE_URL}`; comprobar compatibilidad de la región y conectividad. Si no se dispone de ruta privada, usar el endpoint TLS con Trusted Sources limitado a la aplicación. Nunca desactivar Trusted Sources para permitir builds: los builds de esta solución no consultan PostgreSQL.

El rol de aplicación no debe ser propietario ni superusuario. El operador debe preparar CONNECT/USAGE y DML sobre las tablas; el migrador posee el esquema y concede privilegios de tablas futuras al rol de aplicación. Mantener la URL de migración únicamente en el job como secreto cifrado. No publicar SQL con contraseñas en Git. Presupuesto de conexiones: máximo cinco por proceso API; sumar réplicas, migraciones y mantenimiento frente al límite del clúster existente.

El job `infra/digitalocean/migration-job.yaml` es un fragmento inactivo. Componer para revisión con `python scripts/combine_app_spec.py`; agregar en un spec privado el secreto `MIGRATION_DATABASE_URL` y la aprobación `APPROVED_MIGRATION=0001`. Ejecutar únicamente después de backup y revisión de SQL. No hay jobs programados activos. Futuras sincronizaciones usarán un job SCHEDULED separado, cuya frecuencia, credenciales, límites y reintentos se decidirán en la misión correspondiente.

Validación local sin token ni acceso a cuenta:

```sh
doctl apps spec validate --schema-only infra/digitalocean/app.yaml
python scripts/combine_app_spec.py > /tmp/app-with-migration.yaml
doctl apps spec validate --schema-only /tmp/app-with-migration.yaml
```

La validación de esquema no confirma existencia del repositorio, clúster, usuario, región, permisos ni conectividad. La validación semántica de cuenta y despliegue requiere revisión posterior del propietario; esta misión no la ejecuta. CI valida el esquema, nunca crea ni actualiza aplicaciones.

Fuentes oficiales consultadas el 16 de octubre de 2026: [App Spec](https://docs.digitalocean.com/products/app-platform/reference/app-spec/), [variables enlazadas](https://docs.digitalocean.com/products/app-platform/how-to/use-environment-variables/), [asociación de bases](https://docs.digitalocean.com/products/app-platform/how-to/create-apps/) y [validación doctl](https://docs.digitalocean.com/reference/doctl/reference/apps/spec/validate/).
