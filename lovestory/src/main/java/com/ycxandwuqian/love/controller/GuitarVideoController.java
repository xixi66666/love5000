package com.ycxandwuqian.love.controller;

import com.ycxandwuqian.love.service.GuitarVideoService;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

/**
 * 吉他视频卡片的 REST 接入层。
 *
 * <p>挂在 {@code /api/guitar-videos} 下，只处理 multipart 参数绑定与响应透传；
 * 标题校验、后缀白名单、OSS 上传、封面兜底和软删除等业务规则全部委托给
 * {@link GuitarVideoService}。响应统一为 {@code {success, message, ...}} 形式的 Map，
 * 失败信息放在 {@code message} 里而不是抛异常，因此本层不含 try-catch。</p>
 *
 * <p>视频与封面分别以 {@code file}、{@code cover} 字段提交；封面可选，
 * 前端未选择时会先从本地视频截帧再一并上传。</p>
 */
@RestController
@RequestMapping("/api/guitar-videos")
public class GuitarVideoController {

    private final GuitarVideoService guitarVideoService;

    /**
     * 创建控制器。
     *
     * @param guitarVideoService 视频业务实现；必须非空，Spring 通过构造器注入
     */
    public GuitarVideoController(GuitarVideoService guitarVideoService) {
        this.guitarVideoService = guitarVideoService;
    }

    /**
     * 查询全部展示中的视频卡片。
     *
     * @return 成功时含 {@code success=true} 与按排序值倒序的 {@code videos} 列表；
     *         数据库不可用时 {@code success=false}、{@code videos} 为空列表，页面据此隐藏该模块
     */
    @GetMapping
    public Map<String, Object> listVideos() {
        return guitarVideoService.listVideos();
    }

    /**
     * 上传视频，可选同时上传封面。
     *
     * <p>所有字段都以 {@code multipart/form-data} 提交；校验与落库顺序由
     * {@link GuitarVideoService#uploadVideo} 决定，本方法不做任何预判。</p>
     *
     * @param file        视频文件，必填；后缀仅允许 mp4、webm、mov
     * @param cover       封面图，可为 {@code null}；提供时后缀仅允许 jpg、jpeg、png、webp
     * @param title       标题，必填，服务端去空白后不得为空
     * @param description 描述，可省略，默认空字符串
     * @param tag         标签，可省略，默认空字符串
     * @param sortOrder   排序值，可省略；缺省时按 0 处理，数值越大越靠前
     * @return 统一响应体：成功含 {@code video} 卡片信息，失败含可读的 {@code message}
     */
    @PostMapping("/upload")
    public Map<String, Object> uploadVideo(@RequestParam("file") MultipartFile file,
                                           @RequestParam(value = "cover", required = false) MultipartFile cover,
                                           @RequestParam("title") String title,
                                           @RequestParam(value = "description", defaultValue = "") String description,
                                           @RequestParam(value = "tag", defaultValue = "") String tag,
                                           @RequestParam(value = "sortOrder", required = false) Integer sortOrder) {
        return guitarVideoService.uploadVideo(file, cover, title, description, tag, sortOrder);
    }

    /**
     * 为已有视频单独上传（或替换）封面。
     *
     * @param id    视频主键，路径变量；记录不存在时返回 {@code success=false}
     * @param cover 封面图，必填；后缀仅允许 jpg、jpeg、png、webp
     * @return 成功时含更新后的 {@code video} 卡片信息，失败含可读的 {@code message}
     */
    @PostMapping("/{id}/cover")
    public Map<String, Object> uploadCover(@PathVariable("id") Long id,
                                           @RequestParam("cover") MultipartFile cover) {
        return guitarVideoService.uploadCover(id, cover);
    }

    /**
     * 删除视频卡片。
     *
     * <p>服务层执行的是软删除：数据库里只把状态置为隐藏，OSS 上的视频与封面对象会被尽力清理，
     * 因此删除后列表不再返回该卡片，但记录本身仍保留可追溯。</p>
     *
     * @param id 视频主键，路径变量
     * @return 成功时回显 {@code id}，记录不存在或清理失败时返回 {@code success=false} 与原因
     */
    @DeleteMapping("/{id}")
    public Map<String, Object> deleteVideo(@PathVariable("id") Long id) {
        return guitarVideoService.deleteVideo(id);
    }
}
