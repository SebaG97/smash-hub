# Diseño visual

Notas de la pasada de rediseño hecha con la skill `frontend-design` (27/10/2026). Sirven para mantener la coherencia en los cambios futuros.

## Brief

Hub de la escena de Smash Ultimate en Paraguay (Smash Club Paraguay). Lo usan sobre todo jugadores, muchas veces desde el celular, para ver dónde está cada uno en el ranking, quién juega qué personaje y qué torneos hubo; también los organizadores. El cliente pidió usar los colores del logo y que el sitio no se viera "hecho con IA": nada de grillas de tarjetas ni degradés.

## Tokens

| Nombre | Hex | Uso |
| --- | --- | --- |
| Concreto | `#26221f` | Fondo (el gris cálido del logo, no un casi-negro) |
| Losa | `#302b27` | Superficies de herramientas y filas abiertas, con moderación |
| Hueso | `#efe9df` | Texto |
| Ceniza | `#a2988d` | Texto secundario, reglas de tabla |
| Fuego | `#e5541b` | Acciones, puestos 2 y 3, subrayados |
| Oro | `#f3a81f` | Solo el 1.º puesto y el foco de teclado |

Tipografía: *Big Shoulders Display* (700–900) para títulos, nombres en tablas y cifras; *Atkinson Hyperlegible* para el texto. Escala aproximada 1,25.

## Principios

- **Un solo elemento audaz:** los números de puesto, grandes e inclinados como en la pantalla de resultados del juego, junto a los íconos de stock de los mains. El resto, sobrio.
- **Listas y tablas, no tarjetas.** Filas separadas por reglas; las superficies `Losa` son solo para herramientas de organizadores.
- **Sin** degradés, brillos, sombras de color, etiquetas en mayúsculas sobre los títulos, flechas "↗" en los enlaces ni "01/02/03" decorativos. Los números solo aparecen donde son una secuencia real: puestos y seeds.
- La portada abre con lo más propio de la escena: el top 8 del ranking publicado y los últimos torneos.
- El texto en tono de usuario y en oraciones simples; los metadatos van como oraciones, no unidos con puntos medios.

## Íconos de personajes

`apps/web/public/characters/*.svg` son los íconos de stock de los 84 personajes de Smash Ultimate, en vectores a color de 200×200. Los aportó el responsable del proyecto el 27/10/2026, a partir de una colección de la comunidad sin licencia incluida. Son arte de Nintendo y se usan con fines comunitarios. Antes de copiarlos se limpiaron: sin declaración XML ni DOCTYPE, sin `id`, cifras a un decimal y `viewBox` agregado donde faltaba; se verificó que no tengan scripts ni enlaces externos. `src/lib/characters.ts` relaciona los nombres de start.gg con los archivos; algunos usan el nombre interno del juego (`gaogaen` = Incineroar, `homura` = Pyra & Mythra, `packun_flower` = Piranha Plant), y los tres Mii comparten `mii_fighter`. Si no hay ícono local (por ejemplo "Random Character"), se usa la imagen de start.gg.

## Pasada de color (Misión 11)

El color sale del propio juego: cada jugador toma el color característico de su main (`src/lib/character-colors.ts`, generado desde los SVG, con 16 elegidos a mano). Se usa en la franja de las filas del ranking y la portada, en el fondo teñido del 1.º y en la cabecera de la ficha. El W-L lleva una barra verde y roja; el menú marca la sección actual; la portada tiene un buscador de jugadores, y las páginas de ranking y seeding tienen enlace para volver.
