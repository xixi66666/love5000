package com.example.website.integration;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * 解析 Python 子服务应使用的解释器命令。
 *
 * <p>包内工具类，供 {@link PythonAAutoStartRunner} 与 {@link QuantAAutoStartRunner} 复用。
 * 选择顺序：工作目录下 Windows 虚拟环境 {@code .venv/Scripts/python.exe}、
 * Unix 虚拟环境 {@code .venv/bin/python}、最后回退到配置的解释器命令（默认 {@code python}）。
 * 只按文件是否存在判断，不校验解释器版本，也不检查依赖是否已安装。</p>
 */
final class PythonCommandResolver {

    private PythonCommandResolver() {
    }

    /**
     * 生成解释器命令前缀。
     *
     * <p>虚拟环境位于子服务工作目录下，因此同一个配置在仓库根目录和模块目录启动时
     * 都能正确命中各自的 {@code .venv}。</p>
     *
     * @param command   回退用的解释器命令，例如配置里的 {@code python} 或绝对路径
     * @param directory 子服务工作目录，虚拟环境按此目录查找
     * @return 只含解释器一项的可变列表，调用方会继续追加脚本名或模块参数
     */
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
