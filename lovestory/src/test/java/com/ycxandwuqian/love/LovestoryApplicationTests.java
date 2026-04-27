package com.ycxandwuqian.love;

import com.ycxandwuqian.love.repository.PhotoRepository;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;

import javax.sql.DataSource;

@SpringBootTest
class LovestoryApplicationTests {

    @MockBean
    private DataSource dataSource;

    @MockBean
    private PhotoRepository photoRepository;

    @Test
    void contextLoads() {
    }

}
