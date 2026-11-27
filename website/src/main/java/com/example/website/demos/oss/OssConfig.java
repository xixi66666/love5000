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
// 说明：本文件整体被逐行注释，不参与编译，也不会创建 OSS 客户端或建桶，仅作为阿里云 OSS
// 的示例配置保留，不要把它当成站点的生产 OSS 路径。生产 OSS 能力在 common 模块：
// OssAutoConfiguration 依据 LOVE530_OSS_ENABLED 与 LOVE530_OSS_* 凭据装配 OssUtil，默认关闭。
// 示例里的 BUCKET_NAME 固定为 "spring-cloud-alibaba-test"（原示例桶），与本项目实际桶无关；
// ossBucketInitRunner 会在应用启动时检查并按需建桶，属于有外部副作用且需要凭据的操作。
//
//package com.example.love530.demos.oss;
//
//import com.aliyun.oss.OSS;
//
//import org.springframework.beans.factory.annotation.Autowired;
//import org.springframework.boot.ApplicationRunner;
//import org.springframework.context.annotation.Bean;
//import org.springframework.context.annotation.Configuration;
//
///**
// * OSS common config.
// *
// * @author <a href="mailto:chenxilzx1@gmail.com">theonefx</a>
// */
//@Configuration
//public class OssConfig {
//
//    /**
//     * OSS 示例使用的 Bucket 名称。
//     */
//    public static final String BUCKET_NAME = "spring-cloud-alibaba-test";
//
//    @Autowired
//    private OSS ossClient;
//
//    /**
//     * 可用这段代码检查或创建 OSS Bucket，也可以到
//     * <a href="https://oss.console.aliyun.com/bucket">OSS 控制台</a> 管理。
//     */
//    @Bean
//    public ApplicationRunner ossBucketInitRunner() {
//        return args -> {
//            if (!ossClient.doesBucketExist(BUCKET_NAME)) {
//                ossClient.createBucket(BUCKET_NAME);
//            }
//        };
//    }
//}
