-- Optional cleanup: drop the old full-crawl data collected by the previous
-- GitHub Search based collector. Run this once after applying
-- migrate-trending.sql if you want the site to start from a clean slate.
--
-- After this script the next collection run repopulates the trending Top 10
-- repositories for daily / weekly / monthly.

SET NAMES utf8mb4;
SET time_zone = '+00:00';

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE trending_entries;
TRUNCATE TABLE star_snapshots;
TRUNCATE TABLE collection_runs;
TRUNCATE TABLE repositories;
SET FOREIGN_KEY_CHECKS = 1;
