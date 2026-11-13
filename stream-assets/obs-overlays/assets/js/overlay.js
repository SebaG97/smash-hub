/*
 * Smash Hub · overlays para OBS.
 * Carga config/evento.js y config/partida.js, completa la escena y los vuelve
 * a leer cada 2 segundos. No hay que tocar este archivo para usar los overlays.
 *
 * Parámetros opcionales en la URL (tienen prioridad sobre config/):
 *   ?p1=Nombre&p2=Nombre&s1=1&s2=0&e1=Equipo&e2=Equipo&c1=mario&c2=fox
 *   &ronda=Grand%20Final&formato=BO5&tema=center-stage&evento=Center%20Stage
 *   &logoEvento=assets/images/eventos/center-stage/logo.png&inicio=2026-11-14T15:00:00-03:00
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
    return Promise.all([cargar("config/evento.js"), cargar("config/partida.js")]).then(function () {
      var evento = clonar(window.SH_EVENTO || {});
      var partida = clonar(window.SH_PARTIDA || {});
      aplicarUrl(evento, partida);
      return { evento: evento, partida: partida };
    });
  }

  function clonar(o) {
    return JSON.parse(JSON.stringify(o));
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
        if (p) n.src = ROOT + "assets/images/personajes/" + p + ".svg";
        else n.removeAttribute("src");
      });
      $$("[data-inicial='" + i + "']").forEach(function (n) {
        n.textContent = (j.nombre || "?").trim().charAt(0).toUpperCase();
      });
    });

    var m = d.partida.mostrar || {};
    html.classList.toggle("sin-marca", m.marca === false);
    html.classList.toggle("sin-patrocinadores", m.patrocinadores === false);
    html.classList.toggle("con-logo-evento", !!d.evento.logoEvento);

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
      var max = Number(n.dataset.max || 8);
      (p.secundarios || []).slice(0, max).forEach(function (s) {
        n.append(logoPatrocinador(s, "patrocinador"));
      });
    },
    todos: function (n, d) {
      // principal + secundarios, para tiras y rotación.
      n.replaceChildren();
      var p = d.evento.patrocinadores || {};
      var lista = (p.principal ? [p.principal] : []).concat(p.secundarios || []);
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

  function logoPatrocinador(s, clase) {
    var caja = el("div", clase);
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
  // Los contenedores [data-rotar="6"] muestran un hijo por vez, cada 6 segundos.
  var paso = 0;
  function rotar() {
    $$("[data-rotar]").forEach(function (n) {
      var hijos = n.children;
      if (!hijos.length) return;
      var cada = Number(n.dataset.rotar || 6);
      var k = Math.floor(paso / cada) % hijos.length;
      for (var i = 0; i < hijos.length; i++) hijos[i].classList.toggle("activo", i === k);
    });
  }
  setInterval(function () {
    paso++;
    rotar();
  }, 1000);

  // ------------------------------------------------------------------ ciclo
  function ciclo() {
    leerDatos().then(function (d) {
      var firma = JSON.stringify(d);
      if (firma !== ultimo) {
        ultimo = firma;
        render(d);
      }
    });
  }

  ciclo();
  if (!new URLSearchParams(location.search).has("fijo")) setInterval(ciclo, INTERVALO);
})();
