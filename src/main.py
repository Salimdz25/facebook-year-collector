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
        state = await store.get_value("CURSOR") or {"next_date": date(year, 1, 1).isoformat()}
        start = date.fromisoformat(state["next_date"])
        after_last_day = date(year + 1, 1, 1)
        if start >= after_last_day:
            Actor.log.info(f"Year {year} complete for {page}. Nothing to scrape.")
            return

        # Start with two days, extend by one when below the result cap.
        # Keep the completed two-day result if the third day hits the cap.
        width = 2
        accepted = None
        while True:
            first, end = choose_window(start, width, year)
            scraper_input = {
                "captionText": False,
                "onlyPostsNewerThan": iso_utc(first),
                "onlyPostsOlderThan": iso_utc(end),
                "resultsLimit": limit,
                "startUrls": [{"url": page}],
            }
            Actor.log.info(f"Scraping {first} to {end} (UTC), {width}-day window")
            run = await Actor.call(SCRAPER, scraper_input)
            if run is None or run.status != "SUCCEEDED":
                raise RuntimeError(f"Scraper did not succeed: {run}")

            # The source Actor's dataset remains accessible by run ID as well.
            source_id = run.default_dataset_id
            items = [item async for item in Actor.apify_client.dataset(source_id).iterate_items()]
            if len(items) >= limit:
                if width == 1:
                    raise RuntimeError(
                        f"At least {limit} posts in one day ({first}); "
                        "increase resultsLimit in the Actor input and rerun. Cursor was not advanced."
                    )
                if width == 3 and accepted is not None:
                    Actor.log.warning("Three-day window capped; retaining the two-day result")
                    first, end, items, run, source_id = accepted
                    break
                Actor.log.warning(f"Limit reached ({len(items)}); retrying one day")
                width = 1
                continue
            if width == 2 and end < after_last_day:
                accepted = (first, end, items, run, source_id)
                width = 3
                continue
            break

        # Publish before advancing. A failed write leaves the cursor on this window.
        dataset = await Actor.open_dataset(name=f"fb-posts-{suffix}")
        if items:
            await dataset.push_data(items)
        await store.set_value("CURSOR", {
            "next_date": end.isoformat(),
            "last_window_start": first.isoformat(),
            "last_window_end_exclusive": end.isoformat(),
            "last_source_run_id": run.id,
            "last_source_dataset_id": source_id,
            "last_count": len(items),
            "combined_dataset_id": dataset.id,
        })
        await Actor.push_data({
            "facebook_url": page,
            "year": year,
            "window_start": first.isoformat(),
            "window_end_exclusive": end.isoformat(),
            "count": len(items),
            "source_run_id": run.id,
            "combined_dataset_id": dataset.id,
            "next_date": end.isoformat(),
        })
        Actor.log.info(f"Saved {len(items)} posts; next start: {end}")


if __name__ == "__main__":
    asyncio.run(main())
