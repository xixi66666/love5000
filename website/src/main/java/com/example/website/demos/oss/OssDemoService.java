///*
// * Copyright 2013-2018 the original author or authors.
// *
// * Licensed under the Apache License, Version 2.0 (the "License");
// * you may not use this file except in compliance with the License.
// * You may obtain a copy of the License at
// *
// *      https://www.apache.org/licenses/LICENSE-2.0
// *
// * Unless required by applicable law or agreed to in writing, software
// * distributed under the License is distributed on an "AS IS" BASIS,
// * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// * See the License for the specific language governing permissions and
// * limitations under the License.
// */
//
//
// 说明：本文件整体被逐行注释，不参与编译，仅作为在 Spring 应用中读写 OSS 的示例保留，
// 不是站点实际使用的上传/下载实现。示例覆盖两条路径：把 oss://bucket/key 当作 Resource
// 读写（需要 OSS 的 Resource 协议支持），以及直接调用 OSS 客户端的 getObject/putObject。
// 示例依赖 classpath:/oss-test.json，当前工程没有该文件，直接恢复调用会因资源缺失而失败；
// 生产代码请走 common 模块的 OssUtil，并保持 OSS 默认关闭、凭据只来自环境变量。
//
//package com.example.love530.demos.oss;
//
//import java.io.IOException;
//import java.io.InputStream;
//import java.io.OutputStream;
//
//import com.aliyun.oss.OSS;
//import com.aliyun.oss.common.utils.IOUtils;
//import com.aliyun.oss.model.OSSObject;
//import org.apache.commons.codec.CharEncoding;
//
//import org.springframework.beans.factory.annotation.Autowired;
//import org.springframework.beans.factory.annotation.Value;
//import org.springframework.core.io.Resource;
//import org.springframework.core.io.WritableResource;
//import org.springframework.stereotype.Service;
//import org.springframework.util.StreamUtils;
//
///**
// * This demo code show you how to use oss in your application. You can use is directly or
// * refactor is to implement your own logic|architecture.
// *
// * @author <a href="mailto:chenxilzx1@gmail.com">theonefx</a>
// */
//@Service
//public class OssDemoService {
//
//    @Autowired
//    private OSS ossClient;
//
//    /**
//     * the file in local machine.
//     */
//    @Value("classpath:/oss-test.json")
//    private Resource localFile;
//
//    /**
//     * the file in oss remote server.
//     */
//    @Value("oss://" + OssConfig.BUCKET_NAME + "/oss-test.json")
//    private Resource remoteFile;
//
//    public String readRemoteFileViaResource() throws IOException {
//        return IOUtils.readStreamAsString(remoteFile.getInputStream(),
//                CharEncoding.UTF_8);
//    }
//
//    public String readRemoteFileViaClient() throws IOException {
//        OSSObject ossObject = ossClient.getObject(OssConfig.BUCKET_NAME, "oss-test.json");
//        return IOUtils.readStreamAsString(ossObject.getObjectContent(),
//                CharEncoding.UTF_8);
//    }
//
//    public void uploadWithClient() {
//        ossClient.putObject(OssConfig.BUCKET_NAME, "oss-test.json",
//                this.getClass().getClassLoader().getResourceAsStream("oss-test.json"));
//    }
//
//    public void uploadWithOutputStream() throws IOException {
//        try (OutputStream out = ((WritableResource) this.remoteFile).getOutputStream();
//             InputStream in = localFile.getInputStream()) {
//            StreamUtils.copy(in, out);
//        }
//    }
//}
