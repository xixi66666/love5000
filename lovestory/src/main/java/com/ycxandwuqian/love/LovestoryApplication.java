package com.ycxandwuqian.love;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 恋爱相册服务（lovestory）的 Spring Boot 启动入口。
 *
 * <p>本模块处于 Web 接入层，向浏览器提供照片墙、留言板和吉他视频卡片的静态页面与
 * REST 接口，默认监听 8081 端口；照片与视频经 {@code common} 模块的 {@code OssUtil}
 * 写入阿里云 OSS，记录则通过 MyBatis DAO + XML Mapper 落在 MySQL 的 {@code lovestory} 库。</p>
 *
 * <p>启动阶段不校验数据库与 OSS 的可用性：OSS 由 {@code LOVE530_OSS_ENABLED} 控制且默认关闭，
 * 缺少凭据时 {@code OssUtil} Bean 不存在，上传接口会返回可读的失败提示，
 * 服务本身仍可正常启动，便于本地无云资源时调试页面。</p>
 */
@SpringBootApplication
public class LovestoryApplication {

    /**
     * 标准 Spring Boot 启动方法，参数原样交给 {@link SpringApplication} 处理。
     *
     * @param args 命令行参数，可用来覆盖 {@code application.yml} 中的配置项
     */
    public static void main(String[] args) {
        SpringApplication.run(LovestoryApplication.class, args);
    }

}
