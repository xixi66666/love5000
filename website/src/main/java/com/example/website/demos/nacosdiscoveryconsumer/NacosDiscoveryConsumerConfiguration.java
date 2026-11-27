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
// 说明：本文件整体被逐行注释，不参与编译，仅作为 Nacos Discovery 消费端配置示例保留。
// 示例意图：用 @EnableFeignClients 开启 @FeignClient 接口的扫描与代理生成，配合
// EchoService 按服务名调用提供者。包名仍是迁移前的 com.example.love530，恢复使用时需改为
// com.example.website 并重新引入 spring-cloud-openfeign 依赖。
//
//package com.example.love530.demos.nacosdiscoveryconsumer;
//
//import org.springframework.cloud.openfeign.EnableFeignClients;
//import org.springframework.context.annotation.Configuration;
//
//@Configuration
//@EnableFeignClients // 激活 @FeignClient
//public class NacosDiscoveryConsumerConfiguration {
//
//}
