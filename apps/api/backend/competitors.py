"""
Competitor-intelligence tool — "who do we run into, and who beats us?"

Answers questions like "who are our biggest competitors in South Dakota?" or "who beats CLIENT most
often?". Computed from the master CSV: for every project CLIENT bid on, look at the other bidders and
whether they out-ranked CLIENT (a lower rank number = a better/lower bid).
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .config import MASTER_CSV

_STATE_ALIASES = {"sd": "south dakota", "nd": "north dakota", "mn": "minnesota",
                  "ia": "iowa", "ne": "nebraska", "mt": "montana"}


@lru_cache(maxsize=1)
def _head_to_head() -> pd.DataFrame:
    """One row per (competitor, project CLIENT also bid): did the competitor out-rank CLIENT?"""
    df = pd.read_csv(MASTER_CSV, dtype=str, low_memory=False)
    df["rank"] = pd.to_numeric(df["Bid_Rank"], errors="coerce")
    df["state_l"] = df["State"].astype(str).str.strip().str.lower()

    client = (df[df["Is_CLIENT"] == "TRUE"][["Contract_Id", "rank"]]
           .rename(columns={"rank": "client_rank"}).drop_duplicates("Contract_Id"))
    others = (df[df["Is_CLIENT"] != "TRUE"]
              .merge(client, on="Contract_Id", how="inner")        # only projects CLIENT also bid
              .dropna(subset=["rank", "client_rank"]))
    others["beat_client"] = others["rank"] < others["client_rank"]
    return others


def query_competitors(state: str | None = None, top_n: int = 5) -> dict:
    """CLIENT's most-frequent competitors (optionally in one state) and how often they beat CLIENT."""
    h2h = _head_to_head()
    scope = "all states"
    if state:
        key = _STATE_ALIASES.get(state.strip().lower(), state.strip().lower())
        h2h = h2h[h2h["state_l"] == key]
        scope = state
    if len(h2h) == 0:
        return {"scope": scope, "n_competitors": 0,
                "note": "No shared projects found for that scope."}

    g = (h2h.groupby("Bidder_Clean_Name")
         .agg(shared=("Contract_Id", "nunique"), beat=("beat_client", "sum")).reset_index())
    g = g[g["shared"] >= 5]                       # ignore one-off encounters
    g["beat_pct"] = (g["beat"] / g["shared"] * 100).round(1)
    g = g.sort_values("shared", ascending=False).head(top_n)

    return {
        "scope": scope,
        "n_competitors": len(g),
        "competitors": [{"name": r["Bidder_Clean_Name"], "shared_projects": int(r["shared"]),
                         "beat_client_count": int(r["beat"]), "beat_client_pct": r["beat_pct"]}
                        for _, r in g.iterrows()],
        "note": "'shared' = projects both CLIENT and they bid; 'beat_client_pct' = share of those where "
                "they out-bid CLIENT (lower rank). Ranked by how often CLIENT runs into them.",
    }


TOOL_SCHEMA = {
    "name": "query_competitors",
    "description": (
        "Look up CLIENT's competitors — who CLIENT most frequently bids against (optionally in one state) "
        "and how often each beats CLIENT. Use for questions like 'who are our biggest competitors in "
        "South Dakota', 'who beats us most often'. Computed from CLIENT's shared-project bidding record."),
    "input_schema": {
        "type": "object",
        "properties": {
            "state": {"type": "string", "description": "Full name or 2-letter code, e.g. 'SD'. Omit for all."},
            "top_n": {"type": "integer", "description": "How many competitors to return (default 5)."},
        },
    },
}


def run(tool_input: dict) -> dict:
    return query_competitors(state=tool_input.get("state"), top_n=tool_input.get("top_n", 5))
