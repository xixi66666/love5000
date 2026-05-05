package com.example.website.auth;

import org.springframework.stereotype.Component;

import javax.annotation.PostConstruct;

@Component
public class AuthDatabaseInitializer {

    private final WebsiteAuthUserRepository websiteAuthUserRepository;

    public AuthDatabaseInitializer(WebsiteAuthUserRepository websiteAuthUserRepository) {
        this.websiteAuthUserRepository = websiteAuthUserRepository;
    }

    @PostConstruct
    public void initialize() {
        websiteAuthUserRepository.createTableIfAbsent();
    }
}
