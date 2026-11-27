///*
// * Licensed to the Apache Software Foundation (ASF) under one or more
// * contributor license agreements.  See the NOTICE file distributed with
// * this work for additional information regarding copyright ownership.
// * The ASF licenses this file to You under the Apache License, Version 2.0
// * (the "License"); you may not use this file except in compliance with
// * the License.  You may obtain a copy of the License at
// *
// *     http://www.apache.org/licenses/LICENSE-2.0
// *
// * Unless required by applicable law or agreed to in writing, software
// * distributed under the License is distributed on an "AS IS" BASIS,
// * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// * See the License for the specific language governing permissions and
// * limitations under the License.
// */
//
// 说明：本文件整体被逐行注释，不参与编译，仅作为 @EnableDiscoveryClient 的注册中心接入示例保留。
// 示例意图：开启 Spring Cloud 服务发现，让应用以服务名注册到 Nacos 并解析其他服务实例。
// 当前 website 的可用性判断由 integration/health 的固定服务清单加 HTTP 探测完成，不依赖 Nacos；
// 包名仍是迁移前的 com.example.love530，恢复使用时需改为 com.example.website 并补回相应依赖。
//
//package com.example.love530.nacosdiscovery;
//
//import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
//import org.springframework.context.annotation.Configuration;
//
///**
// * @author <a href="mailto:chenxilzx1@gmail.com">theonefx</a>
// */
//@EnableDiscoveryClient
//@Configuration
//public class NacosDiscoveryConfiguration {
//}
