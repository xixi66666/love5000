package com.example.website.integration.local;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "website.local-services")
public class LocalServiceProperties {
    private String strataDir = "F:/model/Strata";
    private String aimediaDir = "D:/Code/Java_Code/AIMedia";
    private int strataPort = 9999;
    private int studioPort = 8190;
    private int h3Port = 8189;
    private int startupTimeoutSeconds = 180;

    public String getStrataDir() { return strataDir; }
    public void setStrataDir(String value) { strataDir = value; }
    public String getAimediaDir() { return aimediaDir; }
    public void setAimediaDir(String value) { aimediaDir = value; }
    public int getStrataPort() { return strataPort; }
    public void setStrataPort(int value) { strataPort = value; }
    public int getStudioPort() { return studioPort; }
    public void setStudioPort(int value) { studioPort = value; }
    public int getH3Port() { return h3Port; }
    public void setH3Port(int value) { h3Port = value; }
    public int getStartupTimeoutSeconds() { return startupTimeoutSeconds; }
    public void setStartupTimeoutSeconds(int value) { startupTimeoutSeconds = value; }
}
