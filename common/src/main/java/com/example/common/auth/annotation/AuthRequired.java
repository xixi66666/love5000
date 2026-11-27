package com.example.common.auth.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 登录校验标记注解，用于声明「访问该资源需要已登录的 Session」。
 *
 * <p>注解本身不含属性，只是语义标记，由 {@code AuthInterceptor} 在 {@code preHandle}
 * 阶段读取：方法上标注或所在类上标注，任一处命中即调用
 * {@code AuthService#requireCurrentUser} 校验会话。</p>
 *
 * <p>保留策略为 {@link RetentionPolicy#RUNTIME}，因为校验完全依赖反射读取；
 * 作用目标为类型与方法，便于整个 Controller 统一保护，或只保护其中部分接口。</p>
 */
@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
public @interface AuthRequired {
}
