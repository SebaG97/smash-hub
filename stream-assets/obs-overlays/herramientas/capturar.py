"""
Genera las capturas PNG de previews/ a 1920 x 1080.

Solo para mantener el paquete: los overlays NO necesitan esto para funcionar.
Requiere Python 3 con Playwright y Chrome o Edge instalados:
    pip install playwright
    python herramientas/capturar.py            # todas
    python herramientas/capturar.py gameplay   # solo las que contienen "gameplay"

Las capturas usan datos de ejemplo pasados por URL; config/ no se modifica.
"""

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "previews"

EJEMPLO = {
    "p1": "Ñandutí",
    "p2": "Karai Guasu",
    "e1": "SCP",
    "s1": "2",
    "s2": "1",
    "c1": "cloud",
    "c2": "pikachu",
    "ronda": "Winners Final",
    "formato": "BO5",
    "fijo": "1",
}

CENTER_STAGE = {"perfil": "center-stage"}
BRACKET = {"bracket": "previews/datos/bracket-ejemplo.js"}

# (archivo de salida, página, parámetros extra, fondo transparente)
CAPTURAS = [
    ("01-gameplay.png", "gameplay.html", {}, True),
    ("01-gameplay-simulado.png", "previews/gameplay-simulado.html", {}, False),
    ("01-gameplay-zonas-hud.png", "previews/gameplay-simulado.html", {"guias": "1"}, False),
    ("01-gameplay-nombres-largos.png", "previews/gameplay-simulado.html",
     {"p1": "Supercalifragilístico", "e1": "TEAM LARGO", "p2": "Mbarete Guasu Paraguay", "s1": "3", "s2": "2"}, False),
    ("02-versus.png", "versus.html", {}, False),
    ("02-versus-sin-personajes.png", "versus.html", {"c1": "", "c2": "", "e1": ""}, False),
    ("03-starting-soon.png", "starting-soon.html", {"inicio": "+872"}, False),
    ("03-starting-soon-sin-cuenta.png", "starting-soon.html", {}, False),
    ("04-intermission.png", "intermission.html", {}, False),
    ("05-commentators.png", "commentators.html", {}, True),
    ("05-commentators-simulado.png", "previews/commentators-simulado.html", {}, False),
    ("06-sponsors.png", "sponsors.html", {}, False),
    ("08-bracket.png", "bracket.html", BRACKET, False),
    ("08-bracket-vacio.png", "bracket.html", {}, False),
    ("09-gameplay-broadcast.png", "gameplay-broadcast.html", {}, True),
    ("09-gameplay-broadcast-simulado.png", "previews/broadcast-simulado.html", {"vista": "gameplay-broadcast"}, False),
    ("10-commentators-wide.png", "commentators-wide.html", {}, True),
    ("10-commentators-wide-simulado.png", "previews/broadcast-simulado.html", {"vista": "commentators-wide"}, False),
    ("11-ending.png", "ending.html", {}, False),
    ("07-center-stage-gameplay-broadcast.png", "previews/broadcast-simulado.html", {**CENTER_STAGE, "vista": "gameplay-broadcast"}, False),
    ("07-center-stage-commentators-wide.png", "previews/broadcast-simulado.html", {**CENTER_STAGE, "vista": "commentators-wide"}, False),
    ("07-center-stage-ending.png", "ending.html", CENTER_STAGE, False),
    ("07-center-stage-gameplay.png", "previews/gameplay-simulado.html", CENTER_STAGE, False),
    ("07-center-stage-versus.png", "versus.html", CENTER_STAGE, False),
    ("07-center-stage-starting-soon.png", "starting-soon.html", {**CENTER_STAGE, "inicio": "+872"}, False),
    ("07-center-stage-intermission.png", "intermission.html", CENTER_STAGE, False),
    ("07-center-stage-commentators.png", "previews/commentators-simulado.html", CENTER_STAGE, False),
    ("07-center-stage-sponsors.png", "sponsors.html", CENTER_STAGE, False),
    ("07-center-stage-bracket.png", "bracket.html", {**CENTER_STAGE, **BRACKET}, False),
]


def main() -> None:
    filtro = sys.argv[1] if len(sys.argv) > 1 else ""
    SALIDA.mkdir(exist_ok=True)
    errores = []
    with sync_playwright() as pw:
        navegador = None
        for canal in ("chrome", "msedge", None):
            try:
                navegador = pw.chromium.launch(channel=canal) if canal else pw.chromium.launch()
                break
            except Exception:
                continue
        if navegador is None:
            raise SystemExit("No se encontró Chrome, Edge ni Chromium de Playwright.")
        for salida, pagina, extra, transparente in CAPTURAS:
            if filtro not in salida:
                continue
            ctx = navegador.new_context(viewport={"width": 1920, "height": 1080})
            p = ctx.new_page()
            p.on("pageerror", lambda e, s=salida: errores.append(f"{s}: {e}"))
            p.on("requestfailed", lambda r, s=salida: errores.append(f"{s}: no cargó {r.url}"))
            fuera = []
            p.on("request", lambda r: fuera.append(r.url) if not r.url.startswith(("file:", "data:")) else None)
            params = {**EJEMPLO, **extra}
            if params.get("inicio", "").startswith("+"):  # segundos desde ahora
                t = datetime.now(timezone.utc) + timedelta(seconds=int(params["inicio"][1:]))
                params["inicio"] = t.isoformat()
            q = urlencode(params)
            p.goto((RAIZ / pagina).as_uri() + "?" + q)
            p.wait_for_function("document.documentElement.classList.contains('listo')")
            p.evaluate("document.fonts.ready")
            time.sleep(2.2)  # que terminen las entradas
            p.screenshot(path=str(SALIDA / salida), omit_background=transparente)
            if fuera:
                errores.append(f"{salida}: pidió recursos externos {fuera}")
            print("ok", salida)
            ctx.close()
        navegador.close()
    if errores:
        print("\n".join(errores))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
