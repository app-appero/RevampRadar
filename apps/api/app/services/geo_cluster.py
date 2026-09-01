from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from random import Random
from uuid import UUID

_HIGH = {"HIGH", "VERY_HIGH"}


@dataclass(frozen=True)
class GeoMember:
    company_id: UUID
    name: str
    latitude: float
    longitude: float
    city: str | None
    category: str | None
    opportunity_score: int | None
    website_score: int | None
    priority: str | None
    has_app: bool
    has_website: bool


@dataclass(frozen=True)
class ClusterSummary:
    id: int
    size: int
    label: str
    centroid_lat: float
    centroid_lon: float
    avg_opportunity_score: float | None
    high_share: float
    app_share: float
    no_site_share: float
    top_city: str | None
    top_category: str | None
    member_ids: tuple[UUID, ...]


def choose_k(n: int) -> int:
    if n < 3:
        return 1
    return min(6, max(2, round(n**0.5)))


def kmeans(coords: list[tuple[float, float]], k: int, *, rounds: int = 15, seed: int = 42) -> list[int]:
    n = len(coords)
    if n == 0:
        return []
    if k <= 1 or n == 1:
        return [0] * n
    k = min(k, n)
    rng = Random(seed)
    order = list(range(n))
    rng.shuffle(order)
    centroids = [coords[i] for i in order[:k]]
    labels = [0] * n
    for _ in range(rounds):
        changed = False
        for i, point in enumerate(coords):
            best = min(range(k), key=lambda cluster: _distance(point, centroids[cluster]))
            if labels[i] != best:
                labels[i] = best
                changed = True
        for cluster in range(k):
            members = [coords[i] for i, label in enumerate(labels) if label == cluster]
            if members:
                centroids[cluster] = (
                    sum(item[0] for item in members) / len(members),
                    sum(item[1] for item in members) / len(members),
                )
            else:
                centroids[cluster] = coords[rng.randrange(n)]
        if not changed:
            break
    return labels


def cluster_members(members: list[GeoMember]) -> list[ClusterSummary]:
    if not members:
        return []
    coords = [(item.latitude, item.longitude) for item in members]
    labels = kmeans(coords, choose_k(len(members)))
    grouped: dict[int, list[GeoMember]] = {}
    for member, label in zip(members, labels, strict=True):
        grouped.setdefault(label, []).append(member)
    summaries = [_summarize(label, group) for label, group in grouped.items()]
    summaries.sort(key=lambda item: (-item.size, item.id))
    return [_renumber(index, item) for index, item in enumerate(summaries)]


def _renumber(index: int, summary: ClusterSummary) -> ClusterSummary:
    return ClusterSummary(
        id=index,
        size=summary.size,
        label=summary.label,
        centroid_lat=summary.centroid_lat,
        centroid_lon=summary.centroid_lon,
        avg_opportunity_score=summary.avg_opportunity_score,
        high_share=summary.high_share,
        app_share=summary.app_share,
        no_site_share=summary.no_site_share,
        top_city=summary.top_city,
        top_category=summary.top_category,
        member_ids=summary.member_ids,
    )


def _summarize(label: int, members: list[GeoMember]) -> ClusterSummary:
    cities = Counter(item.city for item in members if item.city)
    categories = Counter(item.category for item in members if item.category)
    top_city = cities.most_common(1)[0][0] if cities else None
    top_category = categories.most_common(1)[0][0] if categories else None
    scores = [item.opportunity_score for item in members if item.opportunity_score is not None]
    avg = round(sum(scores) / len(scores), 1) if scores else None
    high_share = round(sum(1 for item in members if item.priority in _HIGH) / len(members), 2)
    app_share = round(sum(1 for item in members if item.has_app) / len(members), 2)
    no_site_share = round(sum(1 for item in members if not item.has_website) / len(members), 2)
    return ClusterSummary(
        id=label,
        size=len(members),
        label=_label(top_category, top_city, avg, app_share, no_site_share),
        centroid_lat=sum(item.latitude for item in members) / len(members),
        centroid_lon=sum(item.longitude for item in members) / len(members),
        avg_opportunity_score=avg,
        high_share=high_share,
        app_share=app_share,
        no_site_share=no_site_share,
        top_city=top_city,
        top_category=top_category,
        member_ids=tuple(item.company_id for item in members),
    )


def _label(
    category: str | None,
    city: str | None,
    avg: float | None,
    app_share: float,
    no_site_share: float,
) -> str:
    cat_bit = category or "misto"
    city_bit = city or "più località"
    if avg is None:
        score_bit = "senza score"
    elif avg >= 70:
        score_bit = "opportunità alta"
    elif avg >= 50:
        score_bit = "opportunità media"
    else:
        score_bit = "opportunità bassa"
    app_bit = "con app" if app_share >= 0.3 else "poche app"
    parts = [cat_bit, city_bit, score_bit, app_bit]
    if no_site_share >= 0.3:
        parts.append("molti senza sito")
    elif no_site_share > 0:
        parts.append("alcuni senza sito")
    return " · ".join(parts)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
