/*
 * DATOS DEL SET ACTUAL — se editan entre partidas.
 *
 * Cambiá nombres y marcadores, guardá, y en 2 segundos se actualizan
 * gameplay, versus e intermedio. No hace falta refrescar OBS.
 *
 * personaje: nombre de archivo de assets/images/personajes/ sin «.svg»
 *            (por ejemplo "mario", "pikachu", "cloud"). Vacío = sin personaje.
 * equipo:    prefijo de equipo. Vacío = sin prefijo.
 */
window.SH_PARTIDA = {
  ronda: "Winners Final",
  formato: "BO5", // "BO3" o "BO5"

  jugador1: { nombre: "Jugador 1", equipo: "", personaje: "", marcador: 0 },
  jugador2: { nombre: "Jugador 2", equipo: "", personaje: "", marcador: 0 },

  // Lo que muestra «Volvemos enseguida» como siguiente set.
  siguiente: {
    ronda: "Losers Semifinal",
    jugador1: "Jugador 3",
    jugador2: "Jugador 4",
  },

  // Elementos del gameplay que se pueden apagar.
  mostrar: {
    marca: true, // logo y nombre del evento abajo a la izquierda
    patrocinadores: true, // patrocinadores rotando abajo a la derecha
  },
};
