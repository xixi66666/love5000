package com.example.personalagent.model;
import java.util.*;

/**
 * 一篇真实 Markdown 笔记在内存中的投影：路径、属性、正文、链接与内容指纹。
 *
 * <p>属模型层，只承载数据与一个判定方法，不做任何 I/O。实例由
 * {@link com.example.personalagent.service.VaultService#read(String)} 与
 * {@link com.example.personalagent.service.VaultService#parse(String, String)} 组装，
 * 是 Controller、阅读渲染、图谱与分析服务之间的唯一数据形状。</p>
 *
 * <p>{@code revision} 是原始文件字节的 SHA-256，既用于编辑乐观锁比对，也写进分析报告的
 * 来源快照；{@code body} 是去掉 frontmatter 后的正文，{@code content} 保留完整原文，
 * 二者不可互换。</p>
 */
public class VaultNote {
    // 字段全部由 VaultService 填充：path 为 Vault 内相对路径（正斜杠），modifiedAt 取文件修改时间。
    public String path,title,domain,revision,content,body,modifiedAt;
    public Map<String,Object> properties=new LinkedHashMap<>();
    public List<String> links=new ArrayList<>();
    /**
     * 判断本篇是否允许作为 AI 分析的素材。
     *
     * <p>四类排除项：模板目录 {@code 90-模板/} 下的样板、显式 {@code ai_exclude: true}
     * 的私人记录、{@code origin=ai_generated} 的派生报告（避免 AI 引用自己的输出），
     * 以及 {@code status} 为 archived/draft/corrected 的历史或待核对内容。
     * 判定逐次计算、不缓存，属性被外部编辑后立即生效。</p>
     *
     * @return {@code true} 表示可以进入检索候选与发送清单
     */
    public boolean eligibleForAi(){
        return !path.startsWith("90-模板/")&&!Boolean.TRUE.equals(properties.get("ai_exclude"))&&!"ai_generated".equals(properties.get("origin"))
            &&!Arrays.asList("archived","draft","corrected").contains(String.valueOf(properties.get("status")));
    }
}
