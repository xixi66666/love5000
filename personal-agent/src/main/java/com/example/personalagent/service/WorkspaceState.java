package com.example.personalagent.service;

import com.example.personalagent.AgentConfig;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import javax.annotation.PreDestroy;
import java.nio.file.*;
import java.nio.channels.*;
import java.util.*;

/** 仅保存登录哈希、仓库选择与任务状态；资料正文以 Vault 为准。 */
@Service
public class WorkspaceState {
    private final ObjectMapper json;
    private final Path file;
    private final FileChannel channel;
    private final FileLock lock;
    private Map<String,Object> state;
    public WorkspaceState(AgentConfig config,ObjectMapper json)throws Exception {
        this.json=json;
        Files.createDirectories(config.dataPath());
        channel=FileChannel.open(config.dataPath().resolve(".knowledge.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE);
        lock=channel.tryLock();
        if(lock==null){channel.close();throw new IllegalStateException("此资料空间已由另一个实例打开");}
        file=config.dataPath().resolve("knowledge-state.json");
        try{state=Files.exists(file)?json.readValue(file.toFile(),new TypeReference<Map<String,Object>>(){}):new LinkedHashMap<>();}
        catch(Exception e){lock.release();channel.close();throw new IllegalStateException("knowledge-state.json 损坏，请恢复备份",e);}
    }
    @SuppressWarnings("unchecked") public synchronized <T>T get(String key){
        Object value=state.get(key);return value==null?null:(T)json.convertValue(value,Object.class);
    }
    public synchronized void put(String key,Object value){
        Map<String,Object> next=new LinkedHashMap<>(state);next.put(key,value);
        try{atomic(file,json.writerWithDefaultPrettyPrinter().writeValueAsBytes(next));state=next;}
        catch(Exception e){throw new IllegalStateException("无法保存资料空间配置",e);}
    }
    public static void atomic(Path target,byte[] bytes)throws Exception {
        Files.createDirectories(target.getParent());Path tmp=Files.createTempFile(target.getParent(),".writing-",".tmp");
        try{
            try(FileChannel out=FileChannel.open(tmp,StandardOpenOption.WRITE)){
                java.nio.ByteBuffer buffer=java.nio.ByteBuffer.wrap(bytes);while(buffer.hasRemaining())out.write(buffer);out.force(true);
            }
            // Windows 索引器/杀毒程序可能短暂占用目标；重试移动，绝不先删除旧文件。
            for(int attempt=0;;attempt++){
                try{try{Files.move(tmp,target,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}
                    catch(AtomicMoveNotSupportedException e){Files.move(tmp,target,StandardCopyOption.REPLACE_EXISTING);}break;}
                catch(AccessDeniedException e){if(attempt>=5)throw e;Thread.sleep(30L*(attempt+1));}
            }
        }
        finally{Files.deleteIfExists(tmp);}
    }
    @PreDestroy public void close()throws Exception{lock.release();channel.close();}
}
