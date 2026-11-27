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
// 说明：本文件整体被逐行注释，不参与编译，也不会注册 Feign 客户端或任何端点，仅作为
// Nacos Discovery + OpenFeign 的消费端示例保留，不要把它当成站点的生产调用路径。
// 示例约定：用 @FeignClient("nacos-service") 按服务名而非固定地址定位提供者，接口方法
// 与提供者 demos/nacosdiscoveryprovider 的 GET /echo/{message} 对应。
// 注意包名仍是本次迁移前的 com.example.love530，若要恢复使用需改为 com.example.website，
// 并重新引入 spring-cloud-openfeign 依赖；当前 website 的服务健康检查不经过 Nacos。
//
//package com.example.love530.demos.nacosdiscoveryconsumer;
//
//import org.springframework.cloud.openfeign.FeignClient;
//import org.springframework.web.bind.annotation.GetMapping;
//import org.springframework.web.bind.annotation.PathVariable;
//
//@FeignClient("nacos-service") // 指向服务提供者应用
//public interface EchoService {
//
//    @GetMapping("/echo/{message}")
//    String echo(@PathVariable("message") String message);
//}
