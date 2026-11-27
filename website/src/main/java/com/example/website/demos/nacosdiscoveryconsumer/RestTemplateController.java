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
// 说明：本文件整体被逐行注释，不参与编译，仅作为负载均衡 RestTemplate 的示例保留，
// 不是站点实际暴露的接口（当前访问 /call/echo/{message} 不会命中任何处理器）。
// 示例意图：用 @LoadBalanced 的 RestTemplate 把 http://nacos-service/... 中的服务名交给
// 注册中心解析为实例地址，从而不需要写死提供者的主机和端口。
// 恢复使用时需把包名改为 com.example.website，并确认 spring-cloud-loadbalancer 依赖存在。
//
//package com.example.love530.demos.nacosdiscoveryconsumer;
//
//import org.springframework.beans.factory.annotation.Autowired;
//import org.springframework.cloud.client.loadbalancer.LoadBalanced;
//import org.springframework.context.annotation.Bean;
//import org.springframework.web.bind.annotation.GetMapping;
//import org.springframework.web.bind.annotation.PathVariable;
//import org.springframework.web.bind.annotation.RestController;
//import org.springframework.web.client.RestTemplate;
//
//@RestController
//public class RestTemplateController {
//
//    @LoadBalanced
//    @Autowired
//    public RestTemplate restTemplate;
//
//    @LoadBalanced
//    @Bean
//    public RestTemplate restTemplate() {
//        return new RestTemplate();
//    }
//
//    @GetMapping("/call/echo/{message}")
//    public String callEcho(@PathVariable String message) {
//        // 访问应用 nacos-service 的 REST "/echo/{message}"
//        return restTemplate.getForObject("http://nacos-service/echo/" + message, String.class);
//    }
//}
