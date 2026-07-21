package com.example.guitar;

import com.example.guitar.auth.service.GuitarAuthPersistenceService;
import org.junit.jupiter.api.Test;
import org.springframework.aop.support.AopUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Collections;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@Import(GuitarApplicationTests.ProtectedEndpointTestController.class)
class GuitarApplicationTests {

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private GuitarAuthPersistenceService persistenceService;

	@Test
	void contextLoads() {
	}

	@Test
	void healthEndpointReturnsServiceStatus() throws Exception {
		mockMvc.perform(get("/api/health"))
				.andExpect(status().isOk())
				.andExpect(content().contentTypeCompatibleWith("application/json"))
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.service").value("guitar"));
	}

	@Test
	void homepageIdentifiesTheGuitarService() throws Exception {
		mockMvc.perform(get("/index.html"))
				.andExpect(status().isOk())
				.andExpect(content().contentTypeCompatibleWith("text/html"))
				.andExpect(content().string(org.hamcrest.Matchers.containsString("Guitar Service")))
				.andExpect(content().string(org.hamcrest.Matchers.containsString("8088")));
	}

	@Test
	void configuredAuthenticationInterceptorProtectsMatrixParameterPath() throws Exception {
		mockMvc.perform(get("/api/users;v=1/me"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("AUTH_REQUIRED"));
	}

	@Test
	void authenticationPersistenceBoundaryIsTransactionProxied() {
		assertThat(AopUtils.isAopProxy(persistenceService)).isTrue();
	}

	@RestController
	static class ProtectedEndpointTestController {

		@GetMapping("/api/users/me")
		public Map<String, Object> currentUser() {
			return Collections.<String, Object>singletonMap("success", true);
		}
	}

}
