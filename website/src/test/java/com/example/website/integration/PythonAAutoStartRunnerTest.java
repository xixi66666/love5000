package com.example.website.integration;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.File;

import static org.assertj.core.api.Assertions.assertThat;

class PythonAAutoStartRunnerTest {

    @Test
    void createsPythonAProcessBuilderWithConsoleLogging() {
        PythonAAutoStartRunner runner = new PythonAAutoStartRunner();
        ReflectionTestUtils.setField(runner, "command", "python");
        ReflectionTestUtils.setField(runner, "port", 5174);
        ReflectionTestUtils.setField(runner, "logToConsole", true);
        File directory = new File("python-a");

        ProcessBuilder builder = runner.createProcessBuilder(directory);

        assertThat(builder.directory()).isEqualTo(directory);
        assertThat(builder.command()).containsExactly("python", "server.py");
        assertThat(builder.environment()).containsEntry("PORT", "5174");
        assertThat(builder.environment()).containsEntry("PYTHONUNBUFFERED", "1");
        assertThat(builder.redirectOutput()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
        assertThat(builder.redirectError()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
    }
}
