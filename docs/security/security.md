# Seguridad

La configuración se obtiene del entorno; `DATABASE_URL` es obligatoria y Pydantic la representa como secreto. Producción exige PostgreSQL con `sslmode=verify-full`, CA y orígenes HTTPS explícitos. El launcher de App Platform materializa la CA enlazada en un archivo temporal con permisos restringidos y fuerza verificación de certificado y hostname. No hay credenciales ni tokens de start.gg.

`.env`, claves privadas, certificados locales, cachés y artefactos se excluyen de Git y del contexto Docker. `.env.example` contiene contraseñas de desarrollo reconocibles y desechables. `NEXT_PUBLIC_*` es público: jamás usarlo para secretos. No volcar configuración, URLs de conexión, parámetros SQL, cuerpos de proveedores ni excepciones completas a logs. El logger de errores HTTP registra solo el tipo de excepción y no se activa el access log de Uvicorn.

CORS permite orígenes concretos y métodos GET; no sustituye autenticación. No existen escrituras HTTP en esta misión. Los servicios API y web de producción se ejecutan sin root. PostgreSQL no publica ningún puerto en Compose. API y web solo se publican en loopback local.

El rol `smash_app` local tiene CONNECT, USAGE y SELECT/INSERT/UPDATE/DELETE sobre tablas creadas por el propietario; no tiene CREATE en public ni capacidades de administración. `smash_migrator` es exclusivamente el propietario de desarrollo. El bootstrap se ejecuta con el rol de aplicación. Producción requiere un migrador separado sin superusuario, propietario solo del esquema de la app, y un usuario limitado de aplicación; no usar `doadmin` para servir HTTP. El servicio de producción no recibe `MIGRATION_DATABASE_URL`. El job de migración la recibe solo cuando un operador aprueba la ejecución.

Los roles locales se crean en la primera inicialización del volumen. Cambiar `.env` no cambia las contraseñas existentes. En producción el operador prepara los roles y grants con herramientas seguras; no existe automatización que modifique la base administrada.

Riesgos pendientes para futuras misiones:

- Dos personas pueden compartir tag, y una persona puede tener varias cuentas. No fusionar identidades por tag; conservar procedencia y revisión humana.
- Un proveedor puede corregir resultados o recibir datos manipulados. Registrar sincronización, validar rosters/resultados y diseñar trazabilidad de cambios antes de publicar estadísticas.
- Autorización administrativa, auditoría inmutable, límites de peticiones y protección de acciones sensibles deberán implementarse antes de habilitar escrituras.
- Los aliases no se borran al cambiar un tag; sus intervalos deben mantenerse transaccionalmente por el futuro servicio de identidad.
- Backups, restauración verificada y política de retención/privacidad quedan a cargo del plan operativo de producción.

Usar Trusted Sources de DigitalOcean para permitir solo la aplicación y el acceso administrativo necesario. Mantener PostgreSQL fuera de ingress y nunca habilitar `0.0.0.0/0` como solución a fallos de conexión. Ver detalles de TLS y red en el runbook de despliegue.
