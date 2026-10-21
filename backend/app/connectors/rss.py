"""Connecteur générique RSS/Atom avec requêtes conditionnelles (ETag / Last-Modified)."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone

import feedparser

from app.connectors.base import CollectState, Connector, FetchResult, RawItem
from app.services.net import FetchError, fetch


def _to_datetime(struct) -> datetime | None:  # noqa: ANN001
    if not struct:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


class RssConnector(Connector):
    type = "rss"
    label = "Flux RSS / Atom"
    access_method = "HTTP GET du flux public, requête conditionnelle (ETag, If-Modified-Since)"
    limits = (
        "Le flux ne contient que les N derniers éléments publiés par la source ; "
        "pas de pagination ni d'historique. Une fréquence trop faible peut manquer des éléments."
    )
    terms = "Respect de robots.txt et des conditions d'utilisation du site ; stockage limité au titre, résumé du flux et lien."
    default_interval_minutes = 30

    def fetch(self, state: CollectState) -> FetchResult:
        headers = {"Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.5"}
        if state.etag:
            headers["If-None-Match"] = state.etag
        if state.last_modified:
            headers["If-Modified-Since"] = state.last_modified

        response = fetch(self.url, headers=headers)
        if response.status == 304:
            return FetchResult(not_modified=True, new_state=state)
        if response.status in (401, 403, 404, 410):
            raise FetchError(f"HTTP {response.status} sur le flux", permanent=True, status=response.status)
        if response.status == 429 or response.status >= 500:
            raise FetchError(f"HTTP {response.status} (temporaire)", status=response.status)
        if response.status != 200:
            raise FetchError(f"HTTP {response.status} inattendu", status=response.status)

        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise FetchError(
                f"Flux illisible : {type(parsed.bozo_exception).__name__}", permanent=True
            )

        feed_language = (parsed.feed.get("language") or "")[:2].lower() or None
        items: list[RawItem] = []
        warnings: list[str] = []
        for entry in parsed.entries:
            link = entry.get("link")
            title = entry.get("title")
            if not link or not title:
                warnings.append("Entrée ignorée : lien ou titre manquant")
                continue
            items.append(
                RawItem(
                    url=link,
                    title=title,
                    summary=entry.get("summary", "") or "",
                    author=entry.get("author"),
                    published_at=_to_datetime(entry.get("published_parsed") or entry.get("updated_parsed")),
                    language=feed_language,
                    guid=entry.get("id"),
                )
            )

        return FetchResult(
            items=items,
            new_state=CollectState(
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
            ),
            feed_language=feed_language,
            warnings=warnings,
        )
