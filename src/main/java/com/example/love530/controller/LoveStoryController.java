package com.example.love530.controller;


import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestTemplate;
import java.nio.charset.StandardCharsets;

@RestController
@RequestMapping("/lovestory")
public class LoveStoryController {


    private final RestTemplate restTemplate = new RestTemplate();
    private final String loveStoryUrl = "http://localhost:8081";

    @GetMapping({"/", "", "/index.html"})
    public ResponseEntity<String> index() {
        String html = restTemplate.getForObject(loveStoryUrl + "/", String.class);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.TEXT_HTML);
        headers.set("Content-Type", "text/html; charset=UTF-8");

        return new ResponseEntity<>(html, headers, HttpStatus.OK);
    }

    @GetMapping("/css/{file:.+}")
    public ResponseEntity<String> getCss(@PathVariable String file) {
        String css = restTemplate.getForObject(loveStoryUrl + "/css/" + file, String.class);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.valueOf("text/css"));
        headers.set("Content-Type", "text/css; charset=UTF-8");

        return new ResponseEntity<>(css, headers, HttpStatus.OK);
    }

    @GetMapping("/js/{file:.+}")
    public ResponseEntity<String> getJs(@PathVariable String file) {
        String js = restTemplate.getForObject(loveStoryUrl + "/js/" + file, String.class);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType( MediaType.valueOf("application/javascript"));
        headers.set("Content-Type", "application/javascript; charset=UTF-8");

        return new ResponseEntity<>(js, headers, HttpStatus.OK);
    }

    @GetMapping("/{path:^(?!css|js).*$}")
    public ResponseEntity<String> getStaticResources(@PathVariable String path) {
        String content = restTemplate.getForObject(loveStoryUrl + "/" + path, String.class);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.TEXT_HTML);
        headers.set("Content-Type", "text/html; charset=UTF-8");

        return new ResponseEntity<>(content, headers, HttpStatus.OK);
    }
}
