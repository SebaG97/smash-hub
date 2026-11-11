# Reglamentos oficiales por torneo (Misión SH-RULES-01)

Fecha: 11 de noviembre de 2026. Estado: implementado. Primer documento: **Reglamento Oficial de Center Stage 2026, versión 1.0**, revisado por última vez el 1 de noviembre de 2026.

## Qué ve el visitante

- **Pestaña «Reglamento»** en la previa del torneo (`/previa/<slug>#reglamento`). Aparece **solo** si el torneo tiene un reglamento asociado. Muestra el nombre del documento, la versión, la fecha de última revisión, el botón «Leer el reglamento», «Abrir el PDF oficial» (pestaña nueva), «Descargar PDF» y el índice de capítulos. Si el torneo todavía no tiene evento o inscritos (y por eso no hay pestañas), el mismo bloque aparece debajo del aviso.
- **Lector web** en `/reglamentos/<id>`: el documento completo, transcrito palabra por palabra, con índice (columna fija en escritorio, arriba en celulares), anclas por capítulo y sección (`#glosario`, `#reglas-del-torneo`, `#escenarios`, `#regla-3-17`…) y una barra inferior en celulares con «Índice», «PDF oficial» y «↑ Arriba». Avisa que, ante cualquier diferencia, vale el PDF.
- **PDF oficial** servido tal cual desde `/reglamentos/<archivo>.pdf`.

Todo es público: no requiere sesión ni pasa por la API.

Center Stage 2026: `/previa/center-stage-2026-1#reglamento` o directamente `/reglamentos/center-stage-2026`.

## Arquitectura

Se eligió la opción más simple que encaja con la arquitectura actual: **archivo estático + configuración por torneo en el código de la web**. No hay tablas, migraciones, endpoints, almacenamiento externo ni dependencias nuevas. Un reglamento cambia cuando cambia el documento oficial, es decir, con muy poca frecuencia, y siempre lo publica la organización; un despliegue por versión es suficiente.

| Pieza | Ubicación |
| --- | --- |
| PDF oficial (sin modificar) | `apps/web/public/reglamentos/<id>-v<versión>.pdf` |
| Tipos y helpers (sin texto) | `apps/web/src/lib/rulebooks/types.ts` |
| Registro de reglamentos y asociación con torneos | `apps/web/src/lib/rulebooks/index.ts` (`RULEBOOKS`) |
| Transcripción de cada documento | `apps/web/src/lib/rulebooks/<id>.ts` |
| Pestaña y lector | `apps/web/src/components/rulebook.tsx` |
| Página del lector | `apps/web/src/app/reglamentos/[id]/page.tsx` |
| Pestaña en la previa | `apps/web/src/components/tournament-preview.tsx` (prop `rules`) |
| Estilos | `apps/web/src/app/globals.css`, sección `rulebooks` |
| Pruebas | `apps/web/tests/rulebooks.test.tsx` |

Flujo:

1. `app/previa/[slug]/page.tsx` (servidor) llama a `rulebookForTournament(slug)` y pasa a la previa un **resumen** (metadatos e índice, sin el texto). Así el texto del reglamento no entra en el bundle de la previa, que sigue cargando igual de rápido.
2. `app/reglamentos/[id]/page.tsx` (servidor) renderiza el documento completo como HTML. No hace llamadas a la API; solo depende del código.

Cada reglamento (`Rulebook`) declara: `id` (URL del lector), `title`, `version`, `revised` (AAAA-MM-DD), `pdf` (ruta pública), `filename` (nombre del archivo descargado), `pages`, `tournaments` (slugs de start.gg a los que aplica) y `chapters`.

El texto se modela como secciones anidadas (`number`, `title`, `blocks`, `sections`) con cuatro tipos de bloque: párrafo (`p`), lista (`list`), glosario (`terms`) y notas al pie con asteriscos (`notes`). Las secciones con `index: true` aparecen en el índice además de los capítulos, como hace el índice del propio documento con 3.23, 3.24 y 3.25. El ancla de cada sección es su `id` o, si no tiene, `regla-<número con guiones>`.

## Cómo asociar un reglamento a otro torneo

Si el mismo reglamento vale para otro torneo (por ejemplo, otra fecha del mismo circuito), basta con agregar el slug de start.gg a `tournaments`:

```ts
tournaments: ["center-stage-2026-1", "otro-torneo-2027"],
```

El slug es el de la URL de start.gg y de la previa: `start.gg/tournament/<slug>` → `/previa/<slug>`.

## Cómo agregar el reglamento de otro torneo

1. Copiar el PDF oficial, **sin modificarlo**, a `apps/web/public/reglamentos/<id>-v<versión>.pdf` (minúsculas y guiones, sin espacios).
2. Crear `apps/web/src/lib/rulebooks/<id>.ts` exportando un `Rulebook` (usar `center-stage-2026.ts` como modelo) con los metadatos y la transcripción. Para extraer el texto: `pdftotext -enc UTF-8 -layout archivo.pdf salida.txt` y unir las líneas cortadas. **No corregir, resumir ni reinterpretar**: se copian también las erratas.
3. Agregarlo a `RULEBOOKS` en `apps/web/src/lib/rulebooks/index.ts`.
4. Ejecutar `npm run test` (verifica que el PDF exista, que sea un PDF y que las anclas no se repitan), `npm run lint` y `npm run build` en `apps/web`.

Si no hay tiempo para transcribir, se puede publicar solo con el PDF: `chapters` con un único capítulo cuyo bloque remita al PDF. La pestaña, la apertura y la descarga funcionan igual. (Hoy el lector siempre muestra el índice; para un reglamento sin transcripción convendría ocultarlo.)

## Cómo publicar una nueva versión

1. Agregar el PDF nuevo con su versión en el nombre (`<id>-v1.1.pdf`). No sobrescribir el anterior: los enlaces ya compartidos al PDF viejo siguen funcionando y quedan cacheados con su nombre.
2. En `<id>.ts`, actualizar `version`, `revised`, `pdf`, `filename`, `pages` y el texto que cambió.
3. Si se quiere retirar la versión anterior, borrar su PDF en un commit aparte.
4. Pruebas, lint, build y despliegue normal de la web.

La URL del lector (`/reglamentos/<id>`) no cambia entre versiones.

## Limitaciones conocidas

- **Agregar o cambiar un reglamento requiere un despliegue.** No hay carga desde el panel de administración. Si algún día los organizadores necesitan publicarlos sin desarrolladores, el paso siguiente sería una tabla de documentos y almacenamiento de archivos; hoy no se justifica.
- **La transcripción es manual.** Se verificó palabra por palabra contra el texto extraído del PDF de Center Stage (3.525 palabras, sin diferencias), pero esa verificación no está automatizada en CI: el PDF manda.
- **Formato.** La versión web no reproduce negritas, sangrías ni la paginación del PDF; conserva numeración, títulos, listas y notas.
- **Numeración del documento de Center Stage.** El índice del PDF llama «5. Indemnización» al capítulo que en el cuerpo se titula «4. Indemnización». La web usa el número del cuerpo y no corrige nada más (por ejemplo, «del mismo del mismo» en 3.7 o «resultará se dará» en 3.24.2 se transcriben tal cual).
- **La pestaña depende de que cargue la previa.** Si start.gg o la API fallan, la previa muestra el error y la pestaña no aparece; el lector `/reglamentos/<id>` y el PDF siguen disponibles porque no dependen de la API.
- **El visor de PDF es el del navegador.** No hay PDF embebido: «Abrir el PDF oficial» lo abre en una pestaña nueva y, en navegadores que no muestran PDF (algunos Android), el sistema lo descarga o lo ofrece a otra aplicación. La lectura principal es la versión web, que no depende de eso.
- **El atributo `download`** puede ser ignorado por algunos navegadores de iOS, que muestran el PDF en vez de descargarlo; desde allí se guarda con «Compartir».
