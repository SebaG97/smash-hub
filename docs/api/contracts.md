# Contratos iniciales

Base: `/api/v1`. JSON UTF-8. Versión de aplicación `0.1.0`. Sin autenticación en estas rutas públicas de lectura; no existe ninguna escritura pública.

| Método y ruta | Éxito | Error previsto |
| --- | --- | --- |
| GET /health/live | 200 `{"status":"alive"}` | Independiente de PostgreSQL |
| GET /health/ready | 200 `{"status":"ready"}` | 503 `{"status":"unavailable"}` |
| GET /meta | 200, estructura debajo | 500 genérico ante fallo inesperado |

```json
{"name":"Smash PY Hub","version":"0.1.0","api_version":"v1","capabilities":["health","metadata"]}
```

Readiness ejecuta `SELECT 1` con timeout de conexión de 3 segundos y statement timeout de 5 segundos. Confirma conectividad, no estado de migración ni disponibilidad de proveedores. Consultar Alembic para comprobar revisión instalada. Liveness no usa ningún servicio externo.

OpenAPI se genera en `/api/openapi.json`; Swagger UI en `/api/docs` y ReDoc en `/api/redoc`. Los esquemas de respuesta están declarados con Pydantic. [Snapshot del contrato](openapi.json) generado desde la factory y verificado por tests.

Fallos inesperados devuelven `{"detail":"Internal server error"}` sin traceback. CORS acepta únicamente los orígenes explícitos configurados y GET. La API no acepta tokens de start.gg en esta fase.

Los contratos internos `ExternalReference` y `CompetitionProvider` reservan referencia de proveedor, fecha de sincronización y consulta de torneos. `RankingScope` y `RankingCalculator` reservan el ámbito competitivo sin implementar Glicko-2. No son endpoints disponibles.
