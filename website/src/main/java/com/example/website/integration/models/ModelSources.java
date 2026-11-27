package com.example.website.integration.models;

import com.example.common.ai.ModelProperties;
import org.springframework.core.env.Environment;

import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/**
 * 模型提供方来源：只从项目根目录的 {@code model.properties} 读取。
 *
 * <p>属于 integration/models 的配置适配层，把 {@link ModelProperties} 中声明的文本提供方
 * 转换成网关可用的标识、显示名、基址与密钥。密钥只留在内存，不进入目录响应，也不写入
 * 选择状态文件。</p>
 *
 * <p>两条安全约束：上游基址只能来自管理员已写好的本地配置，并统一去掉结尾斜杠；
 * 回读时会剔除带用户信息、查询串、片段、缺主机名以及非 HTTPS 的地址，唯一例外是
 * 本机 Strata（{@code http://127.0.0.1:9999}）。配置缺失或无法解析时返回空清单，
 * 让页面显示未就绪，而不是让整个应用启动失败。</p>
 */
public class ModelSources {
    /**
     * 单个文本提供方的展示与连接信息。
     *
     * <p>不可变值对象，密钥字段只供网关内部发起请求；{@code configured} 为空表示不限制
     * 模型清单，由上游返回结果决定可用模型。</p>
     */
    public static class Source {
        /** 提供方标识、显示名、去掉结尾斜杠的基址与密钥；密钥不参与任何对外输出。 */
        final String id, label, base, key;
        /** 配置声明的模型清单，空表示接受上游返回的全部聊天模型。 */
        final List<String> configured;
        /**
         * 构造提供方来源，顺带规范化基址与模型清单。
         *
         * @param id     提供方标识
         * @param label  显示名
         * @param base   上游基址，结尾斜杠会被去掉
         * @param key    API 密钥，可为空表示未配置
         * @param models 逗号分隔的模型清单，可为 {@code null}
         */
        Source(String id, String label, String base, String key, String models) {
            this.id=id; this.label=label; this.base=base.replaceAll("/+$", ""); this.key=key;
            List<String> names=new ArrayList<String>();
            if(models!=null) for(String name:models.split(",")) if(!name.trim().isEmpty()) names.add(name.trim());
            this.configured=names;
        }
        /**
         * 判断模型是否在配置清单内；清单为空时接受任意模型。
         *
         * @param model 上游返回的模型标识
         * @return 命中或无清单约束时返回 {@code true}
         */
        boolean acceptsModel(String model) {
            return configured.isEmpty() || configured.contains(model);
        }
    }
    private final Environment env;
    private final Path root;
    public ModelSources(Environment env, Path root) { this.env=env; this.root=root; }
    /**
     * 从当前工作目录向上查找项目根。
     *
     * <p>判定依据是存在 {@code website/python-a} 目录，因此从仓库任意子目录启动都能定位到
     * 同一份 {@code model.properties}；找不到时退回当前工作目录。</p>
     *
     * @return 项目根目录的绝对路径
     */
    public static Path projectRoot() {
        Path p=Paths.get("").toAbsolutePath();
        while (p != null) { if (Files.isDirectory(p.resolve("website/python-a"))) return p; p=p.getParent(); }
        return Paths.get("").toAbsolutePath();
    }
    /**
     * 定位 {@code model.properties} 的读取位置。
     *
     * <p>实际查找由 {@code ModelProperties.locate(Path)} 完成（当前目录与代码目录逐级向上），
     * 这里只负责传入根目录；不读取任何环境变量，云端部署必须挂载该文件。</p>
     *
     * @return 候选配置文件路径，不保证存在
     */
    public Path modelFile() {
        return ModelProperties.locate(root == null ? projectRoot() : root);
    }
    /**
     * 读取并过滤文本提供方清单。
     *
     * <p>配置缺失或解析失败时返回空清单，让页面显示未就绪而不是让整个应用启动失败。
     * 基址为空的提供方被跳过；随后剔除地址不合规的项：带用户信息、查询串、片段、
     * 缺主机名或非 HTTPS（仅本机 Strata 允许 HTTP）。</p>
     *
     * @return 可直接使用的提供方列表，顺序与配置文件一致
     */
    public List<Source> read() {
        ModelProperties settings;
        try {
            settings = ModelProperties.load(modelFile());
        } catch (RuntimeException e) {
            // 配置缺失或无法读取时保持空目录，页面显示未就绪而不是启动失败。
            return new ArrayList<Source>();
        }
        List<Source> sources=new ArrayList<Source>();
        for (ModelProperties.Provider provider:settings.textProviders()) {
            if (provider.baseUrl().isEmpty()) continue;
            sources.add(new Source(provider.id(), provider.label(), provider.baseUrl(), provider.apiKey(),
                    String.join(",", provider.models())));
        }
        // 上游地址只能来自管理员已写好的本地配置，且远端必须 HTTPS。
        sources.removeIf(s->{try {URI u=URI.create(s.base); return u.getUserInfo()!=null || u.getQuery()!=null || u.getFragment()!=null
                || u.getHost()==null || !("https".equals(u.getScheme()) || ("strata".equals(s.id) && "http".equals(u.getScheme()))); }
            catch(Exception e){return true;}});
        return sources;
    }
    /**
     * 定位本机 Strata 目录，仅用于判断能否一键启动。
     *
     * <p>优先读取 {@code website.local-services.strata-dir}，其次 {@code STRATA_HOME}，
     * 最后回退默认路径 {@code F:/model/Strata}。</p>
     *
     * @return Strata 项目目录路径，不保证存在
     */
    public Path strataHome(){return Paths.get(env.getProperty("website.local-services.strata-dir",env.getProperty("STRATA_HOME","F:/model/Strata")));}
}
