/*
 * DATOS DEL EVENTO — se editan una vez por transmisión.
 *
 * Cómo editar: cambiá solo lo que está entre comillas y guardá el archivo.
 * Los overlays abiertos en OBS releen este archivo cada 2 segundos.
 * Todo lo marcado con «REEMPLAZAR» es un ejemplo o un placeholder.
 */
window.SH_EVENTO = {
  // Perfil de evento: "" = Smash Hub, "center-stage" = Center Stage completo
  // (colores, logos, auspiciantes y textos de config/perfiles/center-stage.js).
  perfil: "",

  // Tournament Stream Helper: true = jugadores, marcador, ronda, comentaristas y Top 8
  // salen de TSH (el paquete tiene que estar dentro de TSH/layout/). Ver README.
  // Equivale a agregar ?tsh=1 a la URL, y sirve también con «Archivo local» en OBS.
  tsh: false,
  scoreboard: "1", // número de marcador de TSH
  diagnostico: true, // aviso rojo en pantalla si TSH está activado y no se encuentran datos
  // Bracket en tiempo real: cada cuántos segundos bracket.html le pide a TSH que vuelva
  // a traer el bracket de start.gg (0 = nunca; TSH solo lo trae al elegir la fase).
  actualizarBracket: 0,
  tshServidor: "http://127.0.0.1:5500", // servidor web de TSH (puerto 5500 por defecto)

  // Tema visual si no hay perfil: "smash-hub" o "center-stage".
  tema: "smash-hub",

  organizacion: "Smash Club Paraguay",
  evento: "Torneo semanal", // REEMPLAZAR: nombre del torneo
  fecha: "Sábado 14 de noviembre", // REEMPLAZAR
  hora: "15:00", // REEMPLAZAR
  lugar: "Asunción, Paraguay", // REEMPLAZAR

  // Cuenta regresiva de «Empezamos pronto». Vacío = no se muestra.
  // Formato: "2026-11-14T15:00:00-03:00"
  inicio: "",

  sitio: "tu-sitio.com.py", // REEMPLAZAR: sitio web
  redes: [
    // REEMPLAZAR: hasta 3 redes. Se muestran como «Red · usuario».
    { red: "Instagram", usuario: "@tu_cuenta" },
    { red: "Discord", usuario: "tu-servidor" },
    { red: "start.gg", usuario: "tu-organizacion" },
  ],

  // Logos. Rutas relativas a la carpeta obs-overlays/.
  logoClub: "assets/images/marca/smash-club-paraguay-circular.png",
  // Logo del torneo. Vacío = no se muestra.
  logoEvento: "",
  // Versión horizontal del logo del torneo, para encabezados. Vacío = no se usa.
  logoEventoHorizontal: "",

  patrocinadores: {
    // REEMPLAZAR: logos con fondo transparente (PNG o SVG).
    principal: {
      nombre: "Patrocinador principal",
      logo: "assets/images/patrocinadores/placeholder-principal.svg",
    },
    secundarios: [
      { nombre: "Patrocinador 1", logo: "assets/images/patrocinadores/placeholder-1.svg" },
      { nombre: "Patrocinador 2", logo: "assets/images/patrocinadores/placeholder-2.svg" },
      { nombre: "Patrocinador 3", logo: "assets/images/patrocinadores/placeholder-3.svg" },
      { nombre: "Patrocinador 4", logo: "assets/images/patrocinadores/placeholder-4.svg" },
    ],
  },

  comentaristas: [
    { nombre: "Comentarista 1", usuario: "@usuario" }, // REEMPLAZAR
    { nombre: "Comentarista 2", usuario: "@usuario" }, // REEMPLAZAR
  ],

  textos: {
    empezamos: ["Empezamos", "pronto"],
    volvemos: ["Volvemos", "enseguida"],
    comentarios: "En la cabina",
    patrocinadores: "Gracias a quienes hacen posible este torneo",
    proximoSet: "Próximo set",
    mesa: ["Mesa de", "análisis"], // commentators-wide
    cierre: ["Gracias", "por ver"], // ending
    cierreEtiqueta: "Hasta el próximo torneo", // ending
    lema: "", // frase corta del evento (pie del gameplay con cámaras y cierre)
  },

  // Mensajes de la cinta inferior de «Volvemos enseguida».
  mensajes: [
    "Resultados, rankings y brackets en el sitio del club", // REEMPLAZAR
    "Seguinos en redes para enterarte del próximo torneo",
    "¿Querés jugar? Inscribite en start.gg",
  ],
};
