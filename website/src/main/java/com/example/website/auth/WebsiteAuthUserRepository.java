package com.example.website.auth;

import com.example.common.auth.model.AuthUser;
import com.example.common.auth.repository.AuthUserRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.util.List;
import java.util.Optional;

@Repository
public class WebsiteAuthUserRepository implements AuthUserRepository {

    private static final RowMapper<AuthUser> AUTH_USER_ROW_MAPPER = (rs, rowNum) -> {
        AuthUser authUser = new AuthUser();
        authUser.setId(rs.getLong("id"));
        authUser.setUsername(rs.getString("username"));
        authUser.setDisplayName(rs.getString("display_name"));
        authUser.setPasswordHash(rs.getString("password_hash"));
        authUser.setRole(rs.getString("role"));
        authUser.setEnabled(rs.getBoolean("enabled"));
        return authUser;
    };

    private final JdbcTemplate jdbcTemplate;

    public WebsiteAuthUserRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void createTableIfAbsent() {
        jdbcTemplate.execute("create table if not exists auth_user (" +
                "id bigint primary key auto_increment," +
                "username varchar(64) not null unique," +
                "display_name varchar(100) not null," +
                "password_hash varchar(100) not null," +
                "role varchar(40) not null default 'USER'," +
                "enabled tinyint(1) not null default 1," +
                "created_at datetime not null default current_timestamp," +
                "updated_at datetime not null default current_timestamp on update current_timestamp" +
                ") charset=utf8mb4");
    }

    @Override
    public Optional<AuthUser> findByUsername(String username) {
        List<AuthUser> users = jdbcTemplate.query(
                "select id, username, display_name, password_hash, role, enabled from auth_user where username = ?",
                AUTH_USER_ROW_MAPPER,
                username
        );
        return users.stream().findFirst();
    }

    @Override
    public Optional<AuthUser> findById(Long id) {
        List<AuthUser> users = jdbcTemplate.query(
                "select id, username, display_name, password_hash, role, enabled from auth_user where id = ?",
                AUTH_USER_ROW_MAPPER,
                id
        );
        return users.stream().findFirst();
    }

    @Override
    public Long save(String username, String passwordHash, String displayName, String role) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement(
                    "insert into auth_user(username, password_hash, display_name, role) values (?, ?, ?, ?)",
                    Statement.RETURN_GENERATED_KEYS
            );
            statement.setString(1, username);
            statement.setString(2, passwordHash);
            statement.setString(3, displayName);
            statement.setString(4, role);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        return key == null ? null : key.longValue();
    }
}
