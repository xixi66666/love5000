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
// 说明：本文件整体被逐行注释，不参与编译，仅作为 OpenFeign 消费端控制器的示例保留，
// 不是站点实际暴露的接口（当前访问 /feign/echo/{message} 不会命中任何处理器）。
// 示例链路：GET /feign/echo/{message} → EchoService（@FeignClient）→ 提供者 nacos-service 的
// GET /echo/{message}。恢复使用时需把包名改为 com.example.website 并补回 openfeign 依赖。
//
//package com.example.love530.demos.nacosdiscoveryconsumer;
//
//import org.springframework.beans.factory.annotation.Autowired;
//import org.springframework.web.bind.annotation.GetMapping;
//import org.springframework.web.bind.annotation.PathVariable;
//import org.springframework.web.bind.annotation.RestController;
//
//@RestController
//public class OpenFeignController {
//
//    @Autowired
//    private EchoService echoService;
//
//    @GetMapping("/feign/echo/{message}")
//    public String feignEcho(@PathVariable String message) {
//        return echoService.echo(message);
//    }
//}
