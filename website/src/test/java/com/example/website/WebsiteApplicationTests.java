package com.example.website;

import com.example.website.auth.WebsiteAuthUserRepository;
import com.example.website.blog.dao.BlogArticleDao;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;

@SpringBootTest(properties = {
        "spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration",
        "python-a.auto-start.enabled=false"
})
class WebsiteApplicationTests {

    @MockBean
    private BlogArticleDao blogArticleDao;

    @MockBean
    private WebsiteAuthUserRepository websiteAuthUserRepository;

    @Test
    void contextLoads() {
    }

}
