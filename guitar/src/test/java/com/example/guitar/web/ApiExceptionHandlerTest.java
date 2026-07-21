package com.example.guitar.web;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataRetrievalFailureException;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.multipart.support.MissingServletRequestPartException;

import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ApiExceptionHandlerTest {

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(new FailureController())
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }

    @Test
    void multipartParsingFailureReturnsStableBadRequestWithoutDetails() throws Exception {
        mockMvc.perform(get("/test/multipart"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("MULTIPART_INVALID"))
                .andExpect(jsonPath("$.message", not(containsString("secret-boundary"))));
    }

    @Test
    void missingMultipartPartReturnsStableBadRequestWithoutDetails() throws Exception {
        mockMvc.perform(get("/test/missing-part"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("MULTIPART_INVALID"))
                .andExpect(jsonPath("$.message", not(containsString("privateFile"))));
    }

    @Test
    void multipartSizeFailureReturnsPayloadTooLarge() throws Exception {
        mockMvc.perform(get("/test/upload-too-large"))
                .andExpect(status().isPayloadTooLarge())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("FILE_TOO_LARGE"));
    }

    @Test
    void dataAccessFailureDoesNotExposeConnectionDetails() throws Exception {
        mockMvc.perform(get("/test/database"))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.code").value("DATA_ACCESS_ERROR"))
                .andExpect(jsonPath("$.message", not(containsString("jdbc:mysql://secret"))));
    }

    @Test
    void unexpectedFailureDoesNotExposeInternalDetails() throws Exception {
        mockMvc.perform(get("/test/unexpected"))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.code").value("INTERNAL_ERROR"))
                .andExpect(jsonPath("$.message", not(containsString("private-token"))));
    }

    @RestController
    private static class FailureController {

        @GetMapping("/test/multipart")
        public void multipart() {
            throw new MultipartException("secret-boundary");
        }

        @GetMapping("/test/upload-too-large")
        public void uploadTooLarge() {
            throw new MaxUploadSizeExceededException(1024L);
        }

        @GetMapping("/test/missing-part")
        public void missingPart() throws MissingServletRequestPartException {
            throw new MissingServletRequestPartException("privateFile");
        }

        @GetMapping("/test/database")
        public void database() {
            throw new DataRetrievalFailureException("jdbc:mysql://secret");
        }

        @GetMapping("/test/unexpected")
        public void unexpected() {
            throw new IllegalStateException("private-token");
        }
    }
}
