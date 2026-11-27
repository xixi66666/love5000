package com.ycxandwuqian.love;

import com.ycxandwuqian.love.dao.PhotoDao;
import com.ycxandwuqian.love.dao.GuitarVideoDao;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;

import javax.sql.DataSource;

/**
 * Spring 上下文冒烟测试。
 *
 * <p>只验证 {@link LovestoryApplication} 能完成装配。{@code DataSource}、{@link PhotoDao}
 * 与 {@link GuitarVideoDao} 都用 {@code @MockBean} 替换，因此不连接真实 MySQL，
 * 也不要求提供 OSS 凭据（OSS 默认关闭，容器中没有 {@code OssUtil} 也应当能启动）。</p>
 */
@SpringBootTest
class LovestoryApplicationTests {

    @MockBean
    private DataSource dataSource;

    @MockBean
    private PhotoDao photoDao;

    @MockBean
    private GuitarVideoDao guitarVideoDao;

    @Test
    void contextLoads() {
    }

}
