/*
 * Smash Hub · overlays para OBS.
 * Carga config/evento.js y config/partida.js, completa la escena y los vuelve
 * a leer cada 2 segundos. No hay que tocar este archivo para usar los overlays.
 *
 * Parámetros opcionales en la URL (tienen prioridad sobre config/):
 *   ?p1=Nombre&p2=Nombre&s1=1&s2=0&e1=Equipo&e2=Equipo&c1=mario&c2=fox
 *   &ronda=Grand%20Final&formato=BO5&tema=center-stage&evento=Center%20Stage
 *   &logoEvento=assets/images/eventos/center-stage/logo.png&inicio=2026-11-14T15:00:00-03:00
 *   &perfil=center-stage&bracket=previews/datos/bracket-ejemplo.js
 */
(function () {
  "use strict";

  var script = document.currentScript;
  var ROOT = script.src.replace(/assets\/js\/overlay\.js.*$/, "");
  var INTERVALO = 2000;
  var ultimo = "";

  // ------------------------------------------------------------------ carga
  function cargar(ruta) {
    return new Promise(function (ok) {
      var s = document.createElement("script");
      s.src = ROOT + ruta + "?v=" + Date.now();
      s.onload = s.onerror = function () {
        s.remove();
        ok();
      };
      document.head.appendChild(s);
    });
  }

  function leerDatos() {
    // ?bracket=ruta/otro.js carga otro archivo de bracket (lo usan las capturas de ejemplo).
    var qb = new URLSearchParams(location.search).get("bracket") || "";
    var rutaBracket = /^[\w\/-]+\.js$/.test(qb) ? qb : "config/bracket.js";
    var archivos = [cargar("config/evento.js"), cargar("config/partida.js"), cargar(rutaBracket)];
    return Promise.all(archivos).then(function () {
      var evento = clonar(window.SH_EVENTO || {});
      // Perfil: config/perfiles/<perfil>.js pisa los datos de evento.js (logos, colores, auspiciantes…).
      var q = new URLSearchParams(location.search);
      var perfil = q.has("perfil") ? q.get("perfil") : evento.perfil;
      window.SH_PERFIL = null;
      var conPerfil = /^[a-z0-9-]+$/.test(perfil || "") ? cargar("config/perfiles/" + perfil + ".js") : Promise.resolve();
      return conPerfil.then(function () {
        if (window.SH_PERFIL) evento = mezclar(evento, clonar(window.SH_PERFIL));
        var d = {
          evento: evento,
          partida: clonar(window.SH_PARTIDA || {}),
          bracket: clonar(window.SH_BRACKET || {}),
        };
        // TSH se activa con ?tsh=1 en la URL o con  tsh: true  en config/evento.js
        // (esto último sirve para OBS con «Archivo local», donde no se puede agregar ?tsh=1).
        TSH.estado.activo = TSH.forzado || d.evento.tsh === true;
        if (!TSH.estado.activo) {
          aplicarUrl(d.evento, d.partida);
          return d;
        }
        // Modo TSH: los datos de competencia vienen de Tournament Stream Helper.
        return leerTsh()
          .then(function (estado) {
            TSH.ultimo = estado;
            TSH.estado.ok = true;
            TSH.estado.error = "";
            TSH.estado.leido = new Date().toISOString();
          })
          .catch(function (e) {
            TSH.estado.ok = false;
            TSH.estado.error = String((e && e.message) || e);
          })
          .then(function () {
            if (TSH.ultimo) {
              try {
                aplicarTsh(TSH.ultimo, d);
              } catch (e) {
                TSH.estado.ok = false;
                TSH.estado.error = String(e.message || e);
              }
            }
            aplicarUrl(d.evento, d.partida);
            return d;
          });
      });
    });
  }

  function clonar(o) {
    return JSON.parse(JSON.stringify(o));
  }

  // ------------------------------------------------------------------ Tournament Stream Helper
  // Lee el estado de TSH y lo usa para jugadores, prefijos, personajes, marcador,
  // ronda, formato, comentaristas y Top 8. Solo lee: no escribe en TSH ni en start.gg.
  // Se activa con ?tsh=1 en la URL o con  tsh: true  en config/evento.js.
  // Si la lectura falla, se conserva el último dato recibido.
  // Estado de la lectura: window.SH_TSH en la consola del navegador.
  //   ?scoreboardNumber=2   otro marcador de TSH (por defecto, el 1; también scoreboard: en evento.js)
  //   ?tshRuta=ruta.json    ubicación exacta del estado, si no se encuentra sola
  // Dónde busca, en orden:
  //   1. http://<servidor de TSH>/program-state        (servidor web de TSH, puerto 5500 por defecto)
  //   2. ../../out/program_state.json                   (paquete en TSH/layout/<carpeta>/)
  //   3. ../out/program_state.json y ../../../out/…     (una carpeta de más o de menos)
  var Q = new URLSearchParams(location.search);
  var INICIO = Date.now();
  var TSH = {
    forzado: Q.get("tsh") === "1",
    tablero: Q.get("scoreboardNumber") || "",
    ruta: /\.json$/i.test(Q.get("tshRuta") || "") ? Q.get("tshRuta") : "",
    fuente: "",
    ultimo: null,
    estado: { activo: false, ok: false, error: "sin leer todavía", bracket: false, leido: "", fuente: "" },
  };
  window.SH_TSH = TSH.estado;

  function candidatosTsh() {
    if (TSH.ruta) return [/^(https?:|file:|\/)/.test(TSH.ruta) ? TSH.ruta : ROOT + TSH.ruta];
    var http = /^https?:$/.test(location.protocol);
    var c = [];
    if (TSH.fuente) c.push(TSH.fuente);
    if (http) c.push(location.origin + "/program-state");
    c.push(ROOT + "../../out/program_state.json", ROOT + "../out/program_state.json", ROOT + "../../../out/program_state.json");
    if (http) c.push(location.origin + "/out/program_state.json");
    return c.filter(function (u, i) {
      return c.indexOf(u) === i;
    });
  }

  /** Prueba las ubicaciones posibles hasta encontrar un estado de TSH con marcador. */
  function leerTsh() {
    var urls = candidatosTsh();
    var errores = [];
    var i = 0;
    var intentar = function () {
      if (i >= urls.length) return Promise.reject(new Error(errores.join(" | ")));
      var url = urls[i++];
      return leerJson(url + (url.indexOf("?") < 0 ? "?" : "&") + "v=" + Date.now())
        .then(function (j) {
          // /program-state del servidor de TSH devuelve { state: {...}, delta_index }
          var e = j && j.state && !j.score ? j.state : j;
          if (!e || !e.score) throw new Error(url + ": no tiene datos de marcador");
          TSH.fuente = url;
          TSH.estado.fuente = url;
          return e;
        })
        .catch(function (err) {
          errores.push(err.message || String(err));
          return intentar();
        });
    };
    return intentar();
  }

  /** Aviso en pantalla mientras TSH está activado pero no se pudo leer nada. */
  function avisoTsh(d) {
    var n = document.getElementById("sh-aviso-tsh");
    var mostrar =
      TSH.estado.activo && !TSH.estado.ok && d.evento.diagnostico !== false && Date.now() - INICIO > 4000;
    if (!mostrar) {
      if (n) n.remove();
      return;
    }
    if (!n) {
      n = document.createElement("div");
      n.id = "sh-aviso-tsh";
      n.style.cssText =
        "position:fixed;left:12px;top:12px;z-index:99;max-width:900px;padding:10px 14px;" +
        "background:#b3122e;color:#fff;font:700 15px/1.35 Verdana,sans-serif;border-radius:4px;" +
        "box-shadow:0 6px 20px rgba(0,0,0,.5)";
      document.body.append(n);
    }
    n.textContent =
      "TSH: no se encuentran los datos. ¿Está abierto TSH? ¿La carpeta está dentro de TSH/layout/? " +
      "Detalle: " +
      TSH.estado.error.slice(0, 260);
  }

  /** Lee un JSON por XHR: funciona por http (servidor de TSH) y en archivos locales de OBS. */
  function leerJson(url) {
    return new Promise(function (ok, mal) {
      var x = new XMLHttpRequest();
      x.open("GET", url, true);
      x.onload = function () {
        if (x.status === 200 || (x.status === 0 && x.responseText)) {
          try {
            ok(JSON.parse(x.responseText));
          } catch (e) {
            mal(new Error("program_state.json no es un JSON válido"));
          }
        } else mal(new Error("no se pudo leer " + url + " (HTTP " + x.status + ")"));
      };
      x.onerror = function () {
        mal(new Error("no se pudo leer " + url));
      };
      x.send();
    });
  }

  function lista(o) {
    if (!o || typeof o !== "object") return [];
    return Object.keys(o)
      .sort(function (a, b) {
        return Number(a) - Number(b);
      })
      .map(function (k) {
        return o[k];
      });
  }

  function nombreTsh(equipo) {
    if (!equipo) return "";
    if (equipo.teamName) return equipo.teamName;
    return lista(equipo.player)
      .map(function (p) {
        return p && p.name;
      })
      .filter(Boolean)
      .join(" / ");
  }

  // Nombres de personajes de TSH → archivos de assets/images/personajes/
  var ALIAS_PJ = {
    hero: "dq_hero",
    piranha_plant: "packun_flower",
    incineroar: "gaogaen",
    pyra: "homura",
    mythra: "homura",
    pyra_and_mythra: "homura",
    min_min: "minmin",
    mii_brawler: "mii_fighter",
    mii_swordfighter: "mii_fighter",
    mii_gunner: "mii_fighter",
    rosalina: "rosalina_and_luma",
    banjo_kazooie: "banjo_and_kazooie",
    olimar_alph: "olimar",
    game_and_watch: "mr_game_and_watch",
    pokemon_trainer_red: "pokemon_trainer",
  };
  /**
   * Bandera del país del jugador, tal como la exporta TSH (dato de start.gg):
   * player.country.asset es una ruta dentro de la carpeta de TSH (assets/country_flag/xx.png).
   * Mismo criterio que los layouts oficiales de TSH (ruta en minúsculas).
   */
  function banderaTsh(jugador) {
    var a = jugador && jugador.country && jugador.country.asset;
    if (!a) return "";
    // Raíz de TSH: el servidor web, o la carpeta que contiene out/program_state.json.
    var raiz = /\/program-state$/.test(TSH.fuente)
      ? location.origin + "/"
      : TSH.fuente.replace(/[^\/]*$/, "").replace(/out\/$/, "");
    return raiz + String(a).replace(/^\.\//, "").toLowerCase();
  }

  function personajeTsh(jugador) {
    var c = lista(jugador && jugador.character)[0];
    var n = (c && (c.en_name || c.name)) || "";
    var k = String(n)
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/&/g, " and ")
      .replace(/[.'’]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "");
    return ALIAS_PJ[k] || k;
  }

  function aplicarTsh(estado, d) {
    var numero = String(TSH.tablero || d.evento.scoreboard || "1");
    var sc = (estado && estado.score) || {};
    // TSH actual: score["1"], score["2"]…; versiones viejas: un solo marcador en score.
    var tablero = sc[numero] || (sc.team ? sc : null);
    if (!tablero || !tablero.team) throw new Error("TSH no tiene el marcador " + numero);
    [1, 2].forEach(function (i) {
      var eq = tablero.team[String(i)] || {};
      var jugadores = lista(eq.player);
      var j = (d.partida["jugador" + i] = d.partida["jugador" + i] || {});
      j.nombre = nombreTsh(eq) || "Por definir";
      j.equipo = jugadores.length === 1 ? jugadores[0].team || "" : "";
      j.personaje = jugadores.length === 1 ? personajeTsh(jugadores[0]) : "";
      j.bandera = jugadores.length === 1 ? banderaTsh(jugadores[0]) : "";
      var s = Number(eq.score);
      j.marcador = isFinite(s) && s >= 0 ? s : 0;
    });
    // Con TSH, lo que TSH deja vacío queda vacío: no se muestran los ejemplos de config/.
    d.partida.ronda = tablero.match || tablero.phase || "";
    var bo = Number(tablero.best_of) || Number(String(tablero.best_of_text || "").replace(/\D+/g, ""));
    d.partida.formato = bo ? "BO" + bo : "";
    d.evento.comentaristas = lista(estado.commentary)
      .filter(function (c) {
        return c && c.name;
      })
      .slice(0, 2)
      .map(function (c) {
        return { nombre: c.name, usuario: c.twitter ? "@" + String(c.twitter).replace(/^@/, "") : "" };
      });
    TSH.estado.bracket = bracketTsh(estado.bracket, d);
    // El set del Top 8 que coincide con el marcador actual (y no terminó) queda «en juego».
    if (TSH.estado.bracket) {
      var a = d.partida.jugador1.nombre;
      var b = d.partida.jugador2.nombre;
      var g = victorias(d.bracket.formato);
      d.bracket.enJuego = "";
      Object.keys(d.bracket.cruces).forEach(function (id) {
        var x = d.bracket.cruces[id];
        var mismos = (x.j1 === a && x.j2 === b) || (x.j1 === b && x.j2 === a);
        if (mismos && !(Number(x.p1) >= g || Number(x.p2) >= g)) d.bracket.enJuego = id;
      });
    }
  }

  /**
   * Top 8 desde el bracket de TSH. Solo si el final del bracket es el estándar de
   * doble eliminación: winners [2, 1, 1, 1 (GF, reset)] y losers [2, 2, 1, 1].
   * Si no coincide, no adivina: se queda con config/bracket.js.
   */
  function bracketTsh(fuente, d) {
    var rondas = fuente && fuente.bracket && fuente.bracket.rounds;
    var slots = fuente && fuente.players && fuente.players.slot;
    if (!rondas || !slots) return false;
    var nums = Object.keys(rondas).map(Number);
    var sets = function (n) {
      return lista(rondas[n] && rondas[n].sets);
    };
    var w = nums
      .filter(function (n) {
        return n > 0;
      })
      .sort(function (a, b) {
        return a - b;
      })
      .slice(-4)
      .map(sets);
    var l = nums
      .filter(function (n) {
        return n < 0;
      })
      .sort(function (a, b) {
        return b - a;
      })
      .slice(-4)
      .map(sets);
    var forma = function (r, esperado) {
      return (
        r.length === esperado.length &&
        r.every(function (s, i) {
          return s.length === esperado[i];
        })
      );
    };
    if (!forma(w, [2, 1, 1, 1]) || !forma(l, [2, 2, 1, 1])) return false;
    var cruce = function (set) {
      var ids = lista(set && set.playerId);
      var pts = lista(set && set.score);
      var jugado = !!(set && set.completed) || Number(pts[0]) > 0 || Number(pts[1]) > 0;
      var lado = function (k) {
        var id = Number(ids[k]);
        var eq = id >= 0 ? slots[id] : null;
        var js = lista(eq && eq.player);
        return {
          f: js.length === 1 ? banderaTsh(js[0]) : "",
          j: id >= 0 ? nombreTsh(eq) : "",
          p: id >= 0 && jugado && pts[k] != null && Number(pts[k]) >= 0 ? Number(pts[k]) : "",
        };
      };
      var a = lado(0);
      var b = lado(1);
      return { j1: a.j, p1: a.p, j2: b.j, p2: b.p, f1: a.f, f2: b.f };
    };
    var gf = w[2][0];
    var gfPts = lista(gf && gf.score);
    var hayReset =
      !!(gf && gf.completed) &&
      Number(gfPts[1]) > Number(gfPts[0]) &&
      lista(w[3][0] && w[3][0].playerId).every(function (id) {
        return Number(id) >= 0;
      });
    d.bracket.cruces = {
      WSF1: cruce(w[0][0]),
      WSF2: cruce(w[0][1]),
      WF: cruce(w[1][0]),
      GF: cruce(gf),
      RESET: hayReset ? cruce(w[3][0]) : { j1: "", p1: "", j2: "", p2: "" },
      LR1A: cruce(l[0][0]),
      LR1B: cruce(l[0][1]),
      LQFA: cruce(l[1][0]),
      LQFB: cruce(l[1][1]),
      LSF: cruce(l[2][0]),
      LF: cruce(l[3][0]),
    };
    return true;
  }

  /** Mezcla b sobre a: los objetos se combinan; listas y valores se reemplazan. */
  function mezclar(a, b) {
    Object.keys(b).forEach(function (k) {
      var obj = function (x) {
        return x && typeof x === "object" && !Array.isArray(x);
      };
      a[k] = obj(a[k]) && obj(b[k]) ? mezclar(a[k], b[k]) : b[k];
    });
    return a;
  }

  function aplicarUrl(evento, partida) {
    var q = new URLSearchParams(location.search);
    partida.jugador1 = partida.jugador1 || {};
    partida.jugador2 = partida.jugador2 || {};
    var mapa = {
      p1: [partida.jugador1, "nombre"],
      p2: [partida.jugador2, "nombre"],
      s1: [partida.jugador1, "marcador"],
      s2: [partida.jugador2, "marcador"],
      e1: [partida.jugador1, "equipo"],
      e2: [partida.jugador2, "equipo"],
      c1: [partida.jugador1, "personaje"],
      c2: [partida.jugador2, "personaje"],
      ronda: [partida, "ronda"],
      formato: [partida, "formato"],
      tema: [evento, "tema"],
      evento: [evento, "evento"],
      inicio: [evento, "inicio"],
      fecha: [evento, "fecha"],
      logoEvento: [evento, "logoEvento"],
    };
    Object.keys(mapa).forEach(function (k) {
      if (q.has(k)) mapa[k][0][mapa[k][1]] = q.get(k);
    });
  }

  // ------------------------------------------------------------------ utilidades
  function valor(datos, ruta) {
    return ruta.split(".").reduce(function (o, k) {
      return o == null ? undefined : o[k];
    }, datos);
  }

  function $$(sel, raiz) {
    return Array.prototype.slice.call((raiz || document).querySelectorAll(sel));
  }

  function el(tag, clase, texto) {
    var e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto != null) e.textContent = texto;
    return e;
  }

  function img(src, alt) {
    var i = new Image();
    i.src = ROOT + src;
    i.alt = alt || "";
    i.decoding = "sync";
    return i;
  }

  /** Achica la letra hasta que el texto entre en su caja (nombres largos). */
  function ajustar(nodo) {
    nodo.style.fontSize = "";
    var base = parseFloat(getComputedStyle(nodo).fontSize);
    var min = base * parseFloat(nodo.dataset.ajustar || "0.5");
    var t = base;
    while (t > min && nodo.scrollWidth > nodo.clientWidth + 1) {
      t -= 1;
      nodo.style.fontSize = t + "px";
    }
  }

  // ------------------------------------------------------------------ render
  function render(d) {
    var html = document.documentElement;
    html.dataset.tema = d.evento.tema || "smash-hub";

    $$("[data-campo]").forEach(function (n) {
      var v = valor(d, n.dataset.campo);
      n.textContent = v == null ? "" : String(v);
      marcarVacio(n, v);
    });

    $$("[data-src]").forEach(function (n) {
      var v = valor(d, n.dataset.src);
      if (v) n.src = ROOT + v;
      else n.removeAttribute("src");
      marcarVacio(n, v);
    });

    var g = { BO3: 2, BO5: 3, BO7: 4 }[String(d.partida.formato || "").toUpperCase()] || 99;
    [1, 2].forEach(function (i) {
      var j = d.partida["jugador" + i] || {};
      $$("[data-jugador='" + i + "']").forEach(function (n) {
        n.classList.toggle("gana", Number(j.marcador) >= g);
        n.classList.toggle("con-equipo", !!j.equipo);
      });
      $$("[data-personaje='" + i + "']").forEach(function (n) {
        var p = (j.personaje || "").trim().toLowerCase().replace(/\s+/g, "_");
        n.classList.toggle("vacio", !p);
        var c = n.closest("[data-ocultar-vacio]");
        if (c) c.classList.toggle("vacio", !p);
        // Personaje sin ícono (nombre desconocido): se oculta en lugar de mostrar una imagen rota.
        n.onerror = function () {
          n.removeAttribute("src");
          n.classList.add("vacio");
          if (c) c.classList.add("vacio");
        };
        if (p) n.src = ROOT + "assets/images/personajes/" + p + ".svg";
        else n.removeAttribute("src");
      });
      $$("[data-inicial='" + i + "']").forEach(function (n) {
        n.textContent = (j.nombre || "?").trim().charAt(0).toUpperCase();
      });
      $$("[data-bandera='" + i + "']").forEach(function (n) {
        ponerBandera(n, j.bandera);
      });
    });

    // Esquinas del gameplay: config/partida.js («mostrar») o el evento/perfil («gameplay»).
    var m = d.partida.mostrar || {};
    var gp = d.evento.gameplay || {};
    html.classList.toggle("sin-marca", m.marca === false || gp.marca === false);
    html.classList.toggle("sin-patrocinadores", m.patrocinadores === false || gp.patrocinadores === false);
    // Opciones de composición (las usa el perfil de Center Stage):
    //   auspiciantesArriba: barra de auspiciantes arriba (abajo no se ve en pantallas gigantes)
    //   carrusel: los auspiciantes se deslizan en lugar de cambiar por tandas
    //   logoCentrado: el logo del evento grande y centrado, en lugar de chico en una esquina
    html.classList.toggle("con-camaras", gp.camaras === true);
    html.classList.toggle("auspicio-arriba", d.evento.auspiciantesArriba === true);
    html.classList.toggle("logo-centrado", d.evento.logoCentrado === true);
    html.classList.toggle("sin-redes", !(d.evento.redes || []).length && !d.evento.sitio);
    html.classList.toggle("con-logo-evento", !!d.evento.logoEvento);
    html.classList.toggle("con-logo-h", !!d.evento.logoEventoHorizontal);
    html.classList.toggle("sin-principal", !(d.evento.patrocinadores || {}).principal);

    $$("[data-lista]").forEach(function (n) {
      (listas[n.dataset.lista] || function () {})(n, d);
    });

    cuenta(d.evento.inicio);
    var fit = function () {
      $$("[data-ajustar]").forEach(ajustar);
    };
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
    fit();
    rotar();
    html.classList.add("listo");
    // Solo para las vistas previas de previews/, que lo cargan en un iframe.
    if (window.parent !== window) window.parent.postMessage("sh-listo", "*");
  }

  function marcarVacio(n, v) {
    var vacio = v == null || v === "" || (Array.isArray(v) && !v.length);
    n.classList.toggle("vacio", vacio);
    var c = n.closest("[data-ocultar-vacio]");
    if (c) c.classList.toggle("vacio", vacio);
  }

  var listas = {
    redes: function (n, d) {
      n.replaceChildren();
      (d.evento.redes || []).slice(0, 3).forEach(function (r) {
        var li = el("li", "red");
        li.append(el("span", "red-nombre", r.red), el("span", "red-usuario", r.usuario));
        n.append(li);
      });
    },
    secundarios: function (n, d) {
      n.replaceChildren();
      var p = d.evento.patrocinadores || {};
      var max = Number(n.dataset.max || 12);
      var lista = (p.secundarios || []).slice(0, max);
      lista.forEach(function (s) {
        n.append(logoPatrocinador(s, "patrocinador"));
      });
      n.classList.toggle("muchos", lista.length > 4);
      n.dataset.cantidad = lista.length;
    },
    todos: function (n, d) {
      // principal + secundarios, para tiras y rotación.
      var p = d.evento.patrocinadores || {};
      var lista = (p.principal ? [p.principal] : []).concat(p.secundarios || []);
      // Carrusel: las tiras ([data-pagina]) se deslizan sin cortes. El rotador de a uno
      // del gameplay no cambia.
      var carrusel = d.evento.carrusel === true && n.hasAttribute("data-pagina");
      n.classList.toggle("es-carrusel", carrusel);
      if (carrusel) {
        var firma = JSON.stringify(lista);
        if (n.dataset.firma === firma && n.firstChild) return; // no reiniciar el deslizamiento
        n.dataset.firma = firma;
        n.replaceChildren();
        var pista = el("div", "carrusel-pista");
        for (var k = 0; k < 2; k++) {
          var grupo = el("div", "carrusel-grupo");
          lista.forEach(function (s) {
            grupo.append(logoPatrocinador(s, "patrocinador"));
          });
          pista.append(grupo);
        }
        pista.style.setProperty("--duracion", Math.max(12, lista.length * 4) + "s");
        n.append(pista);
        return;
      }
      delete n.dataset.firma;
      n.replaceChildren();
      lista.forEach(function (s, i) {
        var l = logoPatrocinador(s, "patrocinador");
        l.style.setProperty("--i", i);
        n.append(l);
      });
      n.style.setProperty("--n", lista.length);
    },
    principal: function (n, d) {
      n.replaceChildren();
      var p = (d.evento.patrocinadores || {}).principal;
      if (p) n.append(logoPatrocinador(p, "patrocinador destacado"));
    },
    comentaristas: function (n, d) {
      var c = d.evento.comentaristas || [];
      $$("[data-comentarista]", n).forEach(function (slot) {
        var k = Number(slot.dataset.comentarista);
        var x = c[k] || {};
        slot.querySelector(".com-nombre").textContent = x.nombre || "";
        slot.querySelector(".com-usuario").textContent = x.usuario || "";
        // Sin nombre, la placa no se muestra (la cámara queda limpia).
        var placa = slot.matches(".caster") ? slot : slot.querySelector(".placa");
        if (placa) placa.classList.toggle("oculto", !x.nombre);
      });
    },
    mensajes: function (n, d) {
      n.replaceChildren();
      var msjs = (d.evento.mensajes || []).filter(Boolean);
      var extra = [d.evento.sitio].concat(
        (d.evento.redes || []).map(function (r) {
          return r.red + " · " + r.usuario;
        })
      );
      var todos = msjs.concat(extra).filter(Boolean);
      // Dos copias para que la cinta se repita sin cortes.
      for (var k = 0; k < 2; k++) {
        var grupo = el("div", "cinta-grupo");
        todos.forEach(function (t) {
          grupo.append(el("span", "cinta-item", t));
        });
        n.append(grupo);
      }
    },
    bracket: function (n, d) {
      renderBracket(n, d);
    },
    brasas: function (n) {
      if (n.childElementCount) return; // no reiniciar la animación
      var cant = Number(n.dataset.cantidad || 26);
      var semilla = 7;
      var azar = function () {
        semilla = (semilla * 9301 + 49297) % 233280;
        return semilla / 233280;
      };
      for (var i = 0; i < cant; i++) {
        var b = el("i", "brasa");
        b.style.left = (azar() * 100).toFixed(2) + "%";
        b.style.setProperty("--t", (9 + azar() * 10).toFixed(2) + "s");
        b.style.setProperty("--d", (-azar() * 18).toFixed(2) + "s");
        b.style.setProperty("--x", ((azar() - 0.5) * 160).toFixed(0) + "px");
        b.style.setProperty("--s", (2 + azar() * 4).toFixed(1) + "px");
        n.append(b);
      }
    },
  };

  // ------------------------------------------------------------------ bracket
  var VACIO = "Por definir";

  function renderBracket(n, d) {
    var b = d.bracket || {};
    var c = b.cruces || {};
    var g = victorias(b.formato);
    $$("[data-cruce]", n).forEach(function (card) {
      var id = card.dataset.cruce;
      var x = c[id] || {};
      var gf = id === "RESET" ? g : Number(id === "GF" && b.formatoFinal ? victorias(b.formatoFinal) : g);
      var w = Number(x.p1) >= gf ? 1 : Number(x.p2) >= gf ? 2 : 0;
      [1, 2].forEach(function (i) {
        var fila = card.querySelector("[data-fila='" + i + "']");
        var nombre = String(x["j" + i] || "").trim();
        var p = x["p" + i];
        fila.querySelector(".br-nombre").textContent = nombre || VACIO;
        var bandera = fila.querySelector(".br-bandera");
        if (bandera) ponerBandera(bandera, x["f" + i] || "");
        fila.querySelector(".br-puntos").textContent = p === "" || p == null ? "" : String(p);
        fila.classList.toggle("pendiente", !nombre);
        fila.classList.toggle("ganador", w === i);
        fila.classList.toggle("perdedor", !!w && w !== i);
      });
      card.classList.toggle("terminado", !!w);
      card.classList.toggle("en-juego", !!b.enJuego && b.enJuego === id);
    });
    var r = c.RESET || {};
    n.classList.toggle("con-reset", b.reset === true || !!(r.j1 || r.j2 || r.p1 || r.p2));
    requestAnimationFrame(function () {
      lineas(n);
    });
  }

  function victorias(formato) {
    return { BO3: 2, BO5: 3, BO7: 4 }[String(formato || "BO5").toUpperCase()] || 3;
  }

  /** Dibuja las conexiones entre cruces (data-hacia) en el SVG del bracket. */
  function lineas(n) {
    var svg = n.querySelector(".br-lineas");
    if (!svg) return;
    var NS = "http://www.w3.org/2000/svg";
    svg.replaceChildren();
    var caja = function (card) {
      var k = card.querySelector(".br-caja");
      return {
        x: card.offsetLeft + k.offsetLeft,
        y: card.offsetTop + k.offsetTop,
        w: k.offsetWidth,
        h: k.offsetHeight,
      };
    };
    $$("[data-hacia]", n).forEach(function (src) {
      var dst = n.querySelector("[data-cruce='" + src.dataset.hacia + "']");
      if (!dst || dst.offsetParent === null || src.offsetParent === null) return;
      var a = caja(src);
      var z = caja(dst);
      var dPath;
      if (src.dataset.hacia === "RESET") {
        // Grand Final → reset, que está debajo: línea vertical
        var cx = a.x + a.w / 2;
        dPath = "M" + cx + " " + (a.y + a.h) + " V" + z.y;
      } else {
        var x1 = a.x + a.w;
        var y1 = a.y + a.h / 2;
        var x2 = z.x;
        var y2 = z.y + z.h / 2;
        var xm = Math.round((x1 + x2) / 2);
        dPath = "M" + x1 + " " + y1 + " H" + xm + " V" + y2 + " H" + x2;
      }
      var p = document.createElementNS(NS, "path");
      p.setAttribute("d", dPath);
      p.setAttribute("class", "br-linea" + (src.classList.contains("terminado") ? " activa" : ""));
      svg.append(p);
    });
  }

  /** Muestra la bandera si hay ruta; si no hay o la imagen no carga, se oculta. */
  function ponerBandera(n, url) {
    n.onerror = function () {
      n.removeAttribute("src");
      n.classList.add("vacio");
    };
    n.classList.toggle("vacio", !url);
    if (!url) n.removeAttribute("src");
    else if (n.getAttribute("src") !== url) n.src = url;
  }

  function logoPatrocinador(s, clase) {
    // estilo: "blanco" pasa el logo a blanco; "placa" lo pone sobre una placa clara.
    var extra = { blanco: " logo-blanco", placa: " logo-placa" }[s.estilo] || "";
    var caja = el("div", clase + extra);
    if (s.logo) caja.append(img(s.logo, s.nombre));
    else caja.append(el("span", "patrocinador-texto", s.nombre || ""));
    return caja;
  }

  // ------------------------------------------------------------------ cuenta regresiva
  var reloj = null;
  function cuenta(inicio) {
    var nodos = $$("[data-cuenta]");
    if (!nodos.length) return;
    clearInterval(reloj);
    var t = inicio ? Date.parse(inicio) : NaN;
    nodos.forEach(function (n) {
      var c = n.closest("[data-ocultar-vacio]");
      if (c) c.classList.toggle("vacio", isNaN(t));
    });
    if (isNaN(t)) return;
    var tick = function () {
      var s = Math.max(0, Math.round((t - Date.now()) / 1000));
      var h = Math.floor(s / 3600);
      var mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
      var ss = String(s % 60).padStart(2, "0");
      var txt = s === 0 ? "En instantes" : (h ? h + ":" + mm : mm) + ":" + ss;
      nodos.forEach(function (n) {
        n.textContent = txt;
      });
    };
    tick();
    reloj = setInterval(tick, 1000);
  }

  // ------------------------------------------------------------------ rotación
  // [data-rotar="6"] muestra un hijo por vez y cambia cada 6 segundos.
  // Con data-pagina="5" muestra tandas de 5 (para listas largas de auspiciantes).
  var paso = 0;
  function rotar() {
    $$("[data-rotar]").forEach(function (n) {
      if (n.classList.contains("es-carrusel")) return;
      var hijos = n.children;
      if (!hijos.length) return;
      var cada = Number(n.dataset.rotar || 6);
      var tam = Number(n.dataset.pagina || 1);
      var paginas = Math.ceil(hijos.length / tam);
      // data-desfase="mitad": empieza en la mitad de la lista (dos rotadores sin repetirse)
      var desfase = n.dataset.desfase === "mitad" ? Math.floor(paginas / 2) : 0;
      var k = (Math.floor(paso / cada) + desfase) % paginas;
      for (var i = 0; i < hijos.length; i++) hijos[i].classList.toggle("activo", Math.floor(i / tam) === k);
    });
  }
  setInterval(function () {
    paso++;
    rotar();
  }, 1000);

  // ------------------------------------------------------------------ ciclo
  function ciclo() {
    leerDatos().then(function (d) {
      avisoTsh(d);
      var firma = JSON.stringify(d);
      if (firma !== ultimo) {
        ultimo = firma;
        render(d);
      }
    });
  }

  // Con TSH se relee cada segundo, para que el marcador cambie casi al instante.
  function programar() {
    setTimeout(function () {
      ciclo();
      programar();
    }, TSH.estado.activo ? 1000 : INTERVALO);
  }
  ciclo();
  if (!Q.has("fijo")) programar();
})();
