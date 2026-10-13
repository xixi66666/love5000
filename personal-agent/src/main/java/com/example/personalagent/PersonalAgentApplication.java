package com.example.personalagent;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
@MapperScan("com.example.personalagent.storage")
public class PersonalAgentApplication {
    public static void main(String[] args) { SpringApplication.run(PersonalAgentApplication.class, args); }
}
