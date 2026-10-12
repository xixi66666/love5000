-- Migration: add the trending_entries table used by the GitHub Trending collector.
-- Execute once against an existing skill_finder database.

SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE TABLE IF NOT EXISTS trending_entries (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  repository_id BIGINT UNSIGNED NOT NULL,
  period VARCHAR(16) NOT NULL,
  rank_position INT UNSIGNED NOT NULL,
  stars_gained INT NOT NULL,
  stars_total INT UNSIGNED NOT NULL DEFAULT 0,
  fetched_at DATETIME NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_trending_entries_period_repo (period, repository_id),
  KEY idx_trending_entries_period_rank (period, rank_position),
  CONSTRAINT fk_trending_entries_repository
    FOREIGN KEY (repository_id) REFERENCES repositories (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
