package com.ycxandwuqian.love.service;

import org.springframework.web.multipart.MultipartFile;

import javax.servlet.http.HttpServletRequest;
import java.util.Map;

/**
 * 历史遗留的照片上传接口占位。
 *
 * <p>位于服务层，但当前没有任何 Controller 或 Service 调用它，也没有真实的上传逻辑；
 * 可用的照片上传能力在 {@link PhotoService} / {@link PhotoServiceImpl} 中。
 * 保留本接口与 {@link uploadPhotoServiceImpl} 只为兼容旧引用，新代码不要在此基础上扩展。</p>
 *
 * <p>类名沿用历史写法（小写开头），与仓库内 UpperCamelCase 的命名约定不一致；
 * 新增类型请按规范命名为 {@code UploadPhotoService} 这类形式。</p>
 */
public interface uploadPhotoService {

    /**
     * 占位方法：没有参数、没有返回值，也不产生任何上传副作用。
     */
    void uploadPhoto();
}
