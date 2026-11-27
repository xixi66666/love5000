package com.ycxandwuqian.love.controller;

import com.example.common.util.OssUtil;
import com.ycxandwuqian.love.dao.PhotoDao;
import com.ycxandwuqian.love.service.PhotoService;
import com.ycxandwuqian.love.service.PhotoServiceImpl;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
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
 * 照片墙的 REST 接入层。
 *
 * <p>挂在 {@code /api/photos} 下，提供上传、列表、删除三个端点。本类只做 multipart 与
 * 路径参数绑定，校验、OSS 写入、补偿删除和数据库访问都在 {@link PhotoService} 内完成；
 * 响应统一为 {@code {success, message, ...}} 形式的 Map，失败信息放在 {@code message} 里
 * 而不是抛异常。</p>
 *
 * <p>两个依赖都用 {@link ObjectProvider} 延迟获取，因此 OSS 关闭
 * （{@code LOVE530_OSS_ENABLED=false}，容器中没有 {@code OssUtil} Bean）时本控制器仍能创建：
 * 上传接口会返回 "OSS is not configured" 的可读失败，列表与删除不受影响。</p>
 */
@RestController
@RequestMapping("/api/photos")
public class UploadPhotoController {

    /** 照片业务实现，构造时确定并全程复用。 */
    private final PhotoService photoService;

    /**
     * Spring 注入用构造器：优先复用容器中的 {@link PhotoService}，缺失时现场装配默认实现。
     *
     * <p>允许 {@code PhotoService} 缺席，是为了让只注册了 DAO 与 OSS 的上下文（例如切片测试）
     * 也能创建控制器，而不必额外声明业务 Bean。</p>
     *
     * @param ossUtilProvider      OSS 工具的延迟提供者；OSS 关闭时取不到实例
     * @param photoDao             照片表 DAO，不允许为 {@code null}
     * @param photoServiceProvider 业务实现的延迟提供者，可被测试替身替换
     */
    @Autowired
    public UploadPhotoController(ObjectProvider<OssUtil> ossUtilProvider,
                                 PhotoDao photoDao,
                                 ObjectProvider<PhotoService> photoServiceProvider) {
        PhotoService availableService = photoServiceProvider.getIfAvailable();
        this.photoService = availableService != null
                ? availableService
                : new PhotoServiceImpl(ossUtilProvider, photoDao);
    }

    /**
     * 保留原构造签名，便于在 Spring MVC 切片或直接实例化时复用同一套照片业务。
     *
     * @param ossUtilProvider OSS 工具的延迟提供者
     * @param photoDao        照片表 DAO
     */
    public UploadPhotoController(ObjectProvider<OssUtil> ossUtilProvider, PhotoDao photoDao) {
        this.photoService = new PhotoServiceImpl(ossUtilProvider, photoDao);
    }

    /**
     * 上传一张照片。
     *
     * @param file        图片文件，必填；后缀仅允许 jpg、jpeg、png、gif、webp
     * @param category    照片分类，必填，取值 cat、girl、us 之一（大小写与首尾空白会被归一化）
     * @param description 展示用描述，可省略；省略时由分类与上传时间自动生成
     * @return 成功时含 OSS 访问地址 {@code url} 与照片摘要 {@code photo}，失败含可读的 {@code message}
     */
    @PostMapping("/upload")
    public Map<String, Object> uploadPhoto(@RequestParam("file") MultipartFile file,
                                           @RequestParam("category") String category,
                                           @RequestParam(value = "description", defaultValue = "") String description) {
        return photoService.uploadPhoto(file, category, description);
    }

    /**
     * 查询照片列表。
     *
     * @return 成功时含按上传时间倒序的 {@code photos}；数据库不可用时
     *         {@code success=false}、{@code photos} 为空列表，页面据此显示空态而不是报错
     */
    @GetMapping
    public Map<String, Object> listPhotos() {
        return photoService.listPhotos();
    }

    /**
     * 删除一张照片。
     *
     * <p>服务层会先删数据库记录再删 OSS 对象，并在 OSS 清理失败时回滚事务，
     * 具体顺序与补偿逻辑见 {@link PhotoService#deletePhoto(Long)}。</p>
     *
     * @param id 照片主键，路径变量
     * @return 成功时回显 {@code id}；记录不存在或清理失败时返回 {@code success=false} 与原因
     */
    @DeleteMapping("/{id}")
    public Map<String, Object> deletePhoto(@PathVariable("id") Long id) {
        return photoService.deletePhoto(id);
    }
}
