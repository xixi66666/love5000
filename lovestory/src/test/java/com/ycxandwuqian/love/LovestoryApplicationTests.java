package com.ycxandwuqian.love;

import com.ycxandwuqian.love.dao.PhotoDao;
import com.ycxandwuqian.love.dao.GuitarVideoDao;
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

    @MockBean
    private GuitarVideoDao guitarVideoDao;

    @Test
    void contextLoads() {
    }

}
