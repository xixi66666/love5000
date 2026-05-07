package com.ycxandwuqian.love;

import com.ycxandwuqian.love.dao.PhotoDao;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;

import javax.sql.DataSource;

@SpringBootTest
class LovestoryApplicationTests {

    @MockBean
    private DataSource dataSource;

    @MockBean
    private PhotoDao photoDao;

    @Test
    void contextLoads() {
    }

}
