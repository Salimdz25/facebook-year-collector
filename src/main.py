import asyncio
from datetime import date

from apify import Actor

from .windows import choose_window, iso_utc, normalize_page_url, storage_suffix

SCRAPER = "apify/facebook-posts-scraper"


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        page = normalize_page_url(actor_input["facebookUrl"])
        year = int(actor_input.get("year", 2025))
        limit = int(actor_input.get("resultsLimit", 50))
        if not 2004 <= year <= 2100 or limit < 1:
            raise ValueError("year must be 2004–2100 and resultsLimit must be positive")

        suffix = storage_suffix(page, year)
        store = await Actor.open_key_value_store(name=f"fb-progress-{suffix}")
        state = await store.get_value("CURSOR") or {
            "next_date": date(year, 1, 1).isoformat(), "phase": "two", "limit": limit
        }
        start = date.fromisoformat(state["next_date"])
        after_last_day = date(year + 1, 1, 1)
        if start >= after_last_day:
            Actor.log.info(f"Year {year} complete for {page}. Nothing to scrape.")
            return

        # A changed cap invalidates an earlier tentative result.
        if state.get("limit") != limit:
            state = {"next_date": start.isoformat(), "phase": "two", "limit": limit}
            await store.set_value("CURSOR", state)
        if state.get("phase") == "paused":
            Actor.log.warning("One day reached the cap. Increase resultsLimit to resume.")
            return

        phase = state.get("phase", "two")
        width = {"one": 1, "two": 2, "three": 3}[phase]
        first, end = choose_window(start, width, year)
        scraper_input = {
            "captionText": False,
            "onlyPostsNewerThan": iso_utc(first),
            "onlyPostsOlderThan": iso_utc(end),
            "resultsLimit": limit,
            "startUrls": [{"url": page}],
        }
        Actor.log.info(f"One scraper call: {first} to {end} (UTC); phase {phase}")
        run = await Actor.call(SCRAPER, scraper_input)
        if run is None or run.status != "SUCCEEDED":
            raise RuntimeError(f"Scraper did not succeed: {run}")
        items = [item async for item in Actor.apify_client.dataset(run.default_dataset_id).iterate_items()]
        count = len(items)

        if phase == "two" and count >= limit:
            await store.set_value("CURSOR", {
                "next_date": start.isoformat(), "phase": "one", "limit": limit
            })
            Actor.log.warning("Two days reached cap; next scheduled run will try one day")
            return

        if phase == "two" and end < after_last_day:
            # A two-day result is only tentative until the following scheduled run.
            await store.set_value("CURSOR", {
                "next_date": start.isoformat(), "phase": "three", "limit": limit,
                "candidate_end": end.isoformat(),
                "candidate_dataset_id": run.default_dataset_id,
                "candidate_run_id": run.id,
                "candidate_count": count,
            })
            Actor.log.info("Under cap; next scheduled run will add a third day")
            return

        if phase == "one" and count >= limit:
            await store.set_value("CURSOR", {
                "next_date": start.isoformat(), "phase": "paused", "limit": limit
            })
            Actor.log.error("One day reached cap; collection paused until resultsLimit increases")
            return

        source_id, source_run_id = run.default_dataset_id, run.id
        if phase == "three" and count >= limit:
            # Use the completed two-day source run, without another scraper call.
            source_id = state["candidate_dataset_id"]
            source_run_id = state["candidate_run_id"]
            end = date.fromisoformat(state["candidate_end"])
            items = [item async for item in Actor.apify_client.dataset(source_id).iterate_items()]
            count = len(items)
            if count >= limit:
                raise RuntimeError("Saved two-day candidate is unexpectedly at the cap")

        # Publish before advancing. If a write fails, the same window can be retried.
        dataset = await Actor.open_dataset(name=f"fb-posts-{suffix}")
        if items:
            await dataset.push_data(items)
        await store.set_value("CURSOR", {
            "next_date": end.isoformat(), "phase": "two", "limit": limit,
            "last_window_start": first.isoformat(),
            "last_window_end_exclusive": end.isoformat(),
            "last_source_run_id": source_run_id,
            "last_source_dataset_id": source_id,
            "last_count": count,
            "combined_dataset_id": dataset.id,
        })
        await Actor.push_data({
            "facebook_url": page, "year": year,
            "window_start": first.isoformat(), "window_end_exclusive": end.isoformat(),
            "count": count, "source_run_id": source_run_id,
            "combined_dataset_id": dataset.id, "next_date": end.isoformat(),
        })
        Actor.log.info(f"Saved {count} posts; next start: {end}")


if __name__ == "__main__":
    asyncio.run(main())
