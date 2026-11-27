package com.ycxandwuqian.love.dao;

import com.ycxandwuqian.love.model.PhotoRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * {@code photo} 表的 MyBatis DAO。
 *
 * <p>位于持久层，方法名与 {@code resources/mapper/PhotoMapper.xml} 中的语句 id 一致，
 * SQL 全部集中在 XML 里维护。表中只有 {@code id}、{@code path}、{@code type}、
 * {@code create_time} 四列，其中 {@code path} 存 OSS 对象键而非可访问 URL。</p>
 *
 * <p>删除是物理删除（{@code delete from photo}），与视频卡的软删除不同；
 * 对应的 OSS 对象由业务层在数据库删除成功后清理。</p>
 */
@Mapper
public interface PhotoDao {

    /**
     * 插入一条照片记录。
     *
     * @param photoRecord 待插入记录；{@code create_time} 由数据库默认值生成，
     *                    自增主键会回填到该对象的 {@code id}
     * @return 受影响行数，1 表示成功
     */
    int insert(PhotoRecord photoRecord);

    /**
     * 查询全部照片，按创建时间倒序、id 倒序，最新的排在最前面。
     *
     * @return 记录列表；无数据时为空列表而不是 {@code null}
     */
    List<PhotoRecord> findAll();

    /**
     * 按主键查询单条记录。
     *
     * @param id 主键
     * @return 命中的记录；不存在时返回 {@code null}
     */
    PhotoRecord findById(@Param("id") Long id);

    /**
     * 按主键物理删除记录。
     *
     * @param id 主键
     * @return 受影响行数，0 表示记录不存在
     */
    int deleteById(@Param("id") Long id);
}
