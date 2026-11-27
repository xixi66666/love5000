package com.ycxandwuqian.love.service;

import org.springframework.stereotype.Service;

/**
 * {@link uploadPhotoService} 的空实现。
 *
 * <p>声明为 {@code @Service} 是为了让按类型注入的历史代码仍能拿到 Bean，
 * 但 {@link #uploadPhoto()} 方法体为空，不读取配置、不访问 OSS 与数据库，
 * 调用后不会产生任何记录或文件。实际照片上传请使用 {@link PhotoServiceImpl}。</p>
 */
@Service
public class uploadPhotoServiceImpl implements uploadPhotoService{

    /**
     * 空实现：仅为满足接口契约而保留方法签名，调用后不做任何事情。
     */
    @Override
    public void uploadPhoto() {

    }
}
