CREATE TABLE IF NOT EXISTS guitar_user (
    id BIGINT PRIMARY KEY,
    nickname VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS guitar_sheet (
    id BIGINT PRIMARY KEY,
    uploader_id BIGINT NOT NULL,
    song_name VARCHAR(120) NOT NULL,
    singer VARCHAR(120) NOT NULL,
    arranger VARCHAR(120),
    sheet_type VARCHAR(30) NOT NULL,
    difficulty VARCHAR(30) NOT NULL,
    key_signature VARCHAR(20) NOT NULL,
    capo_position INTEGER,
    tuning VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL,
    offline_reason VARCHAR(500),
    offline_by BIGINT,
    offline_at TIMESTAMP,
    view_count BIGINT NOT NULL DEFAULT 0,
    favorite_count BIGINT NOT NULL DEFAULT 0,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    CONSTRAINT fk_test_sheet_uploader FOREIGN KEY (uploader_id) REFERENCES guitar_user (id)
);

CREATE TABLE IF NOT EXISTS guitar_admin_action_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    admin_user_id BIGINT NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id BIGINT NOT NULL,
    reason VARCHAR(500),
    before_state VARCHAR(1000),
    after_state VARCHAR(1000),
    ip_address VARCHAR(45),
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_test_admin_log_user FOREIGN KEY (admin_user_id) REFERENCES guitar_user (id)
);

DELETE FROM guitar_admin_action_log;
DELETE FROM guitar_sheet;
DELETE FROM guitar_user;

INSERT INTO guitar_user (id, nickname) VALUES (7, '管理员');
INSERT INTO guitar_sheet (
    id, uploader_id, song_name, singer, arranger, sheet_type, difficulty,
    key_signature, capo_position, tuning, status, view_count, favorite_count,
    create_time, update_time
) VALUES (
    101, 7, '晴天', '周杰伦', '测试编配', 'CHORD', 'EASY',
    'C', 0, 'STANDARD', 'PUBLISHED', 12, 3,
    TIMESTAMP '2026-07-20 10:00:00', TIMESTAMP '2026-07-20 10:00:00'
);
