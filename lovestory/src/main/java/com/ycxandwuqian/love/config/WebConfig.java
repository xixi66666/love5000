package com.ycxandwuqian.love.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.Resource;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.ViewControllerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
import org.springframework.web.servlet.resource.PathResourceResolver;

import java.io.IOException;

/**
 * lovestory 的 Spring MVC 装配类。
 *
 * <p>位于 Web 配置层，只承担两件与业务无关的职责：把站点根路径指向登录页，
 * 以及接管静态资源路由。业务接口一律由 {@code controller} 包中的控制器处理。</p>
 *
 * <p>非显然行为：</p>
 * <ul>
 *   <li>根路径的视图控制器 setOrder(-1)，匹配顺序先于注解式 {@code @RequestMapping}，
 *       因此访问 {@code /} 走的是 forward（地址栏仍停在 {@code /}），
 *       {@link com.ycxandwuqian.love.controller.LoginController} 中同路径的 redirect 分支不会生效。</li>
 *   <li>{@code /uploads/**} 直接映射到进程工作目录下的 {@code uploads/}，属于本地调试用的外挂目录，
 *       不参与打包，目录不存在时该前缀一律 404。</li>
 *   <li>静态资源解析器在没有命中文件时返回 {@code null}，缺失资源以 404 结束，
 *       不会抛出异常或退化成目录列表。</li>
 * </ul>
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    /**
     * 注册根路径到登录页的转发。
     *
     * @param registry Spring MVC 注入的视图控制器注册表；{@code setOrder(-1)} 让它优先于
     *                 注解映射匹配，从而保证直接打开站点根地址时先看到门禁页
     */
    @Override
    public void addViewControllers(ViewControllerRegistry registry) {
        registry.addViewController("/").setViewName("forward:/login.html");
        registry.setOrder(-1);
    }

    /**
     * 注册两组静态资源处理链，顺序即优先级。
     *
     * <p>先注册的 {@code /uploads/**} 使用 {@code file:} 协议指向工作目录，
     * 便于本地把图片直接丢进 {@code uploads/} 预览（该目录不是构建产物，也不会被打包）；
     * 随后注册的 {@code /**} 兜底到 classpath 静态页，并开启资源链
     * （{@code resourceChain(true)}）以启用下面的自定义解析器。</p>
     *
     * @param registry 静态资源注册表
     */
    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/uploads/**")
                .addResourceLocations("file:uploads/");

        registry.addResourceHandler("/**")
                .addResourceLocations("classpath:/static/")
                .resourceChain(true)
                .addResolver(new PathResourceResolver() {
                    /**
                     * 只在目标文件真实存在且可读时返回资源。
                     *
                     * <p>与父类默认实现的差别在于：父类返回前还会调用 {@code checkResource}
                     * 做路径归属校验，本实现只做"存在且可读"的判断，命中即返回。
                     * 返回 {@code null} 表示放弃该资源，请求继续交给后续解析器，
                     * 最终表现为 404，因此缺失的静态页不会触发异常或目录列举。</p>
                     *
                     * @param resourcePath 相对静态资源根目录的请求路径
                     * @param location     当前尝试的资源根，即 {@code classpath:/static/}
                     * @return 命中的资源；不存在或不可读时返回 {@code null}
                     * @throws IOException 相对路径解析过程中由底层资源实现抛出
                     */
                    @Override
                    protected Resource getResource(String resourcePath, Resource location) throws IOException {
                        Resource requestedResource = location.createRelative(resourcePath);
                        if (requestedResource.exists() && requestedResource.isReadable()) {
                            return requestedResource;
                        }
                        return null;
                    }
                });
    }
}
