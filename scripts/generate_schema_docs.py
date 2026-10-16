from pathlib import Path
import sys,json
sys.path.insert(0,'apps/api')
from app.database import models
from app.database.base import Base
from app.main import create_app
from app.core.config import Settings
text='''# Modelo de datos

La revisión congelada `0001` crea 19 tablas de dominio; `0002` agrega procedencia, publicación, conflictos y resultados incompletos sin nuevas tablas. `0003` separa estado, resolución y elegibilidad de sets (ADR-009). Todas tienen `id UUID` generado por la aplicación, `created_at TIMESTAMPTZ DEFAULT now()` y `updated_at TIMESTAMPTZ DEFAULT now()` (actualizado por SQLAlchemy en cambios ORM). Los IDs externos nunca reemplazan las claves internas. Las FKs restringen borrados de entidades referenciadas para preservar historial.

## Relaciones

```mermaid
erDiagram
    countries ||--o{ regions : contiene
    countries o|--o{ communities : ubica
    regions o|--o{ communities : ubica
    countries o|--o{ players : ubica
    regions o|--o{ players : ubica
    communities ||--o{ community_games : admite
    games ||--o{ community_games : asociado
    games ||--o{ characters : contiene
    players ||--o{ player_aliases : historial
    players ||--o{ external_identities : vincula
    data_sources ||--o{ external_identities : identifica
    communities ||--o{ tournaments : organiza
    tournaments ||--o{ events : contiene
    games ||--o{ events : compite
    tournaments ||--o{ tournament_participants : inscribe
    players ||--o{ tournament_participants : participa
    events ||--o{ event_entrants : registra
    event_entrants ||--|{ entrant_members : integra
    tournament_participants ||--o{ entrant_members : compone
    events ||--o{ sets : contiene
    sets ||--o{ set_sides : enfrenta
    event_entrants o|--o{ set_sides : ocupa
    data_sources ||--o{ import_jobs : origina
    data_sources ||--o{ external_mappings : mapea
    tournaments o|--o{ external_mappings : referencia
    events o|--o{ external_mappings : referencia
    sets o|--o{ external_mappings : referencia
    event_entrants o|--o{ external_mappings : referencia
```

La cardinalidad del roster se comprueba al commit: `team_size=1` singles, `2` dobles, otros tamaños positivos admitidos. Un torneo contiene eventos de varios juegos; el juego no es atributo del torneo. La geografía es opcional para jugadores y comunidades; cuando hay región, debe corresponder al país indicado.

## Invariantes competitivas

- `players.tag` está indexado y no es único. `player_aliases` conserva intervalos de tags; `tag_snapshot` en la inscripción evita reescribir la presentación histórica. El importador registra aliases observados sin inventar intervalos de exclusividad; el tag actual solo cambia con evidencia de un torneo posterior y sin bloqueo manual.
- `tournament_participants` tiene una inscripción por jugador/torneo. `entrant_members` apunta a esta inscripción, no directamente a un nombre. FKs compuestas impiden integrar participantes de otro torneo y lados de otro evento.
- Un participante solo integra un entrant por evento. El roster debe tener exactamente el tamaño del evento, con posiciones únicas entre 1 y ese tamaño. Los triggers validan al commit y bloquean las filas de entrant/evento durante la comprobación.
- El status de sets es formato legado de Misión 01/02 para sus triggers; el estado público proviene de lifecycle_status y se interpreta junto a resolution. stats_eligible/ranking_eligible excluyen BYE, DQ, placeholders, resets no utilizados y resultados insuficientes.
- Un set tiene como máximo dos lados distintos y no puede enfrentar un entrant consigo mismo. Los lados pueden estar incompletos mientras el set esté pendiente; no se guardan ganadores ni scores de pendientes.
- `completed`: dos entrants, un ganador, dos scores no negativos y score ganador mayor. Si existe best_of, debe ser impar positivo y el ganador alcanza `best_of // 2 + 1` victorias.
- `dq`: dos entrants, un ganador y scores ausentes. `bye`: un entrant, un ganador y scores ausentes. DQ doble y juegos con más de dos lados quedan para una extensión explícita del modelo.
- `completed_at` es nullable cuando la fuente no publica fecha; un pendiente no lo tiene. `incomplete` conserva resultados finales insuficientes o ambiguos. Solo completed con scores válidos y fecha habilita ranking_eligible como candidato futuro; no se calcula ranking. Los checks por fila se complementan con triggers diferidos por set/lado, que también validan borrados o modificaciones de lados.
- `external_mappings` tiene unicidad fuente/tipo/id externo y fuente/destino interno. Un set externo no puede producir dos sets internos. Cada mapeo apunta a exactamente una FK del tipo declarado; no existen referencias polimórficas sin FK.
- `import_jobs` usa unicidad fuente/idempotency_key. La futura integración realizará escrituras y mapeos en una transacción y hará upsert sobre estas claves; la fundación no importa datos por sí sola.

Los futuros juegos individuales pueden introducir `set_games(set_id, game_number)` y selecciones referenciando `set_sides` y `characters`. No se crean esas tablas todavía. No hay reglas fijas de Paraguay o Smash en las restricciones.

## Diccionario

Columnas comunes descritas arriba; a continuación se listan los campos específicos y restricciones de cada tabla. Los timestamps usan zona horaria. Los valores de origen/sincronización residen en mappings e identidades externas.
'''
descriptions={'countries':'País con ISO de dos letras mayúsculas.','regions':'Subdivisión de un país; código único dentro del país.','communities':'Comunidad con slug global; geografía opcional.','community_games':'Juegos habilitados para una comunidad.','games':'Catálogo global de videojuegos.','characters':'Personajes únicos por slug dentro de cada juego.','players':'Persona/identidad competitiva persistente; el tag no es identificador.','player_aliases':'Tags observados: valid_from es primera evidencia conocida del tag, valid_to no se inventa.','external_identities':'Cuenta externa vinculada a jugador, con sincronización.','tournaments':'Encuentro organizativo; puede contener varios juegos.','tournament_participants':'Inscripción de jugador a torneo, con tag conservado.','events':'Competencia concreta de un juego y tamaño de equipo.','event_entrants':'Unidad competitiva inscrita al evento, individual o equipo.','entrant_members':'Roster mediante participantes del mismo torneo.','sets':'Enfrentamiento con estado y formato opcional.','set_sides':'Lado 1 o 2, entrant y resultado.','data_sources':'Proveedor externo sin tokens.','import_jobs':'Un intento de importación con estado, conteos, conflictos y fechas.','external_mappings':'Correspondencia verificable entre proveedor e identidad interna.'}
from sqlalchemy import UniqueConstraint,CheckConstraint
for table in Base.metadata.sorted_tables:
 text+=f'\n### `{table.name}`\n\n{descriptions[table.name]}\n\n| Campo | Tipo | Nullable | Referencia |\n| --- | --- | --- | --- |\n'
 for c in table.columns:
  if c.name in {'id','created_at','updated_at'}:continue
  refs=', '.join(f.target_fullname for f in c.foreign_keys) or '—'
  text+=f'| `{c.name}` | `{c.type}` | {"sí" if c.nullable else "no"} | {refs} |\n'
 for constraint in sorted(table.constraints,key=lambda c:str(c.name)):
  if isinstance(constraint,UniqueConstraint):text+='\nÚnica: `'+', '.join(c.name for c in constraint.columns)+'`.\n'
  if isinstance(constraint,CheckConstraint):text+='\nCheck: `'+str(constraint.sqltext).replace('\n',' ')+'`.\n'
Path('docs/database/schema.md').write_text(text,encoding='utf-8')
app=create_app(Settings(_env_file=None,database_url='postgresql://unused:unused@localhost/unused',migration_database_url=None))
Path('docs/api/openapi.json').write_text(json.dumps(app.openapi(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
