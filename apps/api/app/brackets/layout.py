"""Where each set of a bracket goes on screen (Mission 25).

Pure: takes the sets of one start.gg phase group with the sets that feed them and returns
columns (one per round) with a `row` for every set, so a set sits halfway between the two
sets its players come from and the connectors can be drawn straight.
"""

import re

ROUNDS = {
    "Winners Quarter-Final": "Cuartos de winners",
    "Winners Semi-Final": "Semifinal de winners",
    "Winners Final": "Final de winners",
    "Losers Quarter-Final": "Cuartos de losers",
    "Losers Semi-Final": "Semifinal de losers",
    "Losers Final": "Final de losers",
    "Grand Final": "Gran final",
    "Grand Final Reset": "Gran final (reset)",
}


def round_label(text):
    """start.gg's round name in Spanish."""
    if not text:
        return None
    if text in ROUNDS:
        return ROUNDS[text]
    found = re.fullmatch(r"(Winners|Losers) Round (\d+)", text)
    if found:
        return f"{found[1]} ronda {found[2]}"
    found = re.fullmatch(r"Round (\d+)", text)
    return f"Ronda {found[1]}" if found else text


def arrange(nodes, kind="DOUBLE_ELIMINATION"):
    """{"winners": [column], "losers": [column], "height": rows} for one phase group.

    Each node is a dict with `id`, `round` (start.gg: negative on the losers side),
    `label`, `shown` (False for byes and empty slots, which still shape the tree) and
    `prereqs`, the (set id, placement) pairs its slots come from. Only shown nodes are
    returned, each with a `row`.
    """
    by = {n["id"]: n for n in nodes}
    result = dict(winners=[], losers=[], height=0)
    for side, inside in (("winners", lambda r: r > 0), ("losers", lambda r: r < 0)):
        mine = {i: n for i, n in by.items() if n["round"] is not None and inside(n["round"])}
        if not any(n["shown"] for n in mine.values()):
            continue
        rows = {}
        if kind == "ROUND_ROBIN":
            for n in mine.values():
                if n["shown"]:
                    rows[n["id"]] = None
            columns = _columns(mine, rows)
            for column in columns:
                for place, item in enumerate(column["sets"]):
                    item["row"] = place
        else:
            _rows(mine, rows)
            columns = _columns(mine, rows)
        result[side] = columns
        result["height"] = max(
            [result["height"]] + [s["row"] + 1 for c in columns for s in c["sets"]]
        )
    return result


def _rows(mine, rows):
    # The winner of a set feeds the next one on the same side; losers dropping from
    # winners do not shape the losers tree.
    kids = {
        i: list(dict.fromkeys(p for p, place in n["prereqs"] if place == 1 and p in mine))
        for i, n in mine.items()
    }
    fed = {k for ks in kids.values() for k in ks}
    roots = sorted((i for i in mine if i not in fed), key=lambda i: -abs(mine[i]["round"]))
    leaf = [0]
    seen = set()

    def place(i):
        if i in seen:
            return rows.get(i)
        seen.add(i)
        below = [r for r in (place(k) for k in kids[i]) if r is not None]
        row = sum(below) / len(below) if below else None
        if mine[i]["shown"]:
            if row is None:
                row = leaf[0]
                leaf[0] += 1
            rows[i] = row
        return row

    for root in roots:
        place(root)
    # Where each shown set's winner goes next, past byes, for the connector lines.
    parent = {k: i for i, ks in kids.items() for k in ks}
    for i in list(rows):
        up = parent.get(i)
        while up is not None and up not in rows:
            up = parent.get(up)
        mine[i]["to"] = up
    if rows:
        low = min(rows.values())
        for i in rows:
            rows[i] -= low


def _columns(mine, rows):
    rounds = sorted({mine[i]["round"] for i in rows}, key=abs)
    columns = []
    for r in rounds:
        items = sorted(
            (i for i in rows if mine[i]["round"] == r),
            key=lambda i: (rows[i] is None, rows[i] or 0, str(i)),
        )
        columns.append(
            dict(
                round=r,
                label=round_label(mine[items[0]].get("label")),
                sets=[
                    {k: v for k, v in mine[i].items() if k not in ("prereqs", "shown")}
                    | dict(row=rows[i])
                    for i in items
                ],
            )
        )
    return columns


def seed_order(size):
    """Bracket positions of seeds 1..size (a power of two): 1, size, …, so 1 and 2 meet last."""
    order = [1]
    while len(order) < size:
        total = len(order) * 2 + 1
        order = [x for seed in order for x in (seed, total - seed)]
    return order
