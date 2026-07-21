package com.example.guitar;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@EnableScheduling
@SpringBootApplication
public class GuitarApplication {

    public static void main(String[] args) {
        SpringApplication.run(GuitarApplication.class, args);
    }

}
