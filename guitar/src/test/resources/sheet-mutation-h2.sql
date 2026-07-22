CREATE TABLE guitar_user (
    id BIGINT PRIMARY KEY,
    nickname VARCHAR(30) NOT NULL
);

CREATE TABLE guitar_sheet (
    id BIGINT PRIMARY KEY,
    uploader_id BIGINT NOT NULL,
    song_name VARCHAR(120) NOT NULL,
    singer VARCHAR(120) NOT NULL,
    arranger VARCHAR(120),
    description VARCHAR(1000),
    keywords VARCHAR(500),
    sheet_type VARCHAR(30) NOT NULL,
    difficulty VARCHAR(30) NOT NULL,
    key_signature VARCHAR(20) NOT NULL,
    capo_position INT,
    tuning VARCHAR(80) NOT NULL,
    file_mode VARCHAR(20) NOT NULL,
    storage_uuid VARCHAR(36) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL,
    view_count BIGINT NOT NULL DEFAULT 0,
    favorite_count BIGINT NOT NULL DEFAULT 0,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE TABLE guitar_sheet_file (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sheet_id BIGINT NOT NULL,
    object_key VARCHAR(500) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_extension VARCHAR(20) NOT NULL,
    file_size BIGINT NOT NULL,
    sort_order INT NOT NULL,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (sheet_id, sort_order)
);

CREATE TABLE guitar_favorite (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sheet_id BIGINT NOT NULL
);

CREATE TABLE guitar_oss_cleanup_task (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    object_key VARCHAR(500) NOT NULL,
    business_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    retry_count INT NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claim_version BIGINT NOT NULL DEFAULT 0,
    processing_started_at TIMESTAMP,
    last_error VARCHAR(1000),
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (object_key <> 'outbox-failure.pdf')
);
