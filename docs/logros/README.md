# Logros de Smash Hub — SH-ACH-01A

Fecha: 12/11/2026. Estado: **implementado en la rama local `sh-ach-01` (SH-ACH-01), pendiente de autorización para publicar.** Sin push ni despliegue. Implementación, logros activos y pasos de publicación: [operations/sh-ach-01.md](../operations/sh-ach-01.md). Decisión técnica: [ADR-023](../adr/ADR-023.md).

| Documento | Contenido |
| --- | --- |
| [Inventario inicial (SH-ACH-01)](../operations/sh-ach-01-inventario.md) | Los 25 logros existentes, hallazgos de compatibilidad y glosario paraguayo por nivel de certeza. |
| [catalogo.md](catalogo.md) | Los 25 existentes con categoría y rareza, 84 nuevos (109 en total), viabilidad, prioridad y primera tanda. |
| [diseno.md](diseno.md) | Revisión técnica, rarezas y porcentajes, persistencia y recálculo, experiencia de usuario, identidad, migraciones y rendimiento. |

## Resumen ejecutivo

1. **Ya hay dos sistemas, y se integran en lugar de reemplazarse.** Los 12 logros del Prode (guardados por cuenta) y los 13 emblemas (calculados al vuelo por jugador) conservan su identificador, nombre y condición. Se los une con un catálogo único en el código, una API y los mismos componentes. El Prode mantiene su tabla, y los logros de jugador ganan una tabla propia con historial.
2. **El problema más serio es de historial, no de catálogo.** El Prode borra y recrea sus logros al liquidar, así que pierde la fecha original, y los emblemas no tienen fecha alguna. El diseño pasa a un recálculo por diferencias: nunca borra, revoca con motivo y nunca reescribe la fecha de reconocimiento. Separa la fecha real del hecho de la fecha en que Smash Hub lo reconoció.
3. **El catálogo llega a 109 logros sin relleno** (25 existentes + 84 nuevos) en 8 categorías. **69 de los nuevos son calculables hoy** con datos que ya están en la base; 8 esperan un dato que falta (pools históricos, serie de torneos, organizador, color de Yoshi); 4 son manuales y 3 necesitan validación de la comunidad.
4. **Primera tanda recomendada: 28 logros** con datos completos y fiables, más 2 del Régimen de Spike si se aprueba su consentimiento y su identificación.
5. **Los datos tienen límites claros.** No hay colores por partida (vBash rojo queda como futuro o especial); los personajes solo existen cuando se reportaron; los pools solo desde SH-SYNC-01; la ciudad del torneo puede faltar. Esos logros se marcan «datos desde» y no muestran porcentajes engañosos.
6. **Spike y vBash se identifican por ID de start.gg, nunca por nametag,** mediante una tabla de «personas de referencia» que carga un superadmin. **Sin su consentimiento registrado, sus colecciones no se activan.**
7. **Hay dos rarezas.** La de diseño (común → legendario) es fija. La estadística muestra porcentaje y cantidad sobre un universo elegible definido por logro. Con menos de 30 elegibles, o con datos incompletos, se muestra solo la cantidad. «Nadie todavía» reemplaza al 0 %.
8. **El humor es opcional para quien lo recibe.** Los logros que se burlan («Nerfeado por la trama», «Los Johns», «No pasar pools», «Mufa confirmada») son públicos por defecto (decisión aprobada) y su dueño puede ocultar cada uno.
9. **La vitrina de 3 logros la elige el usuario,** no un administrador. Sin elección, se muestran automáticamente los 3 más raros, con esa leyenda.
10. **Costo controlado.** Se evalúa en segundo plano, después de importar, sincronizar, publicar un ranking o liquidar un Prode, en una pasada en memoria. Las visitas solo leen filas y no hay ninguna consulta a start.gg por visita.

## Sobre el lore

- **Aportado por la organización en esta misión:** Multiverso de vBash, Régimen de Spike, «Casi, kp», «La mufa no funciona», «En bici hasta CDE», «Nerfeado por la trama», «No pasar pools», «Los Johns», rivalidades y seeding. Se usan como memes confirmados (origen **MC**), pero las condiciones concretas de cada logro son propuestas creativas.
- **No verificado:** sigo sin poder confirmar qué significa «kp» fuera de la frase «Casi, kp». «Nde ru» y «bVash» quedan pendientes de la comunidad.
- No se atribuyen frases a personas ni se incluyen mensajes ni datos de contacto.

## Decisiones aprobadas (SH-ACH-01B y SH-ACH-01)

- El catálogo de 109 es la base de diseño, no una autorización para activar todos. Se activaron los 28 de la primera tanda y los de segunda tanda con datos fiables. Los que dependen de datos inexistentes o de validación quedan registrados como pendientes.
- **Humor:** los logros de humor son **públicos por defecto** y el dueño puede ocultar cada uno. Esto reemplaza la propuesta D3 de abajo.
- Los logros permanentes conservan su primer desbloqueo; alcanzar otro nivel no quita el anterior.
- «Por la puerta de atrás» exige el recorrido real por losers; «Golpe de Estado», la eliminación real de Spike; «Casi, kp», la gran final decisiva.
- Las colecciones de Spike y vBash quedan preparadas y no se activan sin identidad (ID de start.gg) y consentimiento.
- Porcentajes sobre universos elegibles, sin consultas a start.gg por visita.

## Decisiones que requerían aprobación (propuesta original de SH-ACH-01A)

| # | Decisión | Recomendación |
| --- | --- | --- |
| D1 | Aprobar el catálogo: quitar, renombrar o ajustar umbrales de cada logro. | Revisar en especial los nombres en guaraní del nivel B. |
| D2 | **Spike y vBash:** confirmar con ellos que están de acuerdo, y su ID de jugador de start.gg. | Sin consentimiento no se activan sus colecciones. |
| D3 | Política de humor: los logros marcados «h» son públicos solo si su dueño lo elige. | Aprobar así. |
| D4 | Persistencia: tabla `player_achievements` + columnas aditivas en `prode_achievements` (migración `0024`). | Aprobar. |
| D5 | Prode: pasar de «borrar y recrear» a recálculo por diferencias, y revocar en lugar de borrar al anular. | Aprobar antes de liquidar Center Stage, si los tiempos lo permiten; si no, los logros de ese Prode se conservan igual al migrar. |
| D6 | Umbrales estadísticos: mínimo de 30 elegibles y cortes de 1/5/20/50 %. | Aprobar y revisarlos tras la primera tanda. |
| D7 | Primera tanda: 28 logros (+2 de Spike con D2). | Aprobar y calibrar con datos reales antes de lanzar. |
| D8 | Logros manuales: quién otorga («Por Decreto Supremo», «El Dictador ha Hablado», «El verdadero vBash», «Anfitrión»). | Solo administradores, con motivo público y auditoría. |
| D9 | Carga retroactiva: otorgar el historial completo, marcado «reconocido retroactivamente». | Aprobar. |
| D10 | Convención de IDs: español para jugador y comunidad, inglés para el Prode. | Aprobar (respeta lo existente). |
| D11 | Datos futuros: serie de torneos y organizador del torneo. | Decidir más adelante; solo destraban logros T3. |

SH-ACH-01B y SH-ACH-01C no se implementaron.
