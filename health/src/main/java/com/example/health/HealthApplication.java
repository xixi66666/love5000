package com.example.health;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;

@SpringBootApplication(scanBasePackages={"com.example.health", "com.example.personalagent"}, exclude=DataSourceAutoConfiguration.class)
public class HealthApplication {
    public static void main(String[] args) { SpringApplication.run(HealthApplication.class,args); }
}
