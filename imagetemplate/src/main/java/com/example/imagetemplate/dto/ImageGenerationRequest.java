package com.example.imagetemplate.dto;

import java.util.LinkedHashMap;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class ImageGenerationRequest {

    private Map<String, Object> variables = new LinkedHashMap<String, Object>();

    private String extraInstruction;

    private String prompt;

    private String size = "1024x1024";

    private String quality = "low";

    private String outputFormat = "png";

    private String background = "auto";

    private List<ReferenceImageInput> referenceImages = new ArrayList<ReferenceImageInput>();

    public Map<String, Object> getVariables() {
        return variables;
    }

    public void setVariables(Map<String, Object> variables) {
        this.variables = variables;
    }

    public String getExtraInstruction() {
        return extraInstruction;
    }

    public void setExtraInstruction(String extraInstruction) {
        this.extraInstruction = extraInstruction;
    }

    public String getPrompt() {
        return prompt;
    }

    public void setPrompt(String prompt) {
        this.prompt = prompt;
    }

    public String getSize() {
        return size;
    }

    public void setSize(String size) {
        this.size = size;
    }

    public String getQuality() {
        return quality;
    }

    public void setQuality(String quality) {
        this.quality = quality;
    }

    public String getOutputFormat() {
        return outputFormat;
    }

    public void setOutputFormat(String outputFormat) {
        this.outputFormat = outputFormat;
    }

    public String getBackground() {
        return background;
    }

    public void setBackground(String background) {
        this.background = background;
    }

    public List<ReferenceImageInput> getReferenceImages() {
        return referenceImages;
    }

    public void setReferenceImages(List<ReferenceImageInput> referenceImages) {
        this.referenceImages = referenceImages;
    }
}
