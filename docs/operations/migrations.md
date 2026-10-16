# Migraciones y rollback

Revisión inicial: `0001`, 19 tablas del dominio, índices, claves foráneas, checks y cinco constraint triggers diferidos de coherencia competitiva. El esquema Alembic añade su propia tabla `alembic_version`. La revisión está congelada; no usa `Base.metadata.create_all`.

Comandos locales:

```sh
docker compose run --rm api alembic current
docker compose run --rm api alembic upgrade head
docker compose run --rm api alembic check
```

Toda ejecución requiere `MIGRATION_DATABASE_URL` explícita. `DATABASE_URL` es para la aplicación. Se usa un bloqueo asesor transaccional para evitar dos migradores concurrentes. Alembic ejecuta DDL transaccional en PostgreSQL; una migración fallida debe revertir completa.

Para una nueva revisión: editar modelos, generar con `alembic revision --autogenerate -m "..."` en una base local al día y revisar manualmente el SQL. Alembic no detecta automáticamente las funciones ni triggers: deben incluirse y probarse explícitamente. Ejecutar aplicación, reversión y reaplicación en PostgreSQL efímero. No reescribir revisiones publicadas. Adoptar expand/contract para cambios futuros con datos.

`alembic downgrade base` de la revisión inicial elimina las 19 tablas y todos sus datos. Solo se ejecuta automáticamente en pruebas aisladas. No es una estrategia automática de rollback de producción. Si hay datos, preservar backup y preferir una corrección hacia adelante; restaurar en una base alternativa y verificar antes de promoverla.

El job preparado para App Platform está inactivo en un fragmento separado. Solo migra hasta `0001` con `APPROVED_MIGRATION=0001`; no usa `head` ni hace downgrade. Antes de incorporarlo: revisar revisión instalada, SQL, backup, ventana de mantenimiento, permisos y compatibilidad con la versión anterior. Proporcionar secreto del rol migrador por un canal privado. Retirar el fragmento tras el despliegue si no debe ejecutarse en despliegues posteriores. Nunca automatizar migraciones destructivas.

La suite comprueba aplicación, comparación del esquema con modelos, downgrade a base y reaplicación, además de constraints de FK/unique/check y triggers al commit. La guardia de tests solo admite `smashhub_test` en localhost/127.0.0.1/postgres.
