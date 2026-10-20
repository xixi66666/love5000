package com.example.imagetemplate.service;

import org.springframework.stereotype.Service;

import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;

/**
 * 客观质检引擎：把“修图自不自然”从主观争论变成可计算的指标。
 *
 * <p>指标分两类：
 * <ul>
 *   <li>单图绝对指标：亮度、对比度、锐度、噪点、纹理熵、肤色占比与均值。</li>
 *   <li>双图对比指标：修图前后的亮度偏移、肤色色差、结构保持度、纹理保留率。</li>
 * </ul>
 *
 * <p>核心判据来自行业实践：客户反馈的“塑料感 / 蜡像感”本质上是高频纹理被抹除，
 * 因此 {@link Comparison#getTextureRetention()}（分块高频能量保留率）是最关键的指标。
 * 组图出现肤色漂移属于交付级事故，由 {@link Comparison#getSkinColorShift()} 兜底。
 *
 * <p>所有对比都在“同尺寸、真实像素”前提下进行；宽图会被等比缩到 {@value #NORMALIZED_WIDTH}
 * 宽以控制计算量（长宽比保持不变）。
 */
@Service
public class ImageQualityMetricsService {

    /** 分析时的归一化宽度；超过此宽度才缩放，且等比缩放不失真。 */
    private static final int NORMALIZED_WIDTH = 1024;

    /** 拉普拉斯核中心权重。 */
    private static final double LAPLACIAN_CENTER = 4.0d;

    /** 平坦区判定的分位数（取局部方差最低的该比例区域）。 */
    private static final double FLAT_PERCENTILE = 10.0d;

    /** 平坦区域采样的步长（像素）。 */
    private static final int FLAT_SAMPLE_STEP = 2;

    /** 高频能量与纹理熵的分块尺寸。 */
    private static final int TEXTURE_PATCH = 4;

    /** 纹理熵的量化档数。 */
    private static final int TEXTURE_BINS = 64;

    /** 高频残差量化截断值（0-255 尺度）。 */
    private static final double HIGH_FREQ_CLIP = 64.0d;

    /** 亮度偏移告警阈值（0-255 尺度）。 */
    private static final double BRIGHTNESS_SHIFT_WARN = 8.0d;

    /** 肤色色差告警阈值（0-255 尺度）。 */
    private static final double SKIN_COLOR_SHIFT_WARN = 5.0d;

    /** 结构保持度告警阈值。 */
    private static final double STRUCTURE_WARN = 0.9d;

    /** 纹理保留率告警阈值，低于此值判定为疑似过度磨皮。 */
    private static final double TEXTURE_RETENTION_WARN = 0.75d;

    /**
     * 计算单图绝对指标。
     *
     * @param image 待分析图片，不能为空
     * @return 单图指标
     */
    public Metrics analyze(BufferedImage image) {
        if (image == null) {
            throw new IllegalArgumentException("image must not be null");
        }
        return measure(normalize(image));
    }

    /**
     * 对比“修图前”与“修图后”。
     *
     * <p>两张图尺寸必须一致：质检的意义就是在交付尺寸下逐像素比较，
     * 尺寸不一致时缩放会引入插值高频，使纹理保留率失真。
     *
     * @param baseline  修图前（原片）
     * @param retouched 修图后（交付候选）
     * @return 对比结果，含中文判定结论
     */
    public Comparison compare(BufferedImage baseline, BufferedImage retouched) {
        if (baseline == null || retouched == null) {
            throw new IllegalArgumentException("baseline and retouched must not be null");
        }
        if (baseline.getWidth() != retouched.getWidth() || baseline.getHeight() != retouched.getHeight()) {
            throw new IllegalArgumentException(
                    "baseline and retouched must have identical dimensions for a pixel-accurate check: "
                            + baseline.getWidth() + "x" + baseline.getHeight()
                            + " vs " + retouched.getWidth() + "x" + retouched.getHeight());
        }

        BufferedImage baseImage = toRgb(baseline);
        BufferedImage resultImage = toRgb(retouched);

        Comparison comparison = new Comparison();
        comparison.setBaseline(measure(baseImage));
        comparison.setRetouched(measure(resultImage));

        double[] baseLuma = extractLuma(baseImage);
        double[] resultLuma = extractLuma(resultImage);

        double baseTexture = textureEnergy(baseLuma, baseImage.getWidth(), baseImage.getHeight());
        double resultTexture = textureEnergy(resultLuma, resultImage.getWidth(), resultImage.getHeight());
        double retention = baseTexture > 0.0d ? resultTexture / baseTexture : 1.0d;

        comparison.setBrightnessShift(round(Math.abs(
                comparison.getBaseline().getBrightness() - comparison.getRetouched().getBrightness())));
        comparison.setSkinColorShift(round(skinColorDistance(comparison.getBaseline(), comparison.getRetouched())));
        comparison.setStructureRetention(round(pearson(baseLuma, resultLuma)));
        comparison.setTextureRetention(round(retention));
        comparison.setTextureEntropyRatio(round(entropyRatio(
                baseImage, resultImage, baseLuma, resultLuma)));
        comparison.setVerdict(judge(comparison));
        return comparison;
    }

    private Metrics measure(BufferedImage image) {
        int width = image.getWidth();
        int height = image.getHeight();
        double[] values = extractLuma(image);

        Metrics metrics = new Metrics();
        metrics.setWidth(width);
        metrics.setHeight(height);
        metrics.setPixelCount((long) width * height);

        double mean = mean(values);
        metrics.setBrightness(round(mean));
        metrics.setContrast(round(stdDev(values, mean)));

        Lap lap = laplacian(values, width, height);
        metrics.setSharpness(round(varianceOf(lap.response)));
        metrics.setNoise(round(flatRegionNoise(values, lap, width, height)));
        metrics.setTextureEntropy(round(textureEntropy(lap, width, height)));

        SkinStats skin = skinStats(image);
        metrics.setSkinRatio(round(skin.ratio));
        metrics.setSkinRed(skin.red);
        metrics.setSkinGreen(skin.green);
        metrics.setSkinBlue(skin.blue);
        return metrics;
    }

    private String judge(Comparison comparison) {
        StringBuilder verdict = new StringBuilder();
        if (comparison.getTextureRetention() < TEXTURE_RETENTION_WARN) {
            verdict.append("疑似过度磨皮：高频纹理保留率 ")
                    .append(comparison.getTextureRetention())
                    .append(" 低于 ")
                    .append(TEXTURE_RETENTION_WARN)
                    .append("，皮肤可能出现塑料感/蜡像感；建议降低磨皮强度或改用频率分离保留纹理。");
        }
        if (comparison.getStructureRetention() < STRUCTURE_WARN) {
            appendSpace(verdict);
            verdict.append("疑似结构漂移：结构保持度 ")
                    .append(comparison.getStructureRetention())
                    .append(" 低于 ")
                    .append(STRUCTURE_WARN)
                    .append("，可能改动了五官或脸型；建议缩窄 mask 并降低 denoise。");
        }
        if (comparison.getBrightnessShift() > BRIGHTNESS_SHIFT_WARN) {
            appendSpace(verdict);
            verdict.append("曝光漂移：亮度偏移 ")
                    .append(comparison.getBrightnessShift())
                    .append(" 超过 ")
                    .append(BRIGHTNESS_SHIFT_WARN)
                    .append("，与同组其他照片可能不一致。");
        }
        if (comparison.getSkinColorShift() > SKIN_COLOR_SHIFT_WARN) {
            appendSpace(verdict);
            verdict.append("肤色漂移：肤色色差 ")
                    .append(comparison.getSkinColorShift())
                    .append(" 超过 ")
                    .append(SKIN_COLOR_SHIFT_WARN)
                    .append("，交付组图可能出现色调不统一。");
        }
        if (verdict.length() == 0) {
            return "通过：纹理保留、结构保持、曝光与肤色漂移均在阈值内。";
        }
        return verdict.toString();
    }

    private void appendSpace(StringBuilder builder) {
        if (builder.length() > 0) {
            builder.append(' ');
        }
    }

    private double skinColorDistance(Metrics baseline, Metrics retouched) {
        if (baseline.getSkinRatio() <= 0.0d || retouched.getSkinRatio() <= 0.0d) {
            return 0.0d;
        }
        double dRed = baseline.getSkinRed() - retouched.getSkinRed();
        double dGreen = baseline.getSkinGreen() - retouched.getSkinGreen();
        double dBlue = baseline.getSkinBlue() - retouched.getSkinBlue();
        return Math.sqrt((dRed * dRed + dGreen * dGreen + dBlue * dBlue) / 3.0d);
    }

    private double entropyRatio(BufferedImage baseImage,
                                BufferedImage resultImage,
                                double[] baseLuma,
                                double[] resultLuma) {
        double baseEntropy = textureEntropy(
                laplacian(baseLuma, baseImage.getWidth(), baseImage.getHeight()),
                baseImage.getWidth(), baseImage.getHeight());
        double resultEntropy = textureEntropy(
                laplacian(resultLuma, resultImage.getWidth(), resultImage.getHeight()),
                resultImage.getWidth(), resultImage.getHeight());
        if (baseEntropy <= 0.0d) {
            return 1.0d;
        }
        return resultEntropy / baseEntropy;
    }

    /**
     * 分块高频能量：先取拉普拉斯响应（真正的高频分量），再按
     * {@value #TEXTURE_PATCH}x{@value #TEXTURE_PATCH} 分块求响应平方和后取均值。
     *
     * <p>不用“分块像素标准差”：棋盘、条纹这类周期性纹理的块内明暗像素数量恒定，
     * 标准差在模糊前后不变，会漏判纹理损失。拉普拉斯响应只保留高频，
     * 平滑后必然衰减，因此是本指标唯一可靠的度量。
     */
    private double textureEnergy(double[] values, int width, int height) {
        double[] response = laplacian(values, width, height).response;
        int patch = TEXTURE_PATCH;
        int patchesX = width / patch;
        int patchesY = height / patch;
        if (patchesX == 0 || patchesY == 0) {
            return varianceOf(response);
        }
        double sum = 0.0d;
        for (int py = 0; py < patchesY; py++) {
            for (int px = 0; px < patchesX; px++) {
                double blockSum = 0.0d;
                for (int y = 0; y < patch; y++) {
                    int rowStart = (py * patch + y) * width + px * patch;
                    for (int x = 0; x < patch; x++) {
                        double value = response[rowStart + x];
                        blockSum += value * value;
                    }
                }
                sum += blockSum / (double) (patch * patch);
            }
        }
        return sum / (double) (patchesX * patchesY);
    }

    /**
     * 纹理熵：对拉普拉斯响应做直方图统计后求香农熵。
     * 过度平滑会使响应集中到低值档位，熵值随之下降。
     */
    private double textureEntropy(Lap lap, int width, int height) {
        int[] histogram = new int[TEXTURE_BINS];
        long total = 0L;
        for (int y = 1; y < height - 1; y++) {
            int rowStart = y * width;
            for (int x = 1; x < width - 1; x++) {
                double response = Math.abs(lap.response[rowStart + x]);
                if (response > HIGH_FREQ_CLIP) {
                    response = HIGH_FREQ_CLIP;
                }
                int bin = (int) (response / HIGH_FREQ_CLIP * (TEXTURE_BINS - 1));
                histogram[bin]++;
                total++;
            }
        }
        if (total == 0L) {
            return 0.0d;
        }
        double entropy = 0.0d;
        double logTwo = Math.log(2.0d);
        for (int count : histogram) {
            if (count == 0) {
                continue;
            }
            double probability = (double) count / (double) total;
            entropy -= probability * (Math.log(probability) / logTwo);
        }
        return entropy;
    }

    /**
     * 噪点估计：取局部亮度方差最低的 {@value #FLAT_PERCENTILE}% 区域作为“平坦区”，
     * 统计这些区域的拉普拉斯响应能量。
     *
     * <p>用相对分位数而不是绝对方差阈值：真实照片里“平坦”是相对概念（皮肤、天空、幕布），
     * 固定阈值会让噪点值恒为 0。取最低分位数可自适应任意图像的纹理水平。
     */
    private double flatRegionNoise(double[] values, Lap lap, int width, int height) {
        int radius = 2;
        int sampleCount = 0;
        for (int y = radius; y < height - radius; y += FLAT_SAMPLE_STEP) {
            for (int x = radius; x < width - radius; x += FLAT_SAMPLE_STEP) {
                sampleCount++;
            }
        }
        if (sampleCount == 0) {
            return 0.0d;
        }
        double[] positions = new double[sampleCount * 3];
        int index = 0;
        for (int y = radius; y < height - radius; y += FLAT_SAMPLE_STEP) {
            for (int x = radius; x < width - radius; x += FLAT_SAMPLE_STEP) {
                double localSum = 0.0d;
                double localSquareSum = 0.0d;
                int samples = 0;
                for (int dy = -radius; dy <= radius; dy++) {
                    int rowStart = (y + dy) * width;
                    for (int dx = -radius; dx <= radius; dx++) {
                        double value = values[rowStart + x + dx];
                        localSum += value;
                        localSquareSum += value * value;
                        samples++;
                    }
                }
                double localMean = localSum / samples;
                double localVariance = localSquareSum / samples - localMean * localMean;
                positions[index++] = x;
                positions[index++] = y;
                positions[index++] = localVariance > 0.0d ? localVariance : 0.0d;
            }
        }

        double[] sorted = new double[sampleCount];
        for (int i = 0; i < sampleCount; i++) {
            sorted[i] = positions[i * 3 + 2];
        }
        java.util.Arrays.sort(sorted);
        int quantileIndex = (int) Math.floor(sampleCount * FLAT_PERCENTILE / 100.0d);
        if (quantileIndex < 0) {
            quantileIndex = 0;
        }
        if (quantileIndex >= sampleCount) {
            quantileIndex = sampleCount - 1;
        }
        double threshold = sorted[quantileIndex];

        double sum = 0.0d;
        int count = 0;
        for (int i = 0; i < sampleCount; i++) {
            double localVariance = positions[i * 3 + 2];
            if (localVariance <= threshold) {
                int x = (int) positions[i * 3];
                int y = (int) positions[i * 3 + 1];
                double response = lap.response[y * width + x];
                sum += response * response;
                count++;
            }
        }
        if (count == 0) {
            return 0.0d;
        }
        return sum / count;
    }

    private double[] extractLuma(BufferedImage image) {
        int width = image.getWidth();
        int height = image.getHeight();
        double[] values = new double[width * height];
        boolean hasAlpha = image.getColorModel().hasAlpha();
        int index = 0;
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int argb = image.getRGB(x, y);
                if (hasAlpha && ((argb >>> 24) & 0xFF) < 128) {
                    values[index] = 255.0d;
                } else {
                    int red = (argb >> 16) & 0xFF;
                    int green = (argb >> 8) & 0xFF;
                    int blue = argb & 0xFF;
                    values[index] = 0.299d * red + 0.587d * green + 0.114d * blue;
                }
                index++;
            }
        }
        return values;
    }

    private Lap laplacian(double[] values, int width, int height) {
        double[] response = new double[values.length];
        for (int y = 1; y < height - 1; y++) {
            int rowStart = y * width;
            for (int x = 1; x < width - 1; x++) {
                int center = rowStart + x;
                response[center] = LAPLACIAN_CENTER * values[center]
                        - values[center - 1]
                        - values[center + 1]
                        - values[center - width]
                        - values[center + width];
            }
        }
        return new Lap(response);
    }

    private double mean(double[] values) {
        if (values.length == 0) {
            return 0.0d;
        }
        double sum = 0.0d;
        for (double value : values) {
            sum += value;
        }
        return sum / values.length;
    }

    private double stdDev(double[] values, double mean) {
        if (values.length == 0) {
            return 0.0d;
        }
        double sum = 0.0d;
        for (double value : values) {
            double diff = value - mean;
            sum += diff * diff;
        }
        return Math.sqrt(sum / values.length);
    }

    private double varianceOf(double[] values) {
        double mean = mean(values);
        double standardDeviation = stdDev(values, mean);
        return standardDeviation * standardDeviation;
    }

    private double pearson(double[] left, double[] right) {
        if (left.length == 0 || left.length != right.length) {
            return 0.0d;
        }
        double leftMean = mean(left);
        double rightMean = mean(right);
        double covariance = 0.0d;
        double leftVariance = 0.0d;
        double rightVariance = 0.0d;
        for (int i = 0; i < left.length; i++) {
            double leftDiff = left[i] - leftMean;
            double rightDiff = right[i] - rightMean;
            covariance += leftDiff * rightDiff;
            leftVariance += leftDiff * leftDiff;
            rightVariance += rightDiff * rightDiff;
        }
        double denominator = Math.sqrt(leftVariance * rightVariance);
        if (denominator == 0.0d) {
            return 1.0d;
        }
        return covariance / denominator;
    }

    private SkinStats skinStats(BufferedImage image) {
        int width = image.getWidth();
        int height = image.getHeight();
        long total = 0L;
        long skin = 0L;
        double redSum = 0.0d;
        double greenSum = 0.0d;
        double blueSum = 0.0d;
        boolean hasAlpha = image.getColorModel().hasAlpha();
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int argb = image.getRGB(x, y);
                if (hasAlpha && ((argb >>> 24) & 0xFF) < 128) {
                    continue;
                }
                total++;
                int red = (argb >> 16) & 0xFF;
                int green = (argb >> 8) & 0xFF;
                int blue = argb & 0xFF;
                if (isSkin(red, green, blue)) {
                    skin++;
                    redSum += red;
                    greenSum += green;
                    blueSum += blue;
                }
            }
        }
        SkinStats stats = new SkinStats();
        if (skin == 0L || total == 0L) {
            stats.ratio = 0.0d;
            stats.red = 0.0d;
            stats.green = 0.0d;
            stats.blue = 0.0d;
            return stats;
        }
        stats.ratio = (double) skin / (double) total;
        stats.red = round(redSum / skin);
        stats.green = round(greenSum / skin);
        stats.blue = round(blueSum / skin);
        return stats;
    }

    /**
     * 经典 YCbCr 肤色判定：皮肤在色度平面聚集成稳定簇，对光照变化不敏感。
     */
    private boolean isSkin(int red, int green, int blue) {
        if (!(red > 95 && green > 40 && blue > 20 && red > green && red > blue)) {
            return false;
        }
        int max = Math.max(red, Math.max(green, blue));
        int min = Math.min(red, Math.min(green, blue));
        if (max - min <= 15) {
            return false;
        }
        int cb = (int) (128 - 0.168736d * red - 0.331264d * green + 0.5d * blue);
        int cr = (int) (128 + 0.5d * red - 0.418688d * green - 0.081312d * blue);
        return cb >= 77 && cb <= 127 && cr >= 133 && cr <= 173;
    }

    /**
     * 等比缩放到 {@value #NORMALIZED_WIDTH} 宽：仅用于单图绝对指标，
     * 控制超大图的计算量。长宽比保持不变，不做变形。
     */
    private BufferedImage normalize(BufferedImage image) {
        int width = image.getWidth();
        int height = image.getHeight();
        if (width <= NORMALIZED_WIDTH) {
            return toRgb(image);
        }
        int targetHeight = Math.max(1, (int) Math.round((double) height * NORMALIZED_WIDTH / width));
        BufferedImage scaled = new BufferedImage(NORMALIZED_WIDTH, targetHeight, BufferedImage.TYPE_INT_RGB);
        Graphics2D graphics = scaled.createGraphics();
        try {
            graphics.setRenderingHint(RenderingHints.KEY_INTERPOLATION,
                    RenderingHints.VALUE_INTERPOLATION_BILINEAR);
            graphics.drawImage(image, 0, 0, NORMALIZED_WIDTH, targetHeight, null);
        } finally {
            graphics.dispose();
        }
        return scaled;
    }

    private BufferedImage toRgb(BufferedImage image) {
        if (image.getType() == BufferedImage.TYPE_INT_RGB) {
            return image;
        }
        BufferedImage copy = new BufferedImage(image.getWidth(), image.getHeight(), BufferedImage.TYPE_INT_RGB);
        Graphics2D graphics = copy.createGraphics();
        try {
            graphics.drawImage(image, 0, 0, null);
        } finally {
            graphics.dispose();
        }
        return copy;
    }

    private double round(double value) {
        if (Double.isNaN(value) || Double.isInfinite(value)) {
            return 0.0d;
        }
        return Math.round(value * 1000.0d) / 1000.0d;
    }

    private static final class Lap {

        private final double[] response;

        private Lap(double[] response) {
            this.response = response;
        }
    }

    private static final class SkinStats {

        private double ratio;

        private double red;

        private double green;

        private double blue;
    }

    /**
     * 单图绝对指标。
     */
    public static class Metrics {

        private int width;

        private int height;

        private long pixelCount;

        private double brightness;

        private double contrast;

        private double sharpness;

        private double noise;

        private double textureEntropy;

        private double skinRatio;

        private double skinRed;

        private double skinGreen;

        private double skinBlue;

        public int getWidth() {
            return width;
        }

        public void setWidth(int width) {
            this.width = width;
        }

        public int getHeight() {
            return height;
        }

        public void setHeight(int height) {
            this.height = height;
        }

        public long getPixelCount() {
            return pixelCount;
        }

        public void setPixelCount(long pixelCount) {
            this.pixelCount = pixelCount;
        }

        public double getBrightness() {
            return brightness;
        }

        public void setBrightness(double brightness) {
            this.brightness = brightness;
        }

        public double getContrast() {
            return contrast;
        }

        public void setContrast(double contrast) {
            this.contrast = contrast;
        }

        public double getSharpness() {
            return sharpness;
        }

        public void setSharpness(double sharpness) {
            this.sharpness = sharpness;
        }

        public double getNoise() {
            return noise;
        }

        public void setNoise(double noise) {
            this.noise = noise;
        }

        public double getTextureEntropy() {
            return textureEntropy;
        }

        public void setTextureEntropy(double textureEntropy) {
            this.textureEntropy = textureEntropy;
        }

        public double getSkinRatio() {
            return skinRatio;
        }

        public void setSkinRatio(double skinRatio) {
            this.skinRatio = skinRatio;
        }

        public double getSkinRed() {
            return skinRed;
        }

        public void setSkinRed(double skinRed) {
            this.skinRed = skinRed;
        }

        public double getSkinGreen() {
            return skinGreen;
        }

        public void setSkinGreen(double skinGreen) {
            this.skinGreen = skinGreen;
        }

        public double getSkinBlue() {
            return skinBlue;
        }

        public void setSkinBlue(double skinBlue) {
            this.skinBlue = skinBlue;
        }
    }

    /**
     * 双图对比结果。
     */
    public static class Comparison {

        private Metrics baseline;

        private Metrics retouched;

        private double brightnessShift;

        private double skinColorShift;

        private double structureRetention;

        private double textureRetention;

        private double textureEntropyRatio;

        private String verdict;

        public Metrics getBaseline() {
            return baseline;
        }

        public void setBaseline(Metrics baseline) {
            this.baseline = baseline;
        }

        public Metrics getRetouched() {
            return retouched;
        }

        public void setRetouched(Metrics retouched) {
            this.retouched = retouched;
        }

        public double getBrightnessShift() {
            return brightnessShift;
        }

        public void setBrightnessShift(double brightnessShift) {
            this.brightnessShift = brightnessShift;
        }

        public double getSkinColorShift() {
            return skinColorShift;
        }

        public void setSkinColorShift(double skinColorShift) {
            this.skinColorShift = skinColorShift;
        }

        public double getStructureRetention() {
            return structureRetention;
        }

        public void setStructureRetention(double structureRetention) {
            this.structureRetention = structureRetention;
        }

        public double getTextureRetention() {
            return textureRetention;
        }

        public void setTextureRetention(double textureRetention) {
            this.textureRetention = textureRetention;
        }

        public double getTextureEntropyRatio() {
            return textureEntropyRatio;
        }

        public void setTextureEntropyRatio(double textureEntropyRatio) {
            this.textureEntropyRatio = textureEntropyRatio;
        }

        public String getVerdict() {
            return verdict;
        }

        public void setVerdict(String verdict) {
            this.verdict = verdict;
        }
    }
}
