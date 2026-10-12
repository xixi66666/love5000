-- Skill Finder schema (MySQL 5.5+ compatible)
-- Execute this file manually against an empty database.
-- The application never creates or alters tables automatically.

SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE TABLE repositories (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  github_id BIGINT UNSIGNED NOT NULL,
  owner VARCHAR(100) NOT NULL,
  name VARCHAR(100) NOT NULL,
  full_name VARCHAR(191) NOT NULL,
  html_url VARCHAR(512) NOT NULL,
  homepage VARCHAR(512) NULL,
  description TEXT NULL,
  introduction TEXT NULL,
  language VARCHAR(100) NULL,
  topics TEXT NOT NULL,
  categories TEXT NOT NULL,
  matched_rules TEXT NOT NULL,
  stars_count INT UNSIGNED NOT NULL DEFAULT 0,
  forks_count INT UNSIGNED NOT NULL DEFAULT 0,
  open_issues_count INT UNSIGNED NOT NULL DEFAULT 0,
  archived BOOLEAN NOT NULL DEFAULT FALSE,
  disabled BOOLEAN NOT NULL DEFAULT FALSE,
  available BOOLEAN NOT NULL DEFAULT TRUE,
  github_created_at DATETIME NOT NULL,
  github_updated_at DATETIME NOT NULL,
  last_synced_at DATETIME NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_repositories_github_id (github_id),
  UNIQUE KEY uk_repositories_full_name (full_name),
  KEY idx_repositories_stars (stars_count),
  KEY idx_repositories_language (language),
  KEY idx_repositories_available_synced (available, last_synced_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE star_snapshots (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  repository_id BIGINT UNSIGNED NOT NULL,
  snapshot_date DATE NOT NULL,
  stars_count INT UNSIGNED NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_star_snapshots_repository_date (repository_id, snapshot_date),
  KEY idx_star_snapshots_date (snapshot_date),
  CONSTRAINT fk_star_snapshots_repository
    FOREIGN KEY (repository_id) REFERENCES repositories (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE trending_entries (
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

CREATE TABLE collection_runs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  status VARCHAR(32) NOT NULL,
  trigger_type VARCHAR(32) NOT NULL,
  started_at DATETIME NOT NULL,
  finished_at DATETIME NULL,
  query_count INT UNSIGNED NOT NULL DEFAULT 0,
  discovered_count INT UNSIGNED NOT NULL DEFAULT 0,
  updated_count INT UNSIGNED NOT NULL DEFAULT 0,
  failed_count INT UNSIGNED NOT NULL DEFAULT 0,
  rate_limit_remaining INT NULL,
  rate_limit_reset_at DATETIME NULL,
  error_summary TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_collection_runs_started (started_at),
  KEY idx_collection_runs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE last30days_reports (
  direction VARCHAR(32) NOT NULL,
  status VARCHAR(16) NOT NULL,
  payload MEDIUMTEXT NOT NULL,
  message VARCHAR(512) NULL,
  fetched_at DATETIME NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- No DB default: MySQL 5.5 allows one CURRENT_TIMESTAMP default per table, and
  -- epoch defaults break under non-UTC session time zones. The application layer
  -- sets updated_at on every write.
  updated_at DATETIME NULL,
  PRIMARY KEY (direction)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;



