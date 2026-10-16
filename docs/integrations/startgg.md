# Integración start.gg

La CLI consulta exclusivamente `https://api.start.gg/gql/alpha` con HTTPX asíncrono y `STARTGG_API_TOKEN` Bearer. La variable es opcional para arrancar web/API. Sin token, la CLI devuelve `startgg_token_missing`; no hay endpoints de escritura. El token nunca se envía a Next.js ni se guarda en PostgreSQL.

## Documentos GraphQL

En `apps/api/app/integrations/startgg/graphql/`, versionados separadamente:

| Documento | Selección y alcance |
| --- | --- |
| tournament.graphql | ID, nombre, slug, fechas, estado, ciudad/país y referencias a eventos |
| event.graphql | Juego, tipo estructurado, roster, estado y cantidad de entrants |
| participants.graphql | Participantes paginados con tag histórico y Player.id nullable |
| entrants.graphql | Entrants paginados, seed inicial e integrantes individuales |
| standings.graphql | Standings paginados, placement, isFinal y entrant |
| sets.graphql | Sets paginados, estado, ronda, fecha, revisión, ganador y scores por lado |

Se revisaron campos, argumentos y tipos contra la [referencia oficial Event](https://developer.start.gg/reference/event.doc.html), [Tournament](https://developer.start.gg/reference/tournament.doc.html), [Entrant](https://developer.start.gg/reference/entrant.doc.html), [Participant](https://developer.start.gg/reference/participant.doc.html), TeamRosterSize y SetFilters enlazados desde esa referencia el 16/10/2026. La referencia oficial redirige a `smashgg-schema.netlify.app/reference/`. Tournament.state es entero; Event.state es enum. Se contrastaron conexiones con los ejemplos oficiales de [entrants](https://developer.start.gg/docs/examples/queries/event-entrants/), [standings](https://developer.start.gg/docs/examples/queries/event-standings/), [sets](https://developer.start.gg/docs/examples/queries/sets-in-event/) y [scores](https://developer.start.gg/docs/examples/queries/set-score/).

Validación documental realizada; no se afirma introspección completa del esquema actual. Los seis documentos se ejecutaron autenticados en la validación real de los tres torneos, sin errores GraphQL. El test HTTP usa los documentos reales y fixtures representativos, no un token real.

## Límites y errores

La documentación oficial fija [80 solicitudes por 60 segundos y 1000 objetos por consulta](https://developer.start.gg/docs/rate-limits/). El cliente espacia solicitudes a un segundo y pagina en lotes de diez, sin anidar juegos de sets. Un bloqueo PostgreSQL serializa las importaciones persistentes del proveedor en esta base. Ejecutar previews de uno en uno y no compartir el token con otros procesos: el límite pertenece al token, no a esta instalación. No hay worker ni scheduler.

Timeout de conexión 5 s y operaciones 30 s; hasta cuatro intentos ante transporte, HTTP 429/5xx o rate limit del proveedor, con backoff exponencial y jitter. No sigue redirects. Errores HTTP permanentes, JSON inválido y GraphQL (incluso data parcial junto con errors) abortan con códigos fijos. No se imprimen mensajes ni cuerpos externos. Cada conexión exige pageInfo consistente, IDs únicos y total exacto; páginas vacías prematuras, duplicadas o cambiantes fallan. Máximo 10000 páginas. La lista de eventos no tiene conexión paginada: se pide un máximo de 500 referencias y se rechaza el caso que alcance ese límite, para no asumir completitud.

## Identidades y datos ausentes

`player:<Player.id>` es identidad global verificada por la fuente, no una verificación civil de la persona. Participant.id solo identifica una inscripción histórica, almacenada con ámbito de torneo. Sin Player.id se crea una identidad interna provisional exclusiva de esa inscripción; nunca se compara gamerTag para fusionar. Conflictos de identidad abortan y quedan registrados en import_jobs.

Roster estructurado fijo min=max; type=1 permite singles sin roster. Equipos variables o tipo desconocido sin roster fallan explícitamente. No se infiere modalidad por el nombre. Solo standings con isFinal=true producen placement final. No se solicitan email, nombre legal, direcciones, contactos, perfiles de usuario ni personajes.

Un score ausente o un resultado ambiguo se conserva sin inventarlo, como incomplete. DQ requiere etiqueta DQ y marcador -1 de la misma respuesta; BYE requiere etiqueta BYE, estado final y un único entrant ganador. Si falta esa evidencia se mantiene incomplete, con el resultado original para revisión. Estas convenciones conservadoras se contrastaron con los DQ y BYE reales de los torneos autorizados; la referencia pública no garantiza marcadores uniformes para todos los juegos. DQ doble y modalidades con más de dos lados no se normalizan como partidas jugadas. completedAt puede faltar y queda null. ranking_eligible solo señala un candidato con victoria jugada, scores válidos y fecha; no calcula ranking.

No existe snapshot consistente entre páginas en start.gg. Se detectan cambios de totales y referencias rotas, pero modificaciones que preserven esos totales pueden requerir una nueva sincronización. Los torneos grandes se descargan en memoria en esta etapa.

## Alcance de validación confirmado

Los casos reales autorizados son `gg-fest-x-eon`, `game-over-sep` y `super-smash-burgame-7`, exclusivamente singles según el responsable. Ver [plan y matriz de evidencia](../operations/mission-02-validation-plan.md). La identidad compartida entre esos torneos, sus entrants/placements/sets y su reimportación se validaron contra el proveedor; la matriz registra los resultados reales. Dobles se valida con fixtures sintéticos; no se exige un torneo real de dobles para aprobar esta misión y el modelo sigue admitiéndolo. No se sustituyen ni inventan resultados reales.

## Misión 02.1 — Auditoría de bracket

sets.graphql solicita round, startedAt, hasPlaceholder, phaseGroup(id/bracketType) y slotIndex/prereqId/prereqType/prereqPlacement, además de los datos originales de resultado. Son campos de bracket de la referencia oficial, no datos de contacto. La consulta normal usa $showByes=true por defecto y hideEmpty=false; el documento permite $showByes=false para diagnóstico; una segunda conexión con state:[5] recupera sets INVALID omitidos por defecto. Ambas se paginan y validan completamente; la unión conserva IDs únicos y rechaza respuestas contradictorias para el mismo ID.

La auditoría comparó showByes=true/false: el segundo también excluye posiciones vacías con slots bye, mientras conserva DQ. No usar ese filtro para decidir por sí solo si un set fue jugado. La clasificación usa evidencia de slots y dependencias, no la finalización del torneo ni el nombre de la ronda por sí solos. Ver ADR-009 y el informe mission-02-1-report.
