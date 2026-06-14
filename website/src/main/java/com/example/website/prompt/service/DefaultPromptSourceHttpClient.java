package com.example.website.prompt.service;

import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Component
public class DefaultPromptSourceHttpClient implements PromptSourceHttpClient {

    private final RestTemplate restTemplate = new RestTemplate();

    @Override
    public String fetch(String url) {
        String body = restTemplate.getForObject(url, String.class);
        if (body == null) {
            return "";
        }
        if (body.length() > 120000) {
            return body.substring(0, 120000);
        }
        return body;
    }
}
