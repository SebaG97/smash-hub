"""Player achievement rules (SH-ACH-01). Pure: they read a Context built from the
database by app.achievements.service and return the awards that hold today.

Every rule uses only eligible sets of published tournaments (insights.engine.load): no
DQs, byes or placeholders, seeds dropped when organizers flagged the seeding unreliable.
Players are hub players (players.id), resolved from start.gg player ids at import; a
nametag never identifies anyone. Nothing is invented: a rule that needs a score, a round
or the characters of a game skips sets that do not have them.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from app.achievements import catalog
from app.insights import engine as insights

RULE_VERSION = 1
LEGACY_PERMANENT = (
    "trofeos",
    "campeon",
    "amateur",
    "david",
    "remontadas",
    "racha",
    "top8",
    "incansable",
    "mes",
)
YOSHI = "Yoshi"


@dataclass
class SetInfo:
    round: int | None = None  # start.gg: negative in the losers bracket
    best_of: int | None = None
    winner_score: int | None = None
    loser_score: int | None = None

    @property
    def scored(self):
        return self.winner_score is not None and self.loser_score is not None


@dataclass
class Context:
    data: insights.Data
    sets: dict = field(default_factory=dict)  # set id (str) -> SetInfo
    # set id (str) -> [(game number, {player: character}, winning player)]
    games: dict = field(default_factory=dict)
    links: dict = field(default_factory=dict)  # player id -> link created_at
    mufa: list = field(default_factory=list)  # (player, contest, settled_at, share)
    subjects: dict = field(default_factory=dict)  # "spike"/"vbash" -> player id (active)
    manual: dict = field(default_factory=dict)  # player id -> active manual ids


@dataclass
class Award:
    player: object
    achievement_id: str
    event_at: object = None
    detail: str = ""
    evidence: dict = field(default_factory=dict)
    tournament_id: str | None = None
    event_id: str | None = None
    set_id: str | None = None
    opponent: object = None


def _big(f, size=16):
    return f.get("main", True) and (f["entrants"] or 0) >= size


def _title(f, size=8):
    return f.get("main", True) and f["placement"] == 1 and (f["entrants"] or 0) >= size


def _local(at):
    return at.astimezone(insights.ASUNCION)


def _nth(items, n):
    """The n-th item (1-based) in order, or None."""
    return items[n - 1] if len(items) >= n else None


class _Builder:
    def __init__(self, ctx):
        self.ctx = ctx
        self.data = ctx.data
        self.out = {}
        self.tags = ctx.data.tags

    def give(self, award):
        key = (award.player, award.achievement_id)
        known = self.out.get(key)
        # Keep the earliest occurrence: the first time it happened.
        if known is None or (
            award.event_at is not None
            and (known.event_at is None or award.event_at < known.event_at)
        ):
            self.out[key] = award

    def tag(self, player):
        return self.tags.get(player) or "?"

    def from_match(self, player, aid, m, detail, **extra):
        opponent = m.loser if m.winner == player else m.winner
        self.give(
            Award(
                player,
                aid,
                m.at,
                detail,
                dict(extra, set=m.id, round=m.round, tournament=m.tournament),
                m.tournament_id,
                m.event_id,
                m.id,
                opponent,
            )
        )

    def from_finish(self, player, aid, f, detail, **extra):
        self.give(
            Award(
                player,
                aid,
                f["starts_at"],
                detail,
                dict(
                    extra,
                    tournament=f["tournament"],
                    event=f["event"],
                    placement=f["placement"],
                    seed=f["seed"],
                    entrants=f["entrants"],
                ),
                f["tournament_id"],
                f["event_id"],
            )
        )


def evaluate(ctx):
    """{(player, achievement id): Award} for every active automatic achievement."""
    b = _Builder(ctx)
    data = ctx.data
    matches_of = defaultdict(list)
    in_event = defaultdict(list)
    for m in data.matches:  # already chronological
        for p in (m.winner, m.loser):
            matches_of[p].append(m)
            in_event[(p, m.event_id)].append(m)
    finishes_of = defaultdict(list)
    finish_at = {}
    for f in sorted(data.finishes, key=lambda f: (f["starts_at"] is None, f["starts_at"] or 0)):
        finishes_of[f["player"]].append(f)
        finish_at[(f["player"], f["event_id"])] = f
    players = set(matches_of) | set(finishes_of)

    _legacy(b, players)
    for p in players:
        mine = matches_of[p]
        finishes = finishes_of[p]
        _brackets(b, p, mine, finishes, in_event, finish_at)
        _career(b, p, mine, finishes)
        _rivals(b, p, mine)
        _characters(b, p, mine)
        _specials(b, p, mine, finishes)
    for player, created in ctx.links.items():
        b.give(Award(player, "ese_soy_yo", created, "Vinculó su cuenta a su jugador."))
    for player, contest, settled, share in ctx.mufa:
        b.give(
            Award(
                player,
                "la_mufa_no_funciona",
                settled,
                f"Era el favorito del Prode de {contest} ({round(100 * share)} % lo eligió) "
                "y ganó.",
                dict(contest=contest, share=share),
            )
        )
    _spike(b, ctx, matches_of, in_event, finish_at)
    _vbash(b, ctx, matches_of)
    return _finish(b, ctx)


def _legacy(b, players):
    """The old permanent badges, with the same conditions (insights.player_insights)."""
    data = b.data
    for p in players:
        earned = {x["id"]: x for x in insights.player_insights(data, p)["badges"]}
        for aid in LEGACY_PERMANENT:
            if aid in earned:
                b.give(Award(p, aid, _legacy_when(data, p, aid), earned[aid]["why"]))


def _legacy_when(data, p, aid):
    """When the old badge was first earned, as far as the data tells."""
    mine = [m for m in data.matches if p in (m.winner, m.loser)]
    wins = [m for m in mine if m.winner == p]
    finishes = sorted(
        (f for f in data.finishes if f["player"] == p and f["starts_at"]),
        key=lambda f: f["starts_at"],
    )
    titles = [f for f in finishes if _title(f)]
    if aid == "campeon":
        f = _nth(titles, 1)
    elif aid == "trofeos":
        f = _nth(titles, 3)
    elif aid == "amateur":
        f = _nth([f for f in finishes if not f.get("main", True) and _title(dict(f, main=True))], 1)
    elif aid == "top8":
        f = _nth([f for f in finishes if _big(f) and f["placement"] <= 8], 5)
    elif aid == "incansable":
        f = _nth(_distinct_tournaments(finishes), 15)
    elif aid == "david":
        m = _nth([m for m in wins if m.factor >= 3], 1)
        return m.at if m else None
    elif aid == "remontadas":
        m = _nth([m for m in wins if m.comeback], 5)
        return m.at if m else None
    elif aid == "racha":
        return _streak_reached(mine, p, 10)
    else:
        return None
    return f["starts_at"] if f else None


def _distinct_tournaments(finishes):
    seen, out = set(), []
    for f in finishes:
        if f["tournament_id"] not in seen and f["starts_at"]:
            seen.add(f["tournament_id"])
            out.append(f)
    return out


def _streak_reached(mine, p, length):
    run = 0
    for m in mine:
        run = run + 1 if m.winner == p else 0
        if run == length:
            return m.at
    return None


def _brackets(b, p, mine, finishes, in_event, finish_at):
    ctx = b.ctx
    wins = [m for m in mine if m.winner == p]
    first_win = _nth(wins, 1)
    if first_win:
        b.from_match(
            p, "estreno", first_win, f"Ganó su primer set oficial en {first_win.tournament}."
        )
    for m in wins:
        if m.factor >= 5:
            b.from_match(
                p,
                "ndeee",
                m,
                f"Siendo seed {m.winner_seed} le ganó a {b.tag(m.loser)} (seed {m.loser_seed}) "
                f"en {m.tournament}.",
                factor=m.factor,
            )
        info = ctx.sets.get(m.id)
        if info and info.scored and info.winner_score == 3 and info.loser_score == 0:
            rival = finish_at.get((m.loser, m.event_id))
            if rival and rival["placement"] <= 8:
                b.from_match(p, "barrida", m, f"Le ganó 3-0 a {b.tag(m.loser)} en {m.tournament}.")
        if info and info.scored and info.winner_score == 3 and info.loser_score == 2:
            games = sorted(ctx.games.get(m.id) or [])
            if len(games) >= 5 and games[0][2] == m.loser and games[1][2] == m.loser:
                b.from_match(
                    p,
                    "reverse_3_0",
                    m,
                    f"Perdía 0-2 contra {b.tag(m.loser)} y ganó 3-2 en {m.tournament}.",
                )
    events = Counter(m.event_id for m in mine)
    for event_id, n in events.items():
        if n >= 8:
            last = in_event[(p, event_id)][-1]
            b.from_match(p, "kane_o", last, f"Jugó {n} sets en {last.tournament}.", sets=n)
        ev = in_event[(p, event_id)]
        lost_to = {}
        for m in ev:
            if m.loser == p:
                lost_to.setdefault(m.winner, m)
            elif m.loser in lost_to:
                b.from_match(
                    p,
                    "runback",
                    m,
                    f"Perdió con {b.tag(m.loser)} y le ganó después en {m.tournament}.",
                )
    for f in finishes:
        ev = in_event[(p, f["event_id"])]
        if _big(f) and f["placement"] <= 3:
            b.from_finish(p, "primer_podio", f, f"Terminó {f['placement']}.º en {f['tournament']}.")
        if _big(f) and f["placement"] <= 8:
            b.from_finish(p, "primer_top8", f, f"Terminó {f['placement']}.º en {f['tournament']}.")
        if f["seed"] and _big(f) and insights.tier(f["seed"]) - insights.tier(f["placement"]) >= 3:
            b.from_finish(
                p,
                "py_aguasu",
                f,
                f"Siendo seed {f['seed']} terminó {f['placement']}.º en {f['tournament']}.",
            )
        if f["seed"] and _big(f, 32) and f["seed"] >= 25 and f["placement"] <= 8:
            b.from_finish(
                p,
                "desde_el_fondo",
                f,
                f"Siendo seed {f['seed']} hizo top 8 en {f['tournament']}.",
            )
        if f["seed"] == 1 and _big(f) and f["placement"] > 8:
            b.from_finish(
                p,
                "nerfeado_por_la_trama",
                f,
                f"Era el seed 1 de {f['tournament']} y terminó {f['placement']}.º.",
            )
        if not (_big(f) and ev):
            continue
        last = ev[-1]
        info = ctx.sets.get(last.id)
        if f["placement"] == 1 and last.winner == p:
            _champion(b, p, f, ev)
        if f["placement"] == 2 and last.loser == p and info and info.scored and info.round:
            champion = finish_at.get((last.winner, f["event_id"]))
            if (
                info.round > 0
                and champion
                and champion["placement"] == 1
                and info.loser_score >= 1
                and info.winner_score - info.loser_score == 1
            ):
                b.from_match(
                    p,
                    "casi_kp",
                    last,
                    f"Perdió la gran final de {f['tournament']} contra {b.tag(last.winner)} "
                    f"{info.loser_score}-{info.winner_score}, en la última partida.",
                )


def _champion(b, p, f, ev):
    """Champion of a main event of 16 or more: how they got there."""
    ctx = b.ctx
    losses = [m for m in ev if m.loser == p]
    last = ev[-1]
    if not losses:
        b.from_finish(p, "mbarete", f, f"Ganó {f['tournament']} sin perder un set.", sets=len(ev))
    info = ctx.sets.get(last.id)
    if info and info.scored and info.loser_score == 0 and info.winner_score >= 2:
        b.from_match(
            p,
            "purete",
            last,
            f"Ganó su último set de {f['tournament']} {info.winner_score}-0.",
        )
    rounds = [ctx.sets.get(m.id) for m in ev]
    if any(r is None or r.round is None for r in rounds[-3:]):
        return  # without rounds the path through the bracket is unknown
    # Grand final block: trailing winners-side sets against the same opponent.
    i = len(ev) - 1
    rival = last.loser
    while i >= 0 and rival in (ev[i].winner, ev[i].loser) and rounds[i].round > 0:
        i -= 1
    block = ev[i + 1 :]
    if len(block) >= 2 and block[-2].loser == p and block[-1].winner == p:
        b.from_match(
            p,
            "reset_y_corona",
            last,
            f"Perdió el primer set de la gran final de {f['tournament']} y ganó el reset.",
        )
    if losses and i >= 0 and rounds[i].round < 0 and ev[i].winner == p:
        b.from_match(
            p,
            "puerta_de_atras",
            last,
            f"Ganó {f['tournament']} llegando a la gran final desde la final de losers.",
            losers_final=ev[i].id,
        )


def _career(b, p, mine, finishes):
    data = b.data
    wins = [m for m in mine if m.winner == p]
    if mine:
        b.from_match(p, "bautismo", mine[0], f"Jugó su primer set oficial en {mine[0].tournament}.")
    for n, aid in ((50, "medio_centenar"), (300, "trescientos")):
        m = _nth(wins, n)
        if m:
            b.from_match(p, aid, m, f"Llegó a {n} sets ganados en {m.tournament}.")
    at = _streak_reached(mine, p, 20)
    if at:
        b.give(Award(p, "aplanadora", at, "Ganó 20 sets seguidos."))
    m = _nth([m for m in wins if m.comeback], 20)
    if m:
        b.from_match(p, "nunca_muerto", m, "Ganó 20 sets después de perder la primera partida.")
    top8s = [f for f in finishes if _big(f) and f["placement"] <= 8]
    f = _nth(top8s, 15)
    if f:
        b.from_finish(p, "fijo_top8", f, "Hizo 15 top 8 en eventos principales de 16 o más.")
    tournaments = _distinct_tournaments(finishes)
    for n, aid in ((5, "de_la_casa"), (50, "cincuenta_brackets")):
        f = _nth(tournaments, n)
        if f:
            b.from_finish(p, aid, f, f"Llegó a {n} torneos en {f['tournament']}.")
    if len(tournaments) >= 30:
        first = tournaments[0]["starts_at"]
        for f in tournaments[29:]:
            if f["starts_at"] - first >= timedelta(days=730):
                b.from_finish(p, "tuja", f, "Más de 30 torneos y 2 años en la escena.")
                break
    for prev, f in zip(tournaments, tournaments[1:], strict=False):
        if f["starts_at"] - prev["starts_at"] >= timedelta(days=180):
            b.from_finish(
                p,
                "volvio",
                f,
                f"Volvió en {f['tournament']} después de "
                f"{(f['starts_at'] - prev['starts_at']).days} días.",
            )
            break
    months = defaultdict(list)
    for f in tournaments:
        months[insights.month_of(f["starts_at"])].append(f)
    for month, items in sorted(months.items()):
        if len(items) >= 4:
            b.from_finish(
                p,
                "siempre_en_la_ronda",
                items[3],
                f"Jugó {len(items)} torneos en {insights.month_name(month)}.",
            )
            break
    index = sorted({int(m[:4]) * 12 + int(m[5:]) - 1 for m in months})
    run = 0
    for i, value in enumerate(index):
        run = run + 1 if i and value == index[i - 1] + 1 else 1
        if run == 6:
            month = f"{value // 12}-{value % 12 + 1:02d}"
            b.from_finish(
                p,
                "constancia",
                months[month][0],
                "Jugó al menos un torneo por mes, 6 meses seguidos.",
            )
            break
    titles_by_month = defaultdict(list)
    for f in finishes:
        if _title(f) and f["starts_at"]:
            titles_by_month[insights.month_of(f["starts_at"])].append(f)
    for month, items in sorted(titles_by_month.items()):
        if len(items) >= 2:
            b.from_finish(
                p,
                "doble_corona",
                items[1],
                f"Ganó {items[0]['tournament']} y {items[1]['tournament']} en "
                f"{insights.month_name(month)}.",
            )
            break
    side = [
        f
        for f in finishes
        if not f.get("main", True) and f["placement"] == 1 and (f["entrants"] or 0) >= 8
    ]
    if side and side[0]["starts_at"]:
        later = [
            f
            for f in finishes
            if _big(f)
            and f["placement"] <= 8
            and f["starts_at"]
            and f["starts_at"] > side[0]["starts_at"]
        ]
        if later:
            b.from_finish(
                p,
                "graduado",
                later[0],
                f"Ganó {side[0]['event']} y después hizo top 8 en {later[0]['tournament']}.",
            )
    won_months = insights.month_winners(data).get(str(p), [])
    if len(won_months) >= 3:
        b.give(
            Award(
                p,
                "tricampeon_mes",
                None,
                f"Fue jugador del mes {len(won_months)} veces.",
                dict(months=[m for m, _ in won_months]),
            )
        )
    regions = {insights.region_of(f["city"]): f for f in finishes if f.get("city")}
    if {"central", "cde"} <= set(regions):
        latest = max(regions.values(), key=lambda f: f["starts_at"] or 0)
        b.from_finish(
            p, "en_bici_hasta_cde", latest, "Jugó torneos en Gran Asunción y en Ciudad del Este."
        )


def _rivals(b, p, mine):
    head = defaultdict(list)
    for m in mine:
        head[m.loser if m.winner == p else m.winner].append(m)
    opponents = []
    for m in mine:
        rival = m.loser if m.winner == p else m.winner
        if rival not in opponents:
            opponents.append(rival)
            if len(opponents) == 50:
                b.from_match(p, "conoce_a_todos", m, "Jugó contra 50 rivales distintos.")
    for rival, sets in head.items():
        if len(sets) >= 10:
            b.from_match(
                p,
                "che_raa",
                sets[9],
                f"Jugó {len(sets)} sets contra {b.tag(rival)}.",
                sets=len(sets),
            )
        wins = sum(1 for m in sets if m.winner == p)
        if len(sets) >= 20 and min(wins, len(sets) - wins) >= 0.4 * len(sets):
            b.from_match(
                p,
                "clasico",
                sets[-1],
                f"{wins}-{len(sets) - wins} contra {b.tag(rival)} en {len(sets)} sets.",
            )
        losses = 0
        for m in sets:
            if m.loser == p:
                losses += 1
            else:
                if losses >= 5:
                    b.from_match(
                        p,
                        "exorcismo",
                        m,
                        f"Le ganó a {b.tag(rival)} después de {losses} derrotas seguidas.",
                    )
                losses = 0
    johns = [
        m
        for m in mine
        if m.loser == p
        and (info := b.ctx.sets.get(m.id))
        and info.scored
        and info.loser_score >= 1
        and info.winner_score - info.loser_score == 1
    ]
    m = _nth(johns, 10)
    if m:
        b.from_match(p, "los_johns", m, "Perdió 10 sets en la partida decisiva.")


def _characters(b, p, mine):
    ctx = b.ctx
    for m in mine:
        if m.winner != p:
            continue
        games = ctx.games.get(m.id) or []
        used = {chars.get(p) for _, chars, _ in games if chars.get(p)}
        if len(used) >= 3:
            b.from_match(
                p,
                "jopara",
                m,
                f"Le ganó a {b.tag(m.loser)} usando {', '.join(sorted(used))}.",
                characters=sorted(used),
            )


def _specials(b, p, mine, finishes):
    for m in mine:
        if m.winner == p and _local(m.at).hour < 4:
            b.from_match(
                p,
                "pombero",
                m,
                f"Le ganó a {b.tag(m.loser)} a las {_local(m.at):%H:%M} en {m.tournament}.",
            )
            break
    for f in finishes:
        if _title(f) and f["starts_at"]:
            day = _local(f["starts_at"])
            if day.month == 5 and day.day in (14, 15):
                b.from_finish(p, "independencia", f, f"Ganó {f['tournament']} en fecha patria.")


def _spike(b, ctx, matches_of, in_event, finish_at):
    spike = ctx.subjects.get("spike")
    if spike is None:
        return
    versus = defaultdict(list)
    for m in matches_of.get(spike, []):
        versus[m.loser if m.winner == spike else m.winner].append(m)
    for p, sets in versus.items():
        wins = [m for m in sets if m.winner == p]
        m = _nth(sets, 5)
        if m:
            b.from_match(p, "oposicion", m, f"Jugó {len(sets)} sets oficiales contra Spike.")
        m = _nth(wins, 3)
        if m:
            b.from_match(p, "la_resistencia", m, f"Le ganó {len(wins)} sets oficiales a Spike.")
        lost_events = set()
        for m in sets:
            if m.winner == spike:
                lost_events.add(m.event_id)
            elif m.event_id in lost_events:
                b.from_match(
                    p, "indulto", m, f"Perdió con Spike y le ganó después en {m.tournament}."
                )
        for m in wins:
            # Seeds of the same event, official set, reliable seeding (else seeds are None).
            if not (m.winner_seed and m.loser_seed and m.winner_seed > m.loser_seed):
                continue
            b.from_match(
                p,
                "dictador_caido",
                m,
                f"Siendo seed {m.winner_seed} le ganó a Spike (seed {m.loser_seed}) en "
                f"{m.tournament}.",
            )
            spike_sets = in_event.get((spike, m.event_id)) or []
            eliminated = (
                spike_sets
                and spike_sets[-1].id == m.id
                and finish_at.get((spike, m.event_id)) is not None
            )
            if eliminated:
                b.from_match(
                    p,
                    "golpe_de_estado",
                    m,
                    f"Eliminó a Spike de {m.tournament} siendo seed {m.winner_seed} "
                    f"(Spike era seed {m.loser_seed}).",
                )


def _vbash(b, ctx, matches_of):
    vbash = ctx.subjects.get("vbash")
    if vbash is None:
        return
    for p, picks in ctx.data.picks.items():
        if picks.get(YOSHI, 0) >= 10:
            b.give(Award(p, "todos_somos_vbash", None, f"Jugó {picks[YOSHI]} partidas con Yoshi."))
    for m in ctx.data.matches:
        games = ctx.games.get(m.id) or []
        if not games:
            continue
        p = m.winner
        if m.loser == vbash and any(
            winner == p and chars.get(p) == YOSHI for _, chars, winner in games
        ):
            b.from_match(p, "que_vbash_sos", m, f"Le ganó a vBash con Yoshi en {m.tournament}.")
        if all(set(chars.values()) == {YOSHI} and len(chars) == 2 for _, chars, _ in games):
            b.from_match(
                p, "vbash_contra_vbash", m, f"Ganó un duelo de Yoshis contra {b.tag(m.loser)}."
            )


def _finish(b, ctx):
    """Drop what is not active, then the meta achievements over what remains."""
    active_gates = set(ctx.subjects)
    out = {}
    for key, award in b.out.items():
        entry = catalog.get(award.achievement_id)
        if entry is None or entry.status != "active" or entry.scope != "player":
            continue
        gate = catalog.GATED.get(entry.collection) if entry.collection else None
        if gate and gate not in active_gates:
            continue
        out[key] = award
    per_player = defaultdict(set)
    for p, aid in out:
        per_player[p].add(aid)
    for p, ids in ctx.manual.items():
        per_player[p] |= set(ids)
    if "vbash" in active_gates:
        vbash_ids = {a.id for a in catalog.ACHIEVEMENTS if a.collection == "vbash"}
        for p, ids in per_player.items():
            if len(ids & vbash_ids) >= 3:
                out[(p, "multiverso_vbash")] = Award(
                    p, "multiverso_vbash", None, "Obtuvo 3 logros del Multiverso de vBash."
                )
                ids.add("multiverso_vbash")
    countable = {
        a.id for a in catalog.ACHIEVEMENTS if a.kind == "permanent" and a.id != "coleccionista"
    }
    for p, ids in per_player.items():
        n = len(ids & countable)
        if n >= 25:
            out[(p, "coleccionista")] = Award(
                p, "coleccionista", None, f"Tiene {n} logros permanentes."
            )
    return out
