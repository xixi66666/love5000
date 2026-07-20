package com.example.website.integration;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

final class PythonCommandResolver {

    private PythonCommandResolver() {
    }

    static List<String> resolve(String command, File directory) {
        List<String> commandParts = new ArrayList<>();

        File windowsVirtualEnvPython = new File(directory, ".venv" + File.separator + "Scripts" + File.separator + "python.exe");
        if (windowsVirtualEnvPython.isFile()) {
            commandParts.add(windowsVirtualEnvPython.getAbsolutePath());
            return commandParts;
        }

        File unixVirtualEnvPython = new File(directory, ".venv" + File.separator + "bin" + File.separator + "python");
        if (unixVirtualEnvPython.isFile()) {
            commandParts.add(unixVirtualEnvPython.getAbsolutePath());
            return commandParts;
        }

        commandParts.add(command);
        return commandParts;
    }
}
