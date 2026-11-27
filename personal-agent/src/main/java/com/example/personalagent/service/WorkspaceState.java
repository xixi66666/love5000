package com.example.personalagent.service;

import com.example.personalagent.AgentConfig;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import javax.annotation.PreDestroy;
import java.nio.file.*;
import java.nio.channels.*;
import java.util.*;

/**
 * 服务自身状态的小型持久化容器（{@code knowledge-state.json}），并用文件锁保证单实例。
 *
 * <p>属服务层基础设施，被 {@link LocalSecurity}（登录盐与哈希）、{@link VaultService}
 * （当前仓库选择）、{@link AnalysisService} 与 {@link QuartzService}（任务与发布记录）
 * 共享。只存元数据，个人资料正文始终以 Vault 文件为准，因此这个文件损坏的代价是
 * 「需要重新登录或重选仓库」，而不是资料丢失——构造时解析失败会终止启动并提示恢复备份。</p>
 *
 * <p>非显然行为：数据目录里创建锁文件并持有排他锁，第二个实例拿不到锁即启动失败，
 * 避免两个进程同时写同一份状态；每次写入都是「复制—修改—整体重写」，配合
 * {@link #atomic(Path, byte[])} 的临时文件替换，读者要么看到旧版本要么看到新版本，
 * 不会读到半截 JSON。</p>
 */
@Service
public class WorkspaceState {
    private final ObjectMapper json;
    private final Path file;
    private final FileChannel channel;
    private final FileLock lock;
    private Map<String,Object> state;
    /**
     * 打开数据目录、抢占单实例锁并载入状态。
     *
     * @throws Exception 拿不到锁（已有实例在跑）或状态文件无法解析时抛出
     *         {@link IllegalStateException}，后者提示恢复备份
     */
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
    /**
     * 读取并深拷贝一个状态值。
     *
     * @param key 状态键
     * @return 反序列化后的独立副本；键不存在时返回 {@code null}。
     *         调用方修改返回值不会影响已持久化的状态
     */
    @SuppressWarnings("unchecked") public synchronized <T>T get(String key){
        Object value=state.get(key);return value==null?null:(T)json.convertValue(value,Object.class);
    }
    /**
     * 写入或覆盖一个状态键并立即落盘。
     *
     * <p>先复制当前状态再修改，落盘成功后才替换内存引用，因此写盘失败不会让内存与磁盘
     * 产生分歧。</p>
     *
     * @param key   状态键
     * @param value 任意可 JSON 序列化的值
     * @throws IllegalStateException 序列化或写入失败时抛出
     */
    public synchronized void put(String key,Object value){
        Map<String,Object> next=new LinkedHashMap<>(state);next.put(key,value);
        try{atomic(file,json.writerWithDefaultPrettyPrinter().writeValueAsBytes(next));state=next;}
        catch(Exception e){throw new IllegalStateException("无法保存资料空间配置",e);}
    }
    /**
     * 原子写入文件：临时文件 + 落盘 + 重命名替换。
     *
     * <p>重命名优先用 {@code ATOMIC_MOVE}，文件系统不支持时退化为普通替换；Windows 上
     * 索引器或杀毒软件可能短暂占用目标文件，因此对 {@link AccessDeniedException} 做最多
     * 6 次尝试、逐次加长的退避重试。任何情况下都不先删除旧文件，写失败时磁盘上仍是旧内容。</p>
     *
     * @param target 目标文件，父目录不存在会自动创建
     * @param bytes  完整内容
     * @throws Exception 重试耗尽或写入失败时抛出；临时文件在 {@code finally} 中清理
     */
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
    /** 释放文件锁并关闭通道，让下次启动能重新获取单实例锁。 */
    @PreDestroy public void close()throws Exception{lock.release();channel.close();}
}
