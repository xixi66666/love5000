package com.example.personalagent;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import javax.sql.DataSource;
import java.nio.file.*;
import java.nio.channels.*;
import javax.annotation.PreDestroy;

@Configuration
@ConfigurationProperties(prefix="agent")
public class AgentConfig {
    private String dataDir="",apiBase="https://api.deepseek.com",model="deepseek-flash",apiKey="",skillRoots="",bookRoots="";
    private boolean background=true;
    private FileChannel lockChannel;
    private FileLock writerLock;
    public Path dataPath() {
        String local=System.getenv("LOCALAPPDATA");
        return (dataDir.isEmpty()?Paths.get(local==null?System.getProperty("user.home")+"/.local/share":local,"Love530","PersonalAgent"):Paths.get(dataDir)).toAbsolutePath().normalize();
    }
    public Path vaultPath(){return dataPath().resolve("vault");}
    @Bean public DataSource dataSource() throws Exception {
        Files.createDirectories(dataPath());
        lockChannel=FileChannel.open(dataPath().resolve(".agent.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE);
        writerLock=lockChannel.tryLock();
        if(writerLock==null){lockChannel.close();throw new IllegalStateException("此私人资料目录已有运行实例，请复用现有服务");}
        DriverManagerDataSource ds=new DriverManagerDataSource();
        ds.setDriverClassName("org.h2.Driver");
        ds.setUrl("jdbc:h2:file:"+dataPath().resolve("agent").toString().replace('\\','/')+";DB_CLOSE_ON_EXIT=FALSE");
        ds.setUsername("sa"); ds.setPassword("");
        new ResourceDatabasePopulator(new ClassPathResource("schema.sql")).execute(ds);
        return ds;
    }
    @PreDestroy public void releaseWriter() throws Exception {if(writerLock!=null)writerLock.release();if(lockChannel!=null)lockChannel.close();}
    public String getDataDir(){return dataDir;} public void setDataDir(String v){dataDir=v;}
    public String getApiBase(){return apiBase;} public void setApiBase(String v){apiBase=v;}
    public String getModel(){return model;} public void setModel(String v){model=v;}
    public String getApiKey(){return apiKey;} public void setApiKey(String v){apiKey=v;}
    public String getSkillRoots(){return skillRoots;} public void setSkillRoots(String v){skillRoots=v;}
    public String getBookRoots(){return bookRoots;} public void setBookRoots(String v){bookRoots=v;}
    public boolean isBackground(){return background;} public void setBackground(boolean v){background=v;}
}
