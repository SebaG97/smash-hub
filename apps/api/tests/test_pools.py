"""Seeding by pools (Mission 29). Synthetic data only."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.seeding import pools

# start.gg's snake over two pools: 1, 4, 5 in pool A; 2, 3, 6 in pool B.
FOUND = dict(
    phase="Pools",
    groups=[dict(id="ga", name="1"), dict(id="gb", name="2")],
    seeds=[
        dict(seed=1, group="ga", pool_seed=1, player_id="10", tag="Ace"),
        dict(seed=2, group="gb", pool_seed=1, player_id="20", tag="Bee"),
        dict(seed=3, group="gb", pool_seed=2, player_id="30", tag="Cid"),
        dict(seed=4, group="ga", pool_seed=2, player_id="50", tag="Eve"),
        dict(seed=5, group="ga", pool_seed=3, player_id="40", tag="Dot"),
        dict(seed=6, group="gb", pool_seed=3, player_id="99", tag="Nuevo"),
    ],
    pairs=[[4, 5], [3, 6]],
)


def row(seed, player, tag, rating=1500):
    return dict(seed=seed, player_id=player, gamer_tag=tag, prefix=None, mains=[], rating=rating)


ROWS = [
    row(1, "10", "Ace", 1800),
    row(2, "20", "Bee", 1700),
    row(3, "30", "Cid", 1600),
    row(4, "40", "Dot", 1500),
    row(5, "50", "Eve", 1400),
    row(6, "60", "Fin", 1300),
]


def test_the_hub_seeding_is_laid_on_startgg_pools():
    hub = {"40": "dot", "50": "eve"}
    now = datetime(2026, 11, 1, tzinfo=UTC)
    rematch = SimpleNamespace(winner="dot", loser="eve", at=now, tournament="SaN's 10")
    old = SimpleNamespace(winner="eve", loser="dot", at=now - timedelta(days=200), tournament="X")
    result = pools.build(
        ROWS,
        FOUND,
        hub=hub,
        teams={"dot": "bg", "eve": "bg"},
        ranked=["dot"],
        matches=[old, rematch],
    )
    a, b = result["pools"]
    assert (a["name"], [p["tag"] for p in a["players"]]) == ("Pool 1", ["Ace", "Dot", "Eve"])
    assert [p["tag"] for p in b["players"]] == ["Bee", "Cid", "Fin"]
    assert a["top20"] == 1 and a["rating"] == 1567
    # Hub seed 4 is Dot, but start.gg has Eve there: the organizers see both.
    dot = a["players"][1]
    assert (dot["seed"], dot["pool_seed"], dot["startgg_seed"], dot["ranking"]) == (4, 2, 5, 1)
    texts = [w["text"] for w in result["warnings"]]
    assert texts == [
        "Compañeros de equipo en primera ronda: Dot (seed 4) y Eve (seed 5).",
        "Revancha en primera ronda: Dot (seed 4) y Eve (seed 5) se cruzaron en SaN's 10.",
    ]
    assert result["missing"] == ["Nuevo"] and result["outside"] == []


def test_more_players_than_startgg_spots_are_listed_apart():
    result = pools.build(ROWS + [row(7, "70", "Gus")], FOUND)
    assert [p["tag"] for p in result["outside"]] == ["Gus"]


class Session:
    def __init__(self):
        self.added = []

    def query(self, model):
        return self

    def filter(self, *args):
        return self

    def delete(self):
        self.added.clear()

    def add(self, item):
        self.added.append(item)


def test_adopt_copies_startgg_order_and_sends_the_rest_to_the_end():
    session, audits = Session(), []
    project = SimpleNamespace(id="p")
    result = pools.adopt(session, project, ROWS, FOUND, "Org", lambda *a, **kw: audits.append(kw))
    pinned = {o.startgg_player_id: o.seed for o in session.added}
    assert pinned == {"10": 1, "20": 2, "30": 3, "50": 4, "40": 5, "60": 7}
    assert result == dict(placed=5, missing=["Nuevo"], not_signed_up=["Fin"])
    assert audits == [dict(placed=5, missing=1)]
