package com.ycxandwuqian.love.repository;

import com.ycxandwuqian.love.model.PhotoRecord;
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
public class PhotoRepository {

    private static final RowMapper<PhotoRecord> PHOTO_ROW_MAPPER = (rs, rowNum) -> {
        PhotoRecord photoRecord = new PhotoRecord();
        photoRecord.setId(rs.getLong("id"));
        photoRecord.setPath(rs.getString("path"));
        photoRecord.setType(rs.getString("type"));
        photoRecord.setCreateTime(rs.getTimestamp("create_time").toLocalDateTime());
        return photoRecord;
    };

    private final JdbcTemplate jdbcTemplate;

    public PhotoRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Long save(String url, String type) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement preparedStatement =
                    connection.prepareStatement("insert into photo(path, type) values (?, ?)", Statement.RETURN_GENERATED_KEYS);
            preparedStatement.setString(1, url);
            preparedStatement.setString(2, type);
            return preparedStatement;
        }, keyHolder);

        Number key = keyHolder.getKey();
        return key == null ? null : key.longValue();
    }

    public List<PhotoRecord> findAll() {
        return jdbcTemplate.query(
                "select id, path, type, create_time from photo order by create_time desc, id desc",
                PHOTO_ROW_MAPPER
        );
    }

    public Optional<PhotoRecord> findById(Long id) {
        List<PhotoRecord> photos = jdbcTemplate.query(
                "select id, path, type, create_time from photo where id = ?",
                PHOTO_ROW_MAPPER,
                id
        );
        return photos.stream().findFirst();
    }

    public boolean deleteById(Long id) {
        return jdbcTemplate.update("delete from photo where id = ?", id) > 0;
    }
}
