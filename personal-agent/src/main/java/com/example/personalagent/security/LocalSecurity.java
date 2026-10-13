package com.example.personalagent.security;

import com.example.personalagent.Api;
import com.example.personalagent.storage.Store;
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

@Configuration
public class LocalSecurity implements WebMvcConfigurer,HandlerInterceptor {
    private final Store store; private final ObjectMapper json;
    private final Map<String,long[]> attempts=new HashMap<>();
    public LocalSecurity(Store store,ObjectMapper json){this.store=store;this.json=json;}
    @Override public void addInterceptors(InterceptorRegistry registry){registry.addInterceptor(this).addPathPatterns("/**");}
    @Override public boolean preHandle(HttpServletRequest req,HttpServletResponse res,Object handler)throws Exception {
        res.setHeader("X-Content-Type-Options","nosniff");res.setHeader("Referrer-Policy","no-referrer");res.setHeader("X-Frame-Options","DENY");
        res.setHeader("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'");
        String host=req.getServerName();
        boolean local=InetAddress.getByName(req.getRemoteAddr()).isLoopbackAddress();
        if(!local||!("localhost".equalsIgnoreCase(host)||"127.0.0.1".equals(host)||"::1".equals(host)))return fail(res,403,"仅允许本机访问");
        if("/api/health".equals(req.getRequestURI())&&"GET".equals(req.getMethod()))return true;
        String origin=req.getHeader("Origin"),fetch=req.getHeader("Sec-Fetch-Site");
        if(origin!=null){try{URI u=URI.create(origin);int port=u.getPort()<0?80:u.getPort();if(!"http".equals(u.getScheme())||!host.equalsIgnoreCase(u.getHost())||port!=req.getServerPort())return fail(res,403,"来源不被允许");}catch(Exception e){return fail(res,403,"来源无效");}}
        String path=req.getRequestURI();
        // Health has no private fields and remains usable by the homepage no-cors probe.
        if("cross-site".equals(fetch))return fail(res,403,"来源不被允许");
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
    private boolean fail(HttpServletResponse res,int code,String message)throws Exception{res.setStatus(code);res.setContentType("application/json;charset=UTF-8");json.writeValue(res.getWriter(),Api.map("success",false,"message",message));return false;}
    public synchronized void authenticate(String password,boolean setup,HttpServletRequest req) {
        Api.require(password!=null&&password.length()>=8&&password.length()<=128,"密码应为8到128个字符");
        String key=req.getRemoteAddr();long current=System.currentTimeMillis();long[] rate=attempts.computeIfAbsent(key,k->new long[]{current,0});
        if(current-rate[0]>60000){rate[0]=current;rate[1]=0;}if(++rate[1]>10)throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.TOO_MANY_REQUESTS,"尝试过于频繁，请稍后重试");
        Map<String,Object> auth=store.get("auth","owner");
        if(setup){if(auth!=null)throw Api.conflict("个人空间已初始化，请登录");byte[] salt=new byte[32];new SecureRandom().nextBytes(salt);String encoded=Base64.getEncoder().encodeToString(salt);store.put("auth","owner",Api.map("salt",encoded,"hash",hash(password,encoded)));}
        else {if(auth==null||!MessageDigest.isEqual(hash(password,Api.text(auth,"salt")).getBytes(java.nio.charset.StandardCharsets.UTF_8),Api.text(auth,"hash").getBytes(java.nio.charset.StandardCharsets.UTF_8)))throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.UNAUTHORIZED,"密码不正确");}
        HttpSession prior=req.getSession(false);if(prior!=null)prior.invalidate();HttpSession session=req.getSession(true);session.setAttribute("authenticated",true);session.setAttribute("csrf",Api.id());rate[1]=0;
    }
    private String hash(String password,String salt){try{PBEKeySpec spec=new PBEKeySpec(password.toCharArray(),Base64.getDecoder().decode(salt),210000,256);try{return Base64.getEncoder().encodeToString(SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).getEncoded());}finally{spec.clearPassword();}}catch(Exception e){throw new IllegalStateException("密码处理失败");}}
    public Map<String,Object> status(HttpServletRequest req){HttpSession s=req.getSession(false);boolean logged=s!=null&&Boolean.TRUE.equals(s.getAttribute("authenticated"));return Api.map("initialized",store.get("auth","owner")!=null,"authenticated",logged,"csrf_token",logged?s.getAttribute("csrf"):null);}
}
