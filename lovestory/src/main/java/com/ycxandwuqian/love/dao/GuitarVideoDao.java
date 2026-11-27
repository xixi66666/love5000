package com.ycxandwuqian.love.dao;

import com.ycxandwuqian.love.model.GuitarVideoRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * {@code guitar_video} 表的 MyBatis DAO。
 *
 * <p>位于持久层，方法名与 {@code resources/mapper/GuitarVideoMapper.xml} 中的语句 id 一一对应，
 * 参数用 {@code @Param} 与 XML 占位符对齐；下划线列名到驼峰属性的映射由
 * {@code mybatis.configuration.map-underscore-to-camel-case} 配合 mapper 的 resultMap 完成。
 * 这里只声明接口，不含任何 SQL 与业务判断。</p>
 *
 * <p>删除采用软删除语义：{@link #hideById(Long)} 只把 {@code status} 置 0，
 * OSS 上的视频与封面对象由业务层负责清理。</p>
 */
@Mapper
public interface GuitarVideoDao {

    /**
     * 插入一条视频记录。
     *
     * @param guitarVideoRecord 待插入记录；{@code title} 与 {@code videoUrl} 由数据库约束保证非空，
     *                          自增主键会回填到该对象的 {@code id}
     * @return 受影响行数，1 表示成功
     */
    int insert(GuitarVideoRecord guitarVideoRecord);

    /**
     * 查询展示中的卡片。
     *
     * <p>只返回 {@code status = 1} 的记录，排序为 {@code sort_order} 降序、
     * 创建时间降序、id 降序，保证同序号时新记录在前。</p>
     *
     * @return 记录列表；无数据时为空列表而不是 {@code null}
     */
    List<GuitarVideoRecord> findVisible();

    /**
     * 按主键查询单条记录，包含已隐藏（{@code status = 0}）的记录。
     *
     * @param id 主键
     * @return 命中的记录；不存在时返回 {@code null}
     */
    GuitarVideoRecord findById(@Param("id") Long id);

    /**
     * 只更新封面地址，其余字段保持不变。
     *
     * @param id       主键
     * @param coverUrl 新的封面地址（OSS 对象键或完整 URL）
     * @return 受影响行数，0 表示记录不存在
     */
    int updateCoverUrl(@Param("id") Long id, @Param("coverUrl") String coverUrl);

    /**
     * 软删除：把 {@code status} 置 0，记录本身保留。
     *
     * @param id 主键
     * @return 受影响行数，0 表示记录不存在（或已是隐藏状态且数据库未报告变更）
     */
    int hideById(@Param("id") Long id);
}
