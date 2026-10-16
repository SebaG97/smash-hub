# Responsabilidades de módulos

| Módulo | Responsabilidad actual |
| --- | --- |
| core | Variables tipadas, validación de PostgreSQL/TLS/CORS, logging sin payloads |
| database | Base declarativa, engine, sesiones; registro de modelos y Alembic |
| health | Liveness, readiness consultando PostgreSQL y metadatos |
| communities | Países, regiones, comunidades, asociación con juegos y servicio de bootstrap |
| games | Catálogo de videojuegos y personajes por juego |
| players | Identidad persistente, tags no únicos, aliases históricos e identidades de proveedores |
| competitions | Torneos multijuego, participantes, eventos, entrants, rosters, sets y lados |
| integrations | Fuente, jobs, mapeos con FK y contratos de proveedores; sin importación real |
| rankings | Contrato de ámbito comunidad/juego/temporada/equipo; sin cálculos ni tablas de ranking |

`app.database.models` registra todas las tablas para herramientas; los modelos pertenecen a su módulo. La revisión Alembic no importa modelos actuales. Los módulos de dominio no exponen escrituras HTTP. Cada futura operación administrativa necesitará autorización, servicio transaccional y auditoría.

La web usa un layout accesible compartido, rutas por módulo y un componente cliente de estado con timeout, cancelación y reintento. Las páginas de módulos anuncian que no están implementadas. No hay datos competitivos simulados en la interfaz.
