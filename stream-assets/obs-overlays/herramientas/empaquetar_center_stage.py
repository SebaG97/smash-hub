"""
Arma el ZIP de Center Stage para quien opera el stream:
    python herramientas/empaquetar_center_stage.py
Resultado: stream-assets/dist/CENTER-STAGE-OVERLAYS.zip (carpeta center-stage-overlays/).

Qué cambia respecto del paquete completo:
- config/evento.js con perfil "center-stage", TSH activado, fecha del evento
  y sin textos de ejemplo (sitio, redes y comentaristas vacíos: no se muestran).
- Sin herramientas, sin capturas de Smash Hub y sin placeholders de patrocinadores.
- LEEME.txt de herramientas/paquete-center-stage/.
"""

import re
import shutil
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIST = RAIZ.parent / "dist"
NOMBRE = "center-stage-overlays"
FECHA = "14 y 15 de noviembre"


def reemplazar(texto: str, viejo: str, nuevo: str) -> str:
    if viejo not in texto:
        raise SystemExit(f"config/evento.js cambió: no se encontró {viejo!r}")
    return texto.replace(viejo, nuevo)


def evento_center_stage(texto: str) -> str:
    t = texto
    t = reemplazar(t, '  perfil: "",', '  perfil: "center-stage",')
    t = reemplazar(t, "  tsh: false,", "  tsh: true, // false = datos a mano en config/partida.js y config/bracket.js")
    t = re.sub(r'  evento: "[^"]*",[^\n]*', '  evento: "Center Stage",', t, count=1)
    t = re.sub(r'  fecha: "[^"]*",[^\n]*', f'  fecha: "{FECHA}",', t, count=1)
    t = re.sub(r'  hora: "[^"]*",[^\n]*', '  hora: "", // COMPLETAR, por ejemplo "15:00" (vacío = no se muestra)', t, count=1)
    t = re.sub(r'  lugar: "[^"]*",[^\n]*', '  lugar: "Paraguay", // COMPLETAR con la sede si se quiere mostrar', t, count=1)
    t = re.sub(r'  sitio: "[^"]*",[^\n]*', '  sitio: "", // COMPLETAR: sitio web (vacío = no se muestra)', t, count=1)
    t = re.sub(
        r"  redes: \[.*?\n  \],\n",
        "  redes: [\n    // COMPLETAR (hasta 3). Vacío = no se muestran. Ejemplo:\n"
        '    // { red: "Instagram", usuario: "@cuenta" },\n  ],\n',
        t,
        count=1,
        flags=re.S,
    )
    t = re.sub(
        r"  patrocinadores: \{.*?\n  \},\n",
        "  // Los auspiciantes de Center Stage están en config/perfiles/center-stage.js.\n"
        "  patrocinadores: { principal: null, secundarios: [] },\n",
        t,
        count=1,
        flags=re.S,
    )
    t = re.sub(
        r"  comentaristas: \[.*?\n  \],\n",
        "  // Con TSH, los comentaristas salen de TSH. Sin TSH, completar aquí:\n"
        '  // { nombre: "Nombre", usuario: "@usuario" },\n  comentaristas: [],\n',
        t,
        count=1,
        flags=re.S,
    )
    for prohibido in ("tu-sitio", "@tu_cuenta", "placeholder-"):
        if prohibido in t:
            raise SystemExit(f"quedó un placeholder en evento.js: {prohibido}")
    return t


def main() -> None:
    obra = DIST / "_obra" / NOMBRE
    if obra.parent.exists():
        shutil.rmtree(obra.parent)
    obra.mkdir(parents=True)
    for html in RAIZ.glob("*.html"):
        shutil.copy2(html, obra / html.name)
    shutil.copytree(RAIZ / "assets", obra / "assets", ignore=shutil.ignore_patterns("placeholder-*"))
    shutil.copytree(RAIZ / "config", obra / "config")
    (obra / "previews").mkdir()
    for png in sorted((RAIZ / "previews").glob("*.png")):
        if png.name.startswith(("07-center-stage-", "12-tsh-")):
            shutil.copy2(png, obra / "previews" / png.name)
    evento = obra / "config" / "evento.js"
    evento.write_text(evento_center_stage(evento.read_text(encoding="utf-8")), encoding="utf-8")
    shutil.copy2(RAIZ / "herramientas" / "paquete-center-stage" / "LEEME.txt", obra / "LEEME.txt")

    DIST.mkdir(exist_ok=True)
    salida = DIST / "CENTER-STAGE-OVERLAYS.zip"
    salida.unlink(missing_ok=True)
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(obra.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(obra.parent))
    print(f"{salida} · {salida.stat().st_size / 1e6:.1f} MB · {len(z.namelist())} archivos")
    print(f"carpeta para revisar: {obra}")


if __name__ == "__main__":
    main()
