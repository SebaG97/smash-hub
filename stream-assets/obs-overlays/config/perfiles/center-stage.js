/*
 * PERFIL CENTER STAGE
 *
 * Se activa con  perfil: "center-stage"  en config/evento.js.
 * Lo que está acá reemplaza lo de evento.js; lo que no está, se toma de evento.js
 * (fecha, hora, lugar, redes, sitio, comentaristas…).
 *
 * Identidad: logos oficiales y auspiciantes del pack CENTER-STAGE-OBS-PACK.
 * Paleta en assets/css/temas/center-stage.css.
 */
window.SH_PERFIL = {
  tema: "center-stage",
  evento: "Center Stage",

  // Logos oficiales (fondo negro quitado; los JPEG originales están en originales/).
  logoEvento: "assets/images/eventos/center-stage/logo.png",
  logoEventoHorizontal: "assets/images/eventos/center-stage/logo-horizontal.png",

  patrocinadores: {
    // Sin principal: los once se muestran con el mismo peso. Para destacar uno,
    // poné aquí { nombre: "...", logo: "..." } y sacalo de la lista.
    principal: null,
    secundarios: [
      { nombre: "PlayStation", logo: "assets/images/patrocinadores/center-stage/1.png" },
      { nombre: "Game Over Burgers", logo: "assets/images/patrocinadores/center-stage/2.png" },
      { nombre: "Food Dojo", logo: "assets/images/patrocinadores/center-stage/3.png" },
      { nombre: "Katerina & Co Bakery", logo: "assets/images/patrocinadores/center-stage/4.png" },
      { nombre: "Globalbox", logo: "assets/images/patrocinadores/center-stage/5.png" },
      { nombre: "Pulso Gamer", logo: "assets/images/patrocinadores/center-stage/6.png" },
      { nombre: "Heineken", logo: "assets/images/patrocinadores/center-stage/7.png" },
      { nombre: "EON", logo: "assets/images/patrocinadores/center-stage/8.png" },
      // Azul oscuro: sobre fondo oscuro no se lee, así que va sobre una placa clara con sus
      // colores originales (como en el pack v3). Alternativa: estilo: "blanco".
      { nombre: "Santa Bárbara", logo: "assets/images/patrocinadores/center-stage/9.png", estilo: "placa" },
      { nombre: "Apocalypse Boutique", logo: "assets/images/patrocinadores/center-stage/10.png" },
      { nombre: "Performance Corporation", logo: "assets/images/patrocinadores/center-stage/11.png" },
    ],
  },

  textos: {
    empezamos: ["Empieza", "pronto"],
    volvemos: ["Ya", "volvemos"],
    comentarios: "En la cabina",
    patrocinadores: "Auspician",
    proximoSet: "Próximo set",
    mesa: ["Mesa de", "análisis"],
    cierre: ["Nos vemos", "en stage"],
    cierreEtiqueta: "Gracias por ser parte",
    lema: "El escenario es tuyo",
  },

  mensajes: [
    "Center Stage · Super Smash Bros. Ultimate · Paraguay",
    "El escenario es tuyo",
    "Gracias a todos los auspiciantes que hacen posible Center Stage",
  ],
};
