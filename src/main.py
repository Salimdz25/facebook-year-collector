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
        max_days = int(actor_input.get("maxDays", 10))
        if not 2004 <= year <= 2100 or limit < 1 or not 1 <= max_days <= 31:
            raise ValueError("year must be 2004–2100, resultsLimit positive, maxDays 1–31")

        suffix = storage_suffix(page, year)
        store = await Actor.open_key_value_store(name=f"fb-progress-{suffix}")
        state = await store.get_value("CURSOR") or {
            "next_date": date(year, 1, 1).isoformat(),
            "width": max_days, "limit": limit, "max_days": max_days
        }
        start = date.fromisoformat(state["next_date"])
        after_last_day = date(year + 1, 1, 1)
        if start >= after_last_day:
            Actor.log.info(f"Year {year} complete for {page}. Nothing to scrape.")
            return

        # Migrate a tentative result from the earlier 2/3-day version by
        # retrying its start date. No posts had been published for that window.
        if (state.get("limit") != limit or state.get("max_days") != max_days
                or "width" not in state):
            state = {"next_date": start.isoformat(), "width": max_days,
                     "limit": limit, "max_days": max_days}
            await store.set_value("CURSOR", state)
        if state.get("paused"):
            Actor.log.warning("One day reached the cap. Increase resultsLimit to resume.")
            return

        width = int(state["width"])
        first, end = choose_window(start, width, year)
        scraper_input = {
            "captionText": False,
            "onlyPostsNewerThan": iso_utc(first),
            "onlyPostsOlderThan": iso_utc(end),
            "resultsLimit": limit,
            "startUrls": [{"url": page}],
        }
        Actor.log.info(f"One scraper call: {first} to {end} (UTC); {width} days requested")
        run = await Actor.call(SCRAPER, scraper_input)
        if run is None or run.status != "SUCCEEDED":
            raise RuntimeError(f"Scraper did not succeed: {run}")
        items = [item async for item in Actor.apify_client.dataset(run.default_dataset_id).iterate_items()]
        count = len(items)

        if count >= limit:
            actual_days = (end - first).days
            if actual_days > 1:
                next_width = max(1, actual_days // 2)
                await store.set_value("CURSOR", {
                    "next_date": start.isoformat(), "width": next_width,
                    "limit": limit, "max_days": max_days,
                })
                Actor.log.warning(f"Cap reached; next scheduled run will try {next_width} days")
                return
            await store.set_value("CURSOR", {
                "next_date": start.isoformat(), "width": 1,
                "limit": limit, "max_days": max_days, "paused": True,
            })
            Actor.log.error("One day reached cap; collection paused until resultsLimit increases")
            return

        source_id, source_run_id = run.default_dataset_id, run.id

        # Publish before advancing. If a write fails, the same window can be retried.
        dataset = await Actor.open_dataset(name=f"fb-posts-{suffix}")
        if items:
            await dataset.push_data(items)
        await store.set_value("CURSOR", {
            "next_date": end.isoformat(), "width": max_days,
            "limit": limit, "max_days": max_days,
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
