package com.example.personalagent;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import java.nio.file.*;

/**
 * 个人资料库的运行路径配置，绑定 {@code agent.*} 外部配置项。
 *
 * <p>位于配置层：只把外部配置解析成绝对路径，不创建目录、不校验 Vault 内容。
 * 三个路径各有独立来源与回退——{@link #dataPath()} 存放状态、备份与 Quartz 构建产物，
 * {@link #defaultVault()} 指向原生 Obsidian 仓库，{@link #quartzPath()} 定位外部
 * Quartz 源码目录。</p>
 *
 * <p>未显式配置时按操作系统与工作目录探测回退，因此同一份 jar 在 Windows 开发机与
 * 其他系统上的默认路径不同；所有返回值都经 {@code toAbsolutePath().normalize()}，
 * 避免相对路径在后续越界校验中产生歧义。</p>
 */
@Configuration
@ConfigurationProperties(prefix="agent")
public class AgentConfig {
    // 四个字段全部来自 agent.* 配置；留空表示不覆盖下面的默认探测逻辑。
    private String dataDir="";
    private String vaultDir="",quartzDir="",nodeCommand="node";
    /**
     * 状态与产物根目录：登录哈希、仓库选择、笔记备份、Quartz 构建输出都落在这里。
     *
     * @return 绝对规范化的数据目录；未配置 {@code agent.data-dir} 时依次回退到
     *         Windows 的 {@code LOCALAPPDATA}、用户主目录下的 {@code .local/share}，
     *         并统一追加 {@code Love530/PersonalAgent}
     */
    public Path dataPath() {
        String local=System.getenv("LOCALAPPDATA");
        return (dataDir.isEmpty()?Paths.get(local==null?System.getProperty("user.home")+"/.local/share":local,"Love530","PersonalAgent"):Paths.get(dataDir)).toAbsolutePath().normalize();
    }
    /**
     * 默认 Obsidian Vault 路径，仅在状态文件尚未记录仓库选择时使用。
     *
     * <p>非 Windows 系统回退到数据目录下的 {@code knowledge-vault}。测试必须通过
     * {@code agent.vault-dir} 覆盖该值，不得读写 D 盘真实资料。</p>
     *
     * @return 绝对规范化的 Vault 根目录；本方法不检查目录是否存在
     */
    public Path defaultVault(){
        if(!vaultDir.isEmpty())return Paths.get(vaultDir).toAbsolutePath().normalize();
        // Windows 的个人资料集中放在 D 盘，服务状态目录仍可独立配置。
        if(System.getProperty("os.name","").startsWith("Windows"))return Paths.get("D:/个人资料/Obsidian Vault").toAbsolutePath().normalize();
        return dataPath().resolve("knowledge-vault");
    }
    /**
     * 定位外部 Quartz 5.1 源码目录（需含 {@code package.json}），用于调用其构建脚本。
     *
     * <p>未配置 {@code agent.quartz-dir} 时从当前工作目录逐级向上查找 {@code quartz}
     * 与 {@code personal-agent/quartz} 两个候选；都找不到时返回仓库内约定路径，
     * 让构建明确报出「请先 npm ci」，而不是因为路径为空而静默失败。</p>
     *
     * @return Quartz 目录；存在性与依赖完整性由调用方判断
     */
    public Path quartzPath(){
        if(!quartzDir.isEmpty())return Paths.get(quartzDir).toAbsolutePath().normalize();
        for(Path p=Paths.get("").toAbsolutePath();p!=null;p=p.getParent())
            for(Path c:new Path[]{p.resolve("quartz"),p.resolve("personal-agent/quartz")})
                if(Files.isRegularFile(c.resolve("package.json")))return c;
        return Paths.get("personal-agent/quartz").toAbsolutePath();
    }
    public String getDataDir(){return dataDir;} public void setDataDir(String v){dataDir=v;}
    public String getVaultDir(){return vaultDir;} public void setVaultDir(String v){vaultDir=v;}
    public String getQuartzDir(){return quartzDir;} public void setQuartzDir(String v){quartzDir=v;}
    public String getNodeCommand(){return nodeCommand;} public void setNodeCommand(String v){nodeCommand=v;}
}
