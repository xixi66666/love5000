package com.example.imagetemplate.service;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.awt.image.BufferedImage;
import java.util.Random;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * {@link ImageQualityMetricsService} 的行为测试。
 *
 * <p>重点是验证判据的“方向正确性”：模糊化必须让纹理保留率下降并触发过度磨皮告警，
 * 提亮必须触发曝光漂移告警，同图对比必须判为通过。这些是业务可用性的前提。
 */
class ImageQualityMetricsServiceTest {

    private static final int WIDTH = 200;

    private static final int HEIGHT = 200;

    private final ImageQualityMetricsService service = new ImageQualityMetricsService();

    @Test
    @DisplayName("纯色图：亮度等于该灰度，对比度与锐度为零")
    void shouldReportFlatMetricsForSolidImage() {
        BufferedImage image = solid(WIDTH, HEIGHT, 120);

        ImageQualityMetricsService.Metrics metrics = service.analyze(image);

        assertThat(metrics.getWidth()).isEqualTo(WIDTH);
        assertThat(metrics.getHeight()).isEqualTo(HEIGHT);
        assertThat(metrics.getPixelCount()).isEqualTo((long) WIDTH * HEIGHT);
        assertThat(metrics.getBrightness()).isEqualTo(120.0d);
        assertThat(metrics.getContrast()).isEqualTo(0.0d);
        assertThat(metrics.getSharpness()).isEqualTo(0.0d);
        assertThat(metrics.getNoise()).isEqualTo(0.0d);
    }

    @Test
    @DisplayName("含纹理图：锐度与纹理熵显著高于纯色图")
    void shouldReportHigherSharpnessForTexturedImage() {
        BufferedImage flat = solid(WIDTH, HEIGHT, 128);
        BufferedImage textured = checkerboard(WIDTH, HEIGHT, 16);

        ImageQualityMetricsService.Metrics flatMetrics = service.analyze(flat);
        ImageQualityMetricsService.Metrics texturedMetrics = service.analyze(textured);

        assertThat(texturedMetrics.getSharpness()).isGreaterThan(flatMetrics.getSharpness());
        assertThat(texturedMetrics.getTextureEntropy()).isGreaterThan(flatMetrics.getTextureEntropy());
        assertThat(texturedMetrics.getContrast()).isGreaterThan(flatMetrics.getContrast());
    }

    @Test
    @DisplayName("同图对比：纹理保留率与结构保持度为 1，判定通过")
    void shouldPassWhenComparingImageWithItself() {
        BufferedImage image = checkerboard(WIDTH, HEIGHT, 16);

        ImageQualityMetricsService.Comparison comparison = service.compare(image, image);

        assertThat(comparison.getTextureRetention()).isBetween(0.99d, 1.01d);
        assertThat(comparison.getStructureRetention()).isBetween(0.99d, 1.01d);
        assertThat(comparison.getTextureEntropyRatio()).isBetween(0.99d, 1.01d);
        assertThat(comparison.getBrightnessShift()).isLessThan(0.001d);
        assertThat(comparison.getVerdict()).startsWith("通过");
    }

    @Test
    @DisplayName("模糊化（模拟过度磨皮）：纹理保留率下降并触发过度磨皮告警")
    void shouldWarnAboutOverSmoothingWhenImageIsBlurred() {
        BufferedImage original = checkerboard(WIDTH, HEIGHT, 16);
        BufferedImage blurred = boxBlur(original, 3);

        ImageQualityMetricsService.Comparison comparison = service.compare(original, blurred);

        assertThat(comparison.getTextureRetention())
                .as("模糊后高频能量应低于原图")
                .isLessThan(1.0d);
        assertThat(comparison.getTextureRetention())
                .as("3 像素半径模糊应触发过度磨皮阈值")
                .isLessThan(0.75d);
        assertThat(comparison.getVerdict()).contains("疑似过度磨皮");
    }

    @Test
    @DisplayName("提亮：触发曝光漂移告警")
    void shouldWarnAboutBrightnessShiftWhenImageIsBrightened() {
        BufferedImage original = midGradient(WIDTH, HEIGHT, 100);
        BufferedImage brightened = midGradient(WIDTH, HEIGHT, 140);

        ImageQualityMetricsService.Comparison comparison = service.compare(original, brightened);

        assertThat(comparison.getBrightnessShift()).isGreaterThan(8.0d);
        assertThat(comparison.getVerdict()).contains("曝光漂移");
    }

    @Test
    @DisplayName("肤色漂移：肤色均值变化超过阈值时告警")
    void shouldWarnAboutSkinToneShift() {
        BufferedImage original = solid(WIDTH, HEIGHT, 180, 140, 120);
        BufferedImage warmer = solid(WIDTH, HEIGHT, 210, 130, 110);

        ImageQualityMetricsService.Comparison comparison = service.compare(original, warmer);

        assertThat(comparison.getBaseline().getSkinRatio()).isGreaterThan(0.5d);
        assertThat(comparison.getSkinColorShift()).isGreaterThan(5.0d);
        assertThat(comparison.getVerdict()).contains("肤色漂移");
    }

    @Test
    @DisplayName("肤色识别：典型肤色被识别，纯蓝不被识别")
    void shouldDetectSkinTone() {
        ImageQualityMetricsService.Metrics skinMetrics =
                service.analyze(solid(WIDTH, HEIGHT, 200, 150, 130));
        ImageQualityMetricsService.Metrics blueMetrics =
                service.analyze(solid(WIDTH, HEIGHT, 40, 60, 200));

        assertThat(skinMetrics.getSkinRatio()).isGreaterThan(0.9d);
        assertThat(skinMetrics.getSkinRed()).isEqualTo(200.0d);
        assertThat(blueMetrics.getSkinRatio()).isEqualTo(0.0d);
    }

    @Test
    @DisplayName("尺寸不一致：拒绝比较并给出可读原因")
    void shouldRejectComparisonWithDifferentDimensions() {
        BufferedImage small = solid(50, 50, 100);
        BufferedImage large = solid(80, 60, 100);

        assertThatThrownBy(() -> service.compare(small, large))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("identical dimensions")
                .hasMessageContaining("50x50")
                .hasMessageContaining("80x60");
    }

    @Test
    @DisplayName("空参数：拒绝并抛出可读异常")
    void shouldRejectNullInputs() {
        assertThatThrownBy(() -> service.analyze(null))
                .isInstanceOf(IllegalArgumentException.class);

        BufferedImage image = solid(WIDTH, HEIGHT, 100);
        assertThatThrownBy(() -> service.compare(null, image))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> service.compare(image, null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    @DisplayName("噪点估计：噪声图高于纯色图")
    void shouldReportHigherNoiseForNoisyImage() {
        BufferedImage flat = solid(WIDTH, HEIGHT, 128);
        BufferedImage noisy = noisy(WIDTH, HEIGHT, 128, 20);

        ImageQualityMetricsService.Metrics flatMetrics = service.analyze(flat);
        ImageQualityMetricsService.Metrics noisyMetrics = service.analyze(noisy);

        assertThat(noisyMetrics.getNoise()).isGreaterThan(flatMetrics.getNoise());
    }

    @Test
    @DisplayName("大图归一化：超过 1024 宽的图被等比缩放，长宽比保持不变")
    void shouldPreserveAspectRatioWhenNormalizingLargeImage() {
        BufferedImage wide = solid(2048, 1024, 100);

        ImageQualityMetricsService.Metrics metrics = service.analyze(wide);

        assertThat(metrics.getWidth()).isEqualTo(1024);
        assertThat(metrics.getHeight()).isEqualTo(512);
        assertThat(metrics.getPixelCount()).isEqualTo(1024L * 512L);
    }

    // ------------------------------------------------------------------
    // 测试用图构造
    // ------------------------------------------------------------------

    private BufferedImage solid(int width, int height, int gray) {
        return solid(width, height, gray, gray, gray);
    }

    private BufferedImage solid(int width, int height, int red, int green, int blue) {
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        int rgb = (red << 16) | (green << 8) | blue;
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                image.setRGB(x, y, rgb);
            }
        }
        return image;
    }

    private BufferedImage midGradient(int width, int height, int baseGray) {
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        int rgb = (baseGray << 16) | (baseGray << 8) | baseGray;
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                image.setRGB(x, y, rgb);
            }
        }
        return image;
    }

    private BufferedImage checkerboard(int width, int height, int cellSize) {
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                boolean dark = ((x / cellSize) + (y / cellSize)) % 2 == 0;
                int value = dark ? 40 : 215;
                image.setRGB(x, y, (value << 16) | (value << 8) | value);
            }
        }
        return image;
    }

    private BufferedImage noisy(int width, int height, int baseGray, int amplitude) {
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Random random = new Random(20261015L);
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int value = clamp(baseGray + random.nextInt(amplitude * 2 + 1) - amplitude);
                image.setRGB(x, y, (value << 16) | (value << 8) | value);
            }
        }
        return image;
    }

    /**
     * 盒式模糊：模拟“模糊式磨皮”，用于验证纹理保留率判据。
     */
    private BufferedImage boxBlur(BufferedImage source, int radius) {
        int width = source.getWidth();
        int height = source.getHeight();
        BufferedImage result = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                long sum = 0L;
                int count = 0;
                for (int dy = -radius; dy <= radius; dy++) {
                    int sampleY = y + dy;
                    if (sampleY < 0 || sampleY >= height) {
                        continue;
                    }
                    for (int dx = -radius; dx <= radius; dx++) {
                        int sampleX = x + dx;
                        if (sampleX < 0 || sampleX >= width) {
                            continue;
                        }
                        sum += source.getRGB(sampleX, sampleY) & 0xFF;
                        count++;
                    }
                }
                int value = clamp((int) (sum / count));
                result.setRGB(x, y, (value << 16) | (value << 8) | value);
            }
        }
        return result;
    }

    private int clamp(int value) {
        if (value < 0) {
            return 0;
        }
        return value > 255 ? 255 : value;
    }
}
