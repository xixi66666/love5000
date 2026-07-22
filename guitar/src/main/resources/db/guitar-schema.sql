-- Guitar sheet platform schema for MySQL 5.7+
CREATE DATABASE IF NOT EXISTS guitar DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE guitar;

CREATE TABLE IF NOT EXISTS guitar_user (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    phone VARCHAR(20) NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    nickname VARCHAR(30) NOT NULL,
    avatar_object_key VARCHAR(500) DEFAULT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'USER',
    status VARCHAR(20) NOT NULL DEFAULT 'ENABLED',
    ban_reason VARCHAR(500) DEFAULT NULL,
    banned_by BIGINT UNSIGNED DEFAULT NULL,
    banned_at DATETIME DEFAULT NULL,
    ban_expires_at DATETIME DEFAULT NULL,
    last_login_at DATETIME DEFAULT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_guitar_user_phone (phone),
    KEY idx_guitar_user_status_role (status, role),
    CONSTRAINT fk_guitar_user_banned_by FOREIGN KEY (banned_by) REFERENCES guitar_user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_sheet (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    uploader_id BIGINT UNSIGNED NOT NULL,
    song_name VARCHAR(120) NOT NULL,
    singer VARCHAR(120) NOT NULL,
    arranger VARCHAR(120) DEFAULT NULL,
    description VARCHAR(1000) DEFAULT NULL,
    keywords VARCHAR(500) DEFAULT NULL,
    sheet_type VARCHAR(30) NOT NULL,
    difficulty VARCHAR(30) NOT NULL,
    key_signature VARCHAR(20) NOT NULL,
    capo_position TINYINT UNSIGNED DEFAULT NULL,
    tuning VARCHAR(80) NOT NULL,
    file_mode VARCHAR(20) NOT NULL,
    storage_uuid CHAR(36) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PUBLISHED',
    offline_reason VARCHAR(500) DEFAULT NULL,
    offline_by BIGINT UNSIGNED DEFAULT NULL,
    offline_at DATETIME DEFAULT NULL,
    view_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    favorite_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_guitar_sheet_storage_uuid (storage_uuid),
    KEY idx_guitar_sheet_public (status, create_time, id),
    KEY idx_guitar_sheet_uploader (uploader_id, status, create_time),
    KEY idx_guitar_sheet_filters (status, sheet_type, difficulty, key_signature),
    CONSTRAINT fk_guitar_sheet_uploader FOREIGN KEY (uploader_id) REFERENCES guitar_user (id),
    CONSTRAINT fk_guitar_sheet_offline_by FOREIGN KEY (offline_by) REFERENCES guitar_user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_sheet_file (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sheet_id BIGINT UNSIGNED NOT NULL,
    object_key VARCHAR(500) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_extension VARCHAR(20) NOT NULL,
    file_size BIGINT UNSIGNED NOT NULL,
    sort_order INT UNSIGNED NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_guitar_sheet_file_order (sheet_id, sort_order),
    CONSTRAINT fk_guitar_sheet_file_sheet FOREIGN KEY (sheet_id) REFERENCES guitar_sheet (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_favorite_folder (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(50) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_guitar_favorite_folder_owner (id, user_id),
    UNIQUE KEY uk_guitar_favorite_folder_name (user_id, name),
    KEY idx_guitar_favorite_folder_user (user_id, sort_order, id),
    CONSTRAINT fk_guitar_favorite_folder_user FOREIGN KEY (user_id) REFERENCES guitar_user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_favorite (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    folder_id BIGINT UNSIGNED NOT NULL,
    sheet_id BIGINT UNSIGNED NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_guitar_favorite (folder_id, sheet_id),
    KEY idx_guitar_favorite_user (user_id, create_time),
    KEY idx_guitar_favorite_sheet (sheet_id),
    CONSTRAINT fk_guitar_favorite_user FOREIGN KEY (user_id) REFERENCES guitar_user (id),
    CONSTRAINT fk_guitar_favorite_folder_owner FOREIGN KEY (folder_id, user_id) REFERENCES guitar_favorite_folder (id, user_id),
    CONSTRAINT fk_guitar_favorite_sheet FOREIGN KEY (sheet_id) REFERENCES guitar_sheet (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_admin_action_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    admin_user_id BIGINT UNSIGNED NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id BIGINT UNSIGNED NOT NULL,
    reason VARCHAR(500) DEFAULT NULL,
    before_state VARCHAR(1000) DEFAULT NULL,
    after_state VARCHAR(1000) DEFAULT NULL,
    ip_address VARCHAR(45) DEFAULT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_guitar_admin_log_admin (admin_user_id, create_time),
    KEY idx_guitar_admin_log_target (target_type, target_id, create_time),
    KEY idx_guitar_admin_log_action (action_type, create_time),
    CONSTRAINT fk_guitar_admin_log_user FOREIGN KEY (admin_user_id) REFERENCES guitar_user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_oss_cleanup_task (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    object_key VARCHAR(500) NOT NULL,
    business_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    retry_count INT UNSIGNED NOT NULL DEFAULT 0,
    next_retry_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claim_version BIGINT UNSIGNED NOT NULL DEFAULT 0,
    processing_started_at DATETIME DEFAULT NULL,
    last_error VARCHAR(1000) DEFAULT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_guitar_oss_cleanup_poll (status, next_retry_at),
    KEY idx_guitar_oss_cleanup_object (object_key(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guitar_daily_stat (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    stat_date DATE NOT NULL,
    new_user_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    uploaded_sheet_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    sheet_view_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    favorite_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    offline_sheet_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_guitar_daily_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Replace the placeholder only after registering the intended administrator account.
UPDATE guitar_user SET role = 'ADMIN', update_time = CURRENT_TIMESTAMP WHERE phone = '<registered-phone>';
