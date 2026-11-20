package com.example.personalagent;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import java.nio.file.*;

@Configuration
@ConfigurationProperties(prefix="agent")
public class AgentConfig {
    private String dataDir="";
    private String vaultDir="",quartzDir="",nodeCommand="node";
    public Path dataPath() {
        String local=System.getenv("LOCALAPPDATA");
        return (dataDir.isEmpty()?Paths.get(local==null?System.getProperty("user.home")+"/.local/share":local,"Love530","PersonalAgent"):Paths.get(dataDir)).toAbsolutePath().normalize();
    }
    public Path defaultVault(){
        if(!vaultDir.isEmpty())return Paths.get(vaultDir).toAbsolutePath().normalize();
        // Windows 的个人资料集中放在 D 盘，服务状态目录仍可独立配置。
        if(System.getProperty("os.name","").startsWith("Windows"))return Paths.get("D:/个人资料/Obsidian Vault").toAbsolutePath().normalize();
        return dataPath().resolve("knowledge-vault");
    }
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
