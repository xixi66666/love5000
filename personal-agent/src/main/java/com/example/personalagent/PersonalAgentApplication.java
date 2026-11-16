package com.example.personalagent;


import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;
import org.springframework.boot.autoconfigure.SpringBootApplication;


@SpringBootApplication(exclude = DataSourceAutoConfiguration.class)


public class PersonalAgentApplication {
    public static void main(String[] args) { SpringApplication.run(PersonalAgentApplication.class, args); }
}
