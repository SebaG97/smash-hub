# Seguridad

La configuración se obtiene del entorno; `DATABASE_URL` es obligatoria y Pydantic la representa como secreto. Producción exige PostgreSQL con `sslmode=verify-full`, CA y orígenes HTTPS explícitos. El launcher de App Platform materializa la CA enlazada en un archivo temporal con permisos restringidos y fuerza verificación de certificado y hostname. STARTGG_API_TOKEN es un secreto opcional del servidor (CLI y, desde la Misión 05, lecturas de seeding en la API); nunca forma parte del frontend ni de snapshots.

`.env`, claves privadas, certificados locales, cachés y artefactos se excluyen de Git y del contexto Docker. `.env.example` contiene contraseñas de desarrollo reconocibles y desechables. `NEXT_PUBLIC_*` es público: jamás usarlo para secretos. No volcar configuración, URLs de conexión, parámetros SQL, cuerpos de proveedores ni excepciones completas a logs. El logger de errores HTTP registra solo el tipo de excepción y no se activa el access log de Uvicorn.

CORS permite orígenes concretos; no sustituye autenticación. Hasta la Misión 04 no existían escrituras HTTP; la Misión 05 agrega las de seeding (ver abajo). Los servicios API y web de producción se ejecutan sin root. PostgreSQL no publica ningún puerto en Compose. API y web solo se publican en loopback local.

El rol `smash_app` local tiene CONNECT, USAGE y SELECT/INSERT/UPDATE/DELETE sobre tablas creadas por el propietario; no tiene CREATE en public ni capacidades de administración. `smash_migrator` es exclusivamente el propietario de desarrollo. El bootstrap se ejecuta con el rol de aplicación. Producción requiere un migrador separado sin superusuario, propietario solo del esquema de la app, y un usuario limitado de aplicación; no usar `doadmin` para servir HTTP. El servicio de producción no recibe `MIGRATION_DATABASE_URL`. El job de migración la recibe solo cuando un operador aprueba la ejecución.

Los roles locales se crean en la primera inicialización del volumen. Cambiar `.env` no cambia las contraseñas existentes. En producción el operador prepara los roles y grants con herramientas seguras; no existe automatización que modifique la base administrada.

Riesgos pendientes para futuras misiones:

- Dos personas pueden compartir tag, y una persona puede tener varias cuentas. No fusionar identidades por tag; conservar procedencia y revisión humana.
- Un proveedor puede corregir resultados o recibir datos manipulados. Registrar sincronización, validar rosters/resultados y diseñar trazabilidad de cambios antes de publicar estadísticas.
- Autorización administrativa, auditoría inmutable, límites de peticiones y protección de acciones sensibles deberán implementarse antes de habilitar escrituras.
- Los aliases no se borran al cambiar un tag; sus intervalos deben mantenerse transaccionalmente por el futuro servicio de identidad.
- Backups, restauración verificada y política de retención/privacidad quedan a cargo del plan operativo de producción.

Usar Trusted Sources de DigitalOcean para permitir solo la aplicación y el acceso administrativo necesario. Mantener PostgreSQL fuera de ingress y nunca habilitar `0.0.0.0/0` como solución a fallos de conexión. Ver detalles de TLS y red en el runbook de despliegue.

## Controles de Misión 02

Parser con allowlist start.gg/www.start.gg y HTTPS, puerto 443 opcional, sin userinfo; nunca solicita la URL aportada. Endpoint GraphQL fijo y redirects deshabilitados. No se exponen cuerpos de error externos ni excepciones de almacenamiento en CLI/jobs. Los loggers httpx/httpcore están limitados a WARNING en configuración de aplicación. Los documentos no solicitan email, User ni información de contacto.

Las correcciones manuales requieren locks explícitos; una contradicción de identidad no fusiona por gamerTag. Jobs y resultados originales solo son accesibles al rol administrativo SQL, no a la API pública. No hay endpoints de importación ni claves frontend de autorización. La CLI rechaza production durante esta misión; ENVIRONMENT no sustituye la responsabilidad de verificar que DATABASE_URL apunte al entorno local autorizado.

## Misión 03

Cinco rutas nuevas son GET públicos de lectura; requieren UUID y parámetros tipados con rechazo de parámetros desconocidos, timestamps con offset, orden temporal válido y máximo 100 registros por página. Solo consideran torneos publicados. Respuestas incluyen identidad pública actual y resultados, sin payloads, IDs del proveedor ni ubicación/contacto del jugador. No hay llamadas de proveedor desde HTTP. Los links de fuente solo se construyen para start.gg con slug validado y esquema/dominio fijos. Los locks administrativos excluyen conservadoramente sets hasta revisión. La CLI de auditoría rechaza producción/hosts remotos y establece READ ONLY antes de consultar. No cambia CORS ni configuración de DigitalOcean.

## Misión 05: seeding

- Únicas rutas protegidas: `POST /seeding/{slug}/recalculate`, `PUT`/`DELETE /seeding/{slug}/overrides/{player_id}`, `GET /seeding/{slug}/audit` y `GET /seeding/{slug}/session`. Exigen `Authorization: Bearer <ADMIN_TOKEN>`; sin la variable responden 503. La clave tiene al menos 24 caracteres y se compara en tiempo constante. Tras 10 fallos en 10 minutos desde una IP se responde 429 (contador en memoria del proceso).
- CORS admite GET, POST, PUT y DELETE y las cabeceras `Authorization` y `X-Admin-Name`, solo para los orígenes configurados.
- La página guarda la clave en `sessionStorage` de la pestaña (se borra al cerrarla). `X-Admin-Name` se sanea y solo identifica el registro; no es autenticación.
- Toda escritura queda en `seeding_audit_entries` (acción, nombre, detalles, fecha). La aplicación no actualiza ni borra esas filas.
- La API solo *lee* start.gg (descarga de sets, una por proyecto a la vez, código de error seguro si falla). Escribir los seeds en start.gg requiere la CLI con `--confirm`.
- El seeding es público en lectura: tags, IDs de start.gg y resultados que ya son públicos en start.gg; no incluye ubicación ni contacto.
- Pendiente: cuentas individuales con roles, límite de peticiones compartido entre réplicas y rotación de la clave.

## Misión 06: importación web

`POST /imports/startgg` y `GET /imports/status` exigen la clave de admin. Solo aceptan links `https://start.gg` o `https://www.start.gg` (o slugs) y no siguen URLs aportadas. Cada torneo pasa por el importador transaccional con locks por torneo y por proveedor; los fallos se registran en `import_jobs` con códigos seguros. El token de start.gg se usa solo para leer.

## Misión 08: vista pública y borradores

- Los proyectos de seeding nacen como **borradores** (`published = false`). Sin clave, `GET /seeding` solo lista publicados y `GET /seeding/{slug}` de un borrador responde 404, como si no existiera.
- La respuesta pública trae solo el orden final y los mains (seeding), o puesto, mains, puntaje del método oficial, W-L y explicaciones (ranking). No incluye alertas, confianza, ratings internos, ajustes manuales, identidades, parámetros ni sugerencias.
- Con la clave (`Authorization`), las mismas rutas devuelven la vista completa. Una clave incorrecta responde 401, no la vista pública.
- `GET /seeding/{slug}/export.csv` exige la clave. `PUT /seeding/{slug}/publish` publica o despublica, y queda en el registro.
- La web tiene una sola sesión de organizador (`/admin`, enlace discreto en el pie). Sin sesión no muestra formularios ni herramientas.
