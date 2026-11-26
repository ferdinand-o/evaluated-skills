# arctic-shift connector — behaviour that matters for research

Read this before the first connector call of a run (Phase 2).

- Searches sort by time only; max 100 per call; more via `next_cursor` with identical filters and sort.
- Texts are cut at 500 characters by default (`selftext_length`/`body_length` show the real size); full posts via `get_items_by_id` with `max_text_chars` up to 10000.
- `query` and `title` need `subreddit` or `author` (also in aggregations); `body` needs `subreddit`, `author`, `post_id` or `parent_id`. There is no Reddit-wide keyword search, and global URL aggregations time out. Full-text comment search (`body`) in big subreddits often times out even for one week — read comments through `get_comment_tree` of selected threads instead.
- Arctic Shift rejects about 1 in 20 requests under load (`UPSTREAM_TIMEOUT`, "slow down"): retry once after a pause.
- The server forwards about 1 request per second for all callers together; parallel workers beyond 4 only produce `SERVER_BUSY`.
- `frequency`: year, month, week, day, hour, minute, second. Weeks are summed from days (key = Monday). Other time buckets start at midnight German time, written in UTC.
- Collapsed comments are listed in `more_ids`; load them with `get_items_by_id(kind="comments")` when they matter.
- Results above ~100 000 characters are shortened by the server (texts first, then entries; `next_cursor` points to the rest).
- Scores of items younger than about 36 hours are preliminary; deleted content is missing from the archive.
