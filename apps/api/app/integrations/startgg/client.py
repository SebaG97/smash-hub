import asyncio
import random
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

ENDPOINT = "https://api.start.gg/gql/alpha"
DOCUMENTS = Path(__file__).parent / "graphql"


class ImportFailure(Exception):
    """Only fixed, safe codes may cross the CLI/job boundary."""


def parse_slug(value: str) -> str:
    value = value.strip()
    if "://" in value:
        try:
            url = urlsplit(value)
            if (
                url.scheme != "https"
                or url.hostname not in {"start.gg", "www.start.gg"}
                or url.username
                or url.password
                or url.port not in {None, 443}
            ):
                raise ValueError
            match = re.fullmatch(r"/tournament/([A-Za-z0-9][A-Za-z0-9-]{0,149})/?", url.path)
            if not match:
                raise ValueError
            return match[1]
        except ValueError:
            raise ImportFailure("invalid_tournament_url") from None
    value = value.removeprefix("tournament/")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,149}", value):
        raise ImportFailure("invalid_tournament_slug")
    return value


class StartGGClient:
    def __init__(
        self,
        token: SecretStr | None,
        *,
        transport=None,
        sleep=asyncio.sleep,
        clock=time.monotonic,
        interval=1.0,
    ):
        if token is None or not token.get_secret_value().strip():
            raise ImportFailure("startgg_token_missing")
        self.http = httpx.AsyncClient(
            headers={"Authorization": "Bearer " + token.get_secret_value()},
            timeout=httpx.Timeout(30, connect=5),
            follow_redirects=False,
            transport=transport,
        )
        self.sleep, self.clock, self.interval = sleep, clock, interval
        self.last = float("-inf")
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.http.aclose()

    async def query(self, document: str, variables: dict) -> dict:
        query = (DOCUMENTS / (document + ".graphql")).read_text(encoding="utf-8-sig")
        async with self.lock:
            for attempt in range(4):
                await self.sleep(max(0, self.interval - (self.clock() - self.last)))
                self.last = self.clock()
                retry_after = 0
                try:
                    response = await self.http.post(
                        ENDPOINT, json={"query": query, "variables": variables}
                    )
                    if response.status_code == 429 or response.status_code >= 500:
                        header = response.headers.get("Retry-After", "0")
                        try:
                            retry_after = max(0, float(header))
                        except ValueError:
                            try:
                                retry_after = max(
                                    0,
                                    (
                                        parsedate_to_datetime(header) - datetime.now(UTC)
                                    ).total_seconds(),
                                )
                            except (ValueError, TypeError, OverflowError):
                                retry_after = 0
                        if retry_after > 120:
                            raise ImportFailure("startgg_retry_later")
                        code = (
                            "startgg_rate_limited"
                            if response.status_code == 429
                            else "startgg_http_error"
                        )
                    elif response.status_code != 200:
                        raise ImportFailure("startgg_http_error")
                    else:
                        try:
                            payload = response.json()
                        except ValueError:
                            raise ImportFailure("startgg_invalid_json") from None
                        if not isinstance(payload, dict):
                            raise ImportFailure("startgg_invalid_response")
                        if payload.get("errors"):
                            # Partial GraphQL data must never be committed as complete.
                            raise ImportFailure("startgg_graphql_error")
                        if payload.get("success") is False:
                            if "rate limit" in str(payload.get("message", "")).lower():
                                code = "startgg_rate_limited"
                            else:
                                raise ImportFailure("startgg_provider_error")
                        elif isinstance(payload.get("data"), dict):
                            return payload["data"]
                        else:
                            raise ImportFailure("startgg_invalid_response")
                except (httpx.TimeoutException, httpx.TransportError):
                    code = "startgg_transport_error"
                if attempt == 3:
                    raise ImportFailure(code)
                await self.sleep(max(retry_after, 2**attempt + random.uniform(0, 1)))
        raise ImportFailure("startgg_unavailable")

    async def pages(
        self,
        document: str,
        root: str,
        connection: str,
        external_id: str,
        *,
        variables: dict | None = None,
    ) -> list:
        result, seen, expected = [], set(), None
        for page in range(1, 10001):
            data = await self.query(
                document, {"id": external_id, "page": page, "perPage": 10, **(variables or {})}
            )
            try:
                conn = data[root][connection]
                info, nodes = conn["pageInfo"], conn["nodes"]
                total, pages = info["total"], info["totalPages"]
                if (
                    type(total) is not int
                    or type(pages) is not int
                    or total < 0
                    or pages < 0
                    or pages > 10000
                    or not isinstance(nodes, list)
                    or len(nodes) > 10
                    or (expected is not None and expected != (total, pages))
                ):
                    raise ValueError
                expected = total, pages
                for node in nodes:
                    key = str(node["id"])
                    if key in seen or node["id"] is None:
                        raise ValueError
                    seen.add(key)
                    result.append(node)
                if page >= pages:
                    if len(result) != total:
                        raise ValueError
                    return result
                if not nodes:
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                raise ImportFailure("startgg_incomplete_pagination") from None
        raise ImportFailure("startgg_pagination_limit")

    async def download(self, slug: str) -> dict:
        data = await self.query("tournament", {"slug": parse_slug(slug)})
        tournament = data.get("tournament")
        if not tournament:
            raise ImportFailure("startgg_tournament_not_found")
        participants = await self.pages(
            "participants", "tournament", "participants", str(tournament["id"])
        )
        if len(tournament.get("events") or []) >= 500:
            raise ImportFailure("startgg_event_limit_reached")
        events = []
        for reference in tournament.get("events") or []:
            event = (await self.query("event", {"id": str(reference["id"])})).get("event")
            if not event:
                raise ImportFailure("startgg_event_missing")
            event = dict(event)
            for connection in ("entrants", "standings", "sets"):
                event[connection] = await self.pages(
                    connection, "event", connection, str(event["id"])
                )
            # start.gg omits INVALID sets by default, including unused GF resets.
            # Fetch that state explicitly, validate its pagination, and retain its IDs.
            invalid = await self.pages(
                "sets", "event", "sets", str(event["id"]), variables={"states": [5]}
            )
            by_id = {str(row["id"]): row for row in event["sets"]}
            for row in invalid:
                key = str(row["id"])
                if key in by_id and by_id[key] != row:
                    raise ImportFailure("startgg_inconsistent_set_snapshot")
                by_id[key] = row
            event["sets"] = list(by_id.values())
            events.append(event)
        return {"tournament": tournament, "participants": participants, "events": events}
