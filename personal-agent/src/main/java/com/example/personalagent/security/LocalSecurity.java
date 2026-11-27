package com.example.personalagent.security;

import com.example.personalagent.Api;
import com.example.personalagent.service.WorkspaceState;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.*;
import javax.servlet.http.*;
import java.net.*;
import java.security.*;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import java.util.*;

/**
 * 本机访问控制：来源校验、Session 登录、CSRF、登录限流与安全响应头。
 *
 * <p>属安全层，同时实现 {@link WebMvcConfigurer}（把自身注册为拦截全部请求的拦截器）
 * 与 {@link HandlerInterceptor}。除 {@code GET /api/health} 和三个 {@code /api/auth/}
 * 接口外，所有 {@code /api/} 请求都要求已登录；非 GET/HEAD 还必须带与会话内令牌
 * 逐字节相等的 {@code X-CSRF-Token}。</p>
 *
 * <p>几处刻意的例外与取舍：只接受回环地址与本机 Host；带 Origin 的请求必须同源；
 * {@code Sec-Fetch-Site: cross-site} 的文档导航仅对首页放行——从 8080 打开 5178 属于
 * 这种形态，但该例外不外扩到 API 或 iframe。{@code /library/} 使用更宽的 CSP
 * （允许内联脚本）并单独要求登录，好让 Quartz 自带脚本可用而不放开其他页面。
 * 密码用 PBKDF2-HMAC-SHA256 迭代 210000 次加 32 字节随机盐，状态文件里只有盐与哈希，
 * 从不落明文。</p>
 */
@Configuration
public class LocalSecurity implements WebMvcConfigurer,HandlerInterceptor {
    private final WorkspaceState store; private final ObjectMapper json;
    /** 登录尝试窗口：来源地址到「起始毫秒、次数」的映射，60 秒滚动清零；进程内状态，重启即失效。 */
    private final Map<String,long[]> attempts=new HashMap<>();
    public LocalSecurity(WorkspaceState store,ObjectMapper json){this.store=store;this.json=json;}
    /** 把自身注册为全局拦截器，覆盖静态页与 {@code /library/} 产物在内的所有请求。 */
    @Override public void addInterceptors(InterceptorRegistry registry){registry.addInterceptor(this).addPathPatterns("/**");}
    /**
     * 请求准入：先写安全响应头，再依次校验来源、豁免路径、会话与 CSRF。
     *
     * <p>顺序有意从便宜到昂贵：先判回环地址与 Host，再判免登录路径，最后才取 Session；
     * 任何一步失败都直接写出 JSON 错误并中断链路，不进入 Controller。
     * 未登录固定返回 401，来源或 CSRF 不符固定返回 403，两者语义不混用。</p>
     *
     * @param req     原始请求；远端地址与服务名可能被代理伪造，因此只作为本机场景的约束
     * @param res     用于设置安全头、状态码与错误响应体
     * @param handler 目标处理器，本实现不使用
     * @return {@code true} 表示放行；{@code false} 表示已写出 401/403，或已重定向到首页
     * @throws Exception 写响应体或计算摘要失败时抛出
     */
    @Override public boolean preHandle(HttpServletRequest req,HttpServletResponse res,Object handler)throws Exception {
        res.setHeader("X-Content-Type-Options","nosniff");res.setHeader("Referrer-Policy","no-referrer");res.setHeader("X-Frame-Options","DENY");
        res.setHeader("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' http://127.0.0.1:8080 http://localhost:8080; frame-ancestors 'none'; base-uri 'self'; form-action 'self'");
        String host=req.getServerName();
        boolean local=InetAddress.getByName(req.getRemoteAddr()).isLoopbackAddress();
        if(!local||!("localhost".equalsIgnoreCase(host)||"127.0.0.1".equals(host)||"::1".equals(host)))return fail(res,403,"仅允许本机访问");
        if("/api/health".equals(req.getRequestURI())&&"GET".equals(req.getMethod()))return true;
        String origin=req.getHeader("Origin"),fetch=req.getHeader("Sec-Fetch-Site");
        if(origin!=null){try{URI u=URI.create(origin);int port=u.getPort()<0?80:u.getPort();if(!"http".equals(u.getScheme())||!host.equalsIgnoreCase(u.getHost())||port!=req.getServerPort())return fail(res,403,"来源不被允许");}catch(Exception e){return fail(res,403,"来源无效");}}
        String path=req.getRequestURI();
        // Health has no private fields and remains usable by the homepage no-cors probe.
        // Opening the public entry from localhost:8080 to 127.0.0.1 is a cross-site document navigation.
        boolean entryNavigation=origin==null&&"GET".equals(req.getMethod())&&("/".equals(path)||"/index.html".equals(path))
                &&"navigate".equals(req.getHeader("Sec-Fetch-Mode"))&&"document".equals(req.getHeader("Sec-Fetch-Dest"));
        if("cross-site".equals(fetch)&&!entryNavigation)return fail(res,403,"来源不被允许");
        if(path.startsWith("/library/")) {
            HttpSession librarySession=req.getSession(false);
            res.setHeader("Cache-Control","no-store");
            // Quartz 构建使用经清理的 Markdown，页面内置脚本仅在资料站路径启用。
            res.setHeader("Content-Security-Policy","default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'");
            if(librarySession==null||!Boolean.TRUE.equals(librarySession.getAttribute("authenticated"))) {res.sendRedirect("/");return false;}
        }
        if(!path.startsWith("/api/"))return true;
        res.setHeader("Cache-Control","no-store");
        if(path.equals("/api/auth/status")||path.equals("/api/auth/login")||path.equals("/api/auth/setup"))return true;
        HttpSession session=req.getSession(false);
        if(session==null||!Boolean.TRUE.equals(session.getAttribute("authenticated")))return fail(res,401,"请先登录个人空间");
        if(!"GET".equals(req.getMethod())&&!"HEAD".equals(req.getMethod())) {
            String csrf=req.getHeader("X-CSRF-Token");
            if(csrf==null||!MessageDigest.isEqual(csrf.getBytes("UTF-8"),String.valueOf(session.getAttribute("csrf")).getBytes("UTF-8")))return fail(res,403,"会话校验失败，请刷新页面");
        }
        return true;
    }
    /**
     * 写出统一的失败响应并返回 {@code false}，便于在 {@link #preHandle} 里单行短路。
     *
     * @param res     响应对象，会被设置状态码与 JSON Content-Type
     * @param code    401（未登录）或 403（来源、CSRF 校验失败）
     * @param message 回显给前端的中文提示，不含内部细节
     * @return 恒为 {@code false}
     */
    private boolean fail(HttpServletResponse res,int code,String message)throws Exception{res.setStatus(code);res.setContentType("application/json;charset=UTF-8");json.writeValue(res.getWriter(),Api.map("success",false,"message",message));return false;}
    /**
     * 设置或校验密码，并签发新的登录 Session。
     *
     * <p>{@code synchronized} 保证限流窗口与会话状态在并发登录下不会互相踩踏。限流按
     * 来源地址在 60 秒窗口内累计，第 11 次起返回 429，成功登录会清零计数。
     * 初始化分支在已有凭据时返回 409；登录分支用定长比较，避免按耗时猜测密码。
     * 签发新会话前先作废旧会话，防止会话固定攻击。</p>
     *
     * @param password 8–128 个字符；长度不符直接 422，不做截断或修剪
     * @param setup    {@code true} 表示首次设置密码，{@code false} 表示校验既有密码
     * @param req      用于读取来源地址并重建会话
     * @throws org.springframework.web.server.ResponseStatusException 422 密码不合规、
     *         409 已初始化、401 密码错误或 429 尝试过于频繁
     */
    public synchronized void authenticate(String password,boolean setup,HttpServletRequest req) {
        Api.require(password!=null&&password.length()>=8&&password.length()<=128,"密码应为8到128个字符");
        String key=req.getRemoteAddr();long current=System.currentTimeMillis();long[] rate=attempts.computeIfAbsent(key,k->new long[]{current,0});
        if(current-rate[0]>60000){rate[0]=current;rate[1]=0;}if(++rate[1]>10)throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.TOO_MANY_REQUESTS,"尝试过于频繁，请稍后重试");
        Map<String,Object> auth=store.get("auth");
        if(setup){if(auth!=null)throw Api.conflict("个人空间已初始化，请登录");byte[] salt=new byte[32];new SecureRandom().nextBytes(salt);String encoded=Base64.getEncoder().encodeToString(salt);store.put("auth",Api.map("salt",encoded,"hash",hash(password,encoded)));}
        else {if(auth==null||!MessageDigest.isEqual(hash(password,Api.text(auth,"salt")).getBytes(java.nio.charset.StandardCharsets.UTF_8),Api.text(auth,"hash").getBytes(java.nio.charset.StandardCharsets.UTF_8)))throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.UNAUTHORIZED,"密码不正确");}
        HttpSession prior=req.getSession(false);if(prior!=null)prior.invalidate();HttpSession session=req.getSession(true);session.setAttribute("authenticated",true);session.setAttribute("csrf",Api.id());rate[1]=0;
    }
    /**
     * 用 PBKDF2-HMAC-SHA256 派生密码哈希。
     *
     * @param password 明文密码，只在本方法内存在，派生后立即清空字符数组
     * @param salt     Base64 编码的 32 字节随机盐，与哈希一起存入状态文件
     * @return Base64 编码的 256 位派生密钥
     * @throws IllegalStateException 运行环境缺少该算法时抛出，属不可恢复的配置错误
     */
    private String hash(String password,String salt){try{PBEKeySpec spec=new PBEKeySpec(password.toCharArray(),Base64.getDecoder().decode(salt),210000,256);try{return Base64.getEncoder().encodeToString(SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).getEncoded());}finally{spec.clearPassword();}}catch(Exception e){throw new IllegalStateException("密码处理失败");}}
    /**
     * 读取当前登录态。
     *
     * @param req 当前请求；不会为匿名访问新建 Session
     * @return {@code initialized/authenticated/csrf_token}；未登录时令牌子项为 {@code null}
     */
    public Map<String,Object> status(HttpServletRequest req){HttpSession s=req.getSession(false);boolean logged=s!=null&&Boolean.TRUE.equals(s.getAttribute("authenticated"));return Api.map("initialized",store.get("auth")!=null,"authenticated",logged,"csrf_token",logged?s.getAttribute("csrf"):null);}
}
