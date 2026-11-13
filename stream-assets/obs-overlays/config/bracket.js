/*
 * TOP 8 — doble eliminación. Lo usa bracket.html.
 *
 * Por cada set: j1 / j2 = jugadores, p1 / p2 = sets ganados.
 * Nombre vacío = «Por definir». Puntos vacíos = todavía no se jugó.
 * Cuando alguien llega a las victorias del formato (3 en BO5), ese set
 * queda terminado: el ganador se resalta y su línea se enciende.
 * El bracket NO avanza solo: escribí el ganador en el set siguiente.
 * Guardá y en 2 segundos se actualiza en OBS.
 */
window.SH_BRACKET = {
  titulo: "Top 8",
  formato: "BO5", // formato de todos los sets del Top 8
  formatoFinal: "BO5", // Grand Final (y reset)

  // Set que se está jugando ahora (se marca «En juego»). Vacío = ninguno.
  // Valores: WSF1, WSF2, WF, LR1A, LR1B, LQFA, LQFB, LSF, LF, GF, RESET
  enJuego: "",

  // true muestra el reset de Grand Final aunque todavía esté vacío.
  reset: false,

  cruces: {
    // Winners
    WSF1: { j1: "", p1: "", j2: "", p2: "" }, // Winners Semifinal 1
    WSF2: { j1: "", p1: "", j2: "", p2: "" }, // Winners Semifinal 2
    WF: { j1: "", p1: "", j2: "", p2: "" }, // Winners Final
    // Losers
    LR1A: { j1: "", p1: "", j2: "", p2: "" }, // Losers Round 1 (A)
    LR1B: { j1: "", p1: "", j2: "", p2: "" }, // Losers Round 1 (B)
    LQFA: { j1: "", p1: "", j2: "", p2: "" }, // Losers Quarterfinal (A)
    LQFB: { j1: "", p1: "", j2: "", p2: "" }, // Losers Quarterfinal (B)
    LSF: { j1: "", p1: "", j2: "", p2: "" }, // Losers Semifinal
    LF: { j1: "", p1: "", j2: "", p2: "" }, // Losers Final
    // Final
    GF: { j1: "", p1: "", j2: "", p2: "" }, // Grand Final (j1 = viene de winners)
    RESET: { j1: "", p1: "", j2: "", p2: "" }, // Grand Final reset (si hace falta)
  },
};
