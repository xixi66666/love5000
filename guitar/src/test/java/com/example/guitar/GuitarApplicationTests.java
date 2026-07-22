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
				.andExpect(content().string(org.hamcrest.Matchers.containsString("GUITAR")))
				.andExpect(content().string(org.hamcrest.Matchers.containsString("/js/api.js")))
				.andExpect(content().string(org.hamcrest.Matchers.containsString("8088")));
	}

	@Test
	void authPageExposesAccessibleAuthForms() throws Exception {
		mockMvc.perform(get("/auth.html"))
				.andExpect(status().isOk())
				.andExpect(content().contentTypeCompatibleWith("text/html"))
				.andExpect(content().string(org.hamcrest.Matchers.containsString("for=\"login-phone\"")))
				.andExpect(content().string(org.hamcrest.Matchers.containsString("data-auth-tab=\"register\"")))
				.andExpect(content().string(org.hamcrest.Matchers.containsString("/js/auth.js")));
	}

	@Test
	void phaseOneWorkspacePagesExposeTheirModules() throws Exception {
		assertWorkspacePage("/upload.html", "/js/upload.js");
		assertWorkspacePage("/favorites.html", "/js/favorites.js");
		assertWorkspacePage("/profile.html", "/js/profile.js");
		assertWorkspacePage("/admin.html", "/js/admin.js");
	}

	private void assertWorkspacePage(String path, String module) throws Exception {
		mockMvc.perform(get(path))
				.andExpect(status().isOk())
				.andExpect(content().contentTypeCompatibleWith("text/html"))
				.andExpect(content().string(org.hamcrest.Matchers.containsString(module)))
				.andExpect(content().string(org.hamcrest.Matchers.containsString("id=\"main\"")));
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
