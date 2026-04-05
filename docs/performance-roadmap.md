# Performance Optimization Roadmap

## Done

| Item | Detail |
|------|--------|
| Trigram indexes | GIN indexes on `Ticker.display_name` and `symbol` for fast search |
| PostgreSQL tuning | shared_buffers 512MB, work_mem 8MB, random_page_cost 1.1 |
| Install Redis | Running on server, Django CACHES configured |
| Cache ticker list | 27K rows cached in Redis for 1 hour |
| Cache search results | Cached for 2 minutes keyed by query |
| Fix N+1 in AdminDashboard | Replaced per-user loops with annotate() |
| Fix CompanyAnalysisView | 3 queries reduced to 1 |
| Composite indexes | CompanyAnalysis(ticker, -generated_at), LookupLog(user, timestamp), LookupLog(session_key, timestamp) |
| Search debounce | 200ms to 300ms |
| Dynamic imports | CompareTab, FundamentalsTab, CompanyAnalysis lazy-loaded |
| useMemo fix | CompanySearchInput excludeSet |
| Reduce Gunicorn workers | 3 to 2 (1 vCPU machine) |
| Cache PE10/fundamentals endpoints | Redis cache on PE10View (5 min TTL) and FundamentalsView (10 min TTL) |
| Enable pg_stat_statements | Query performance monitoring on production PostgreSQL |
| Dynamic import CompanyMetricsCard + Recharts | Code-split via next/dynamic; Recharts no longer in initial bundle |
| Lazy-load images | `loading="lazy"` on all logo `<img>` tags; footer logo via Next.js `<Image>` |

## Remaining

| Item | Impact | Effort |
|------|--------|--------|
| Upgrade or separate VPS | High (the real ceiling: 1 vCPU / 2 GB shared, 420 MB swap) | Decision needed |
| Replace Apache with Caddy or Nginx | Medium (frees ~200 MB RAM) | Medium |
