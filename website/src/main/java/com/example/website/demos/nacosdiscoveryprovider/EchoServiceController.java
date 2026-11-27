/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package com.example.website.demos.nacosdiscoveryprovider;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

/**
 * Nacos Discovery 示例中的服务提供者端点。
 *
 * <p>属于 {@code demos} 示例包，只演示被消费方按服务名调用的 REST 契约：
 * {@code GET /echo/{message}} 回显 {@code "[ECHO] : " + message}。路径与
 * {@code demos/nacosdiscoveryconsumer} 里被注释掉的 {@code EchoService} Feign 客户端一致，
 * 但消费端当前未启用，所以本端点在站点里没有实际调用方。</p>
 *
 * <p>非生产路径：业务接口不要继续加在这里。</p>
 */
@RestController
public class EchoServiceController {

    /**
     * 回显路径中的消息，用于联调服务发现与服务间调用是否打通。
     *
     * @param message 路径变量，原样拼进响应；不做长度或字符集校验
     * @return 形如 {@code [ECHO] : hello} 的纯文本
     */
    @GetMapping("/echo/{message}")
    public String echo(@PathVariable String message) {
        return "[ECHO] : " + message;
    }
}
