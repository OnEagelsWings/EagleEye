"""Offline adapter for World Bank global electricity access aggregates.

Only numeric global annual observations are accepted. No network access,
automatic publication, author metadata or arbitrary source URLs.
"""
import json
import math
import uuid
from bridge import validate, MAX, unique_object, reject_constant

INDICATOR = "EG.ELC.ACCS.ZS"
SOURCE = "https://data.worldbank.org/indicator/EG.ELC.ACCS.ZS"
TOPIC = "World electricity access (% of population)"


def adapt(raw, *, synthetic):
    """Convert a single World Bank API page into an unsigned staging record."""
    if type(synthetic) is not bool or not isinstance(raw, bytes) or len(raw) > MAX:
        raise ValueError("invalid adapter input")
    try:
        page = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid input") from exc
    if not isinstance(page, list) or len(page) != 2:
        raise ValueError("invalid page")
    meta, rows = page
    if (not isinstance(meta, dict) or type(meta.get("pages")) is not int
            or meta["pages"] != 1 or type(meta.get("page")) is not int
            or meta["page"] != 1 or not isinstance(rows, list)
            or not 1 <= len(rows) <= 200):
        raise ValueError("expected one complete page")
    observations = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid observation")
        indicator = row.get("indicator")
        year, value = row.get("date"), row.get("value")
        if (not isinstance(indicator, dict) or indicator.get("id") != INDICATOR
                or row.get("countryiso3code") != "WLD"
                or not isinstance(year, str) or len(year) != 4
                or not year.isascii() or not year.isdigit()
                or not 1900 <= int(year) <= 2100 or year in observations):
            raise ValueError("unexpected series or year")
        if value is not None and (type(value) not in (int, float)
                                  or not 0 <= value <= 100 or not math.isfinite(value)):
            raise ValueError("invalid percentage")
        observations[year] = value
    summary = "\n".join(year + ": " + ("missing" if value is None else str(value))
                        for year, value in sorted(observations.items()))
    if synthetic:
        summary = "Synthetic fixture; not real observations.\n" + summary
    ident = uuid.uuid5(uuid.NAMESPACE_URL, SOURCE + "\n" + summary)
    result = json.dumps({"schema": 1, "id": str(ident), "kind": "research_result",
                         "classification": "public-topic", "topic": TOPIC,
                         "summary": summary, "sources": [{"title": "World Bank indicator",
                         "url": SOURCE}], "synthetic": synthetic},
                        sort_keys=True, ensure_ascii=False).encode("utf-8")
    validate(result)
    return result
