package com.example.personalagent;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
/**
 * 统一响应体与参数校验的小工具，供 Controller 与 Service 组装 JSON 结构。
 *
 * <p>属基础工具层，被几乎所有 Web 组件引用。成功响应约定为
 * {@code {"success":true,"data":...}}，失败响应为
 * {@code {"success":false,"message":"..."}}，后者由
 * {@link com.example.personalagent.controller.ErrorAdvice} 从异常翻译而来。</p>
 *
 * <p>校验失败一律抛 {@link ResponseStatusException}：{@link #require(boolean, String)}
 * 映射 422，{@link #conflict(String)} 映射 409，因此 Service 层只需表达业务语义，
 * 不必拼装 HTTP 状态码。工具类不可实例化。</p>
 */
public final class Api {
    private Api(){}
    /**
     * 按「键、值、键、值」交替的可变参数构造有序 Map。
     *
     * @param pairs 交替出现的键值对；键为 {@code null} 时按字符串 {@code "null"} 记录
     * @return {@link LinkedHashMap}，保持调用方给定顺序，使响应字段顺序稳定
     * @throws ArrayIndexOutOfBoundsException 传入奇数个参数（最后一项没有配对的键或值）
     */
    public static Map<String,Object> map(Object... pairs){Map<String,Object> m=new LinkedHashMap<>();for(int i=0;i<pairs.length;i+=2)m.put(String.valueOf(pairs[i]),pairs[i+1]);return m;}
    /**
     * 包装成功响应 {@code {"success":true,"data":...}}。
     *
     * @param data 任意可序列化负载，允许 {@code null}
     */
    public static Map<String,Object> ok(Object data){return map("success",true,"data",data);}
    /**
     * 读取 Map 中的字符串值。
     *
     * <p>缺键或值为 {@code null} 时返回空串而不是字面量 {@code "null"}：前端把请求体
     * 字段直接透传进来，缺字段与空串在这里被归一成同一种语义。</p>
     */
    public static String text(Map<String,Object> m,String key){return m.get(key)==null?"":String.valueOf(m.get(key));}
    /**
     * 断言业务条件成立，否则以 HTTP 422 拒绝请求。
     *
     * @param condition 期望为真的业务条件
     * @param message   直接回显给前端的简体中文提示，不得包含路径或密钥
     * @throws ResponseStatusException 条件为假时抛出，携带 422 与给定提示
     */
    public static void require(boolean condition,String message){if(!condition)throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,message);}
    /** 构造 HTTP 409 冲突异常，用于乐观锁失败、路径被占用、仓库已切换等并发语义。 */
    public static ResponseStatusException conflict(String message){return new ResponseStatusException(HttpStatus.CONFLICT,message);}
    /** 生成不透明记录标识；笔记文件名、附件名与构建目录名都以它作为主键。 */
    public static String id(){return UUID.randomUUID().toString();}
    /**
     * 把时刻格式化为固定 9 位小数秒的 ISO-8601 字符串。
     *
     * <p>位数固定是为了让同一时间字段在文件内容与 JSON 响应中保持字节可比，
     * 便于前端逐字比较与按字符串排序。</p>
     */
    public static String instant(java.time.Instant value){return new java.time.format.DateTimeFormatterBuilder().appendInstant(9).toFormatter().format(value);}
    /** 当前 UTC 时刻，格式同 {@link #instant(java.time.Instant)}。 */
    public static String now(){return instant(java.time.Instant.now());}
}
