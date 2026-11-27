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
 * 宽以控制计算量（长宽比保持不变）。</p>
 *
 * <p>本类位于 service 层，只做纯计算：不读文件、不发网络请求、不缓存中间结果，
 * 也没有可变共享状态，因此可以并发调用。所有对外数值统一保留 3 位小数，
 * {@code NaN} 与无穷大归零，保证响应可安全序列化为 JSON。</p>
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
     * <p>宽度超过 {@value #NORMALIZED_WIDTH} 的图会先等比缩小再分析，未超过时只做色彩模型转换；
     * 因此返回的 {@code width}/{@code height} 是分析用尺寸，不一定是原图尺寸。</p>
     *
     * @param image 待分析图片，不能为空
     * @return 单图指标；所有指标保留 3 位小数
     * @throws IllegalArgumentException 图片为 {@code null}
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
     * 尺寸不一致时缩放会引入插值高频，使纹理保留率失真。</p>
     *
     * <p>两张图都会先转换成 {@code TYPE_INT_RGB}（透明像素的 alpha 不再参与），
     * 再分别计算单图指标，最后得出亮度偏移、肤色色差、结构保持度（皮尔逊相关系数）、
     * 纹理保留率与纹理熵比，并由 {@link #judge} 生成中文判定结论。
     * 基准图纹理能量为 0 时纹理保留率取 1.0，避免除以零把正常图判成过度磨皮。</p>
     *
     * @param baseline  修图前（原片）
     * @param retouched 修图后（交付候选）
     * @return 对比结果，含中文判定结论
     * @throws IllegalArgumentException 任一参数为 {@code null}，或两图宽高不一致
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

    /**
     * 计算一张（已归一化尺寸的）图片的全部绝对指标。
     *
     * <p>亮度数组只提取一次，均值、标准差与拉普拉斯响应都复用它；噪点与纹理熵再复用
     * 同一份响应，避免对同一张图重复做全图卷积。肤色统计要扫 RGB 三通道，
     * 因此单独再遍历一遍原图。</p>
     *
     * @param image 已转换成 RGB 的分析图
     * @return 填好全部字段的指标对象
     */
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

    /**
     * 依据阈值生成中文判定结论。
     *
     * <p>四条告警各自独立判断，命中多条时按“纹理 → 结构 → 曝光 → 肤色”的顺序用空格拼接，
     * 因此结论里可能同时出现多个问题；一条都不命中时返回固定的“通过”文案。
     * 阈值分别为：纹理保留率低于 {@value #TEXTURE_RETENTION_WARN}（疑似过度磨皮）、
     * 结构保持度低于 {@value #STRUCTURE_WARN}（疑似改动五官）、亮度偏移超过
     * {@value #BRIGHTNESS_SHIFT_WARN}（曝光漂移）、肤色色差超过
     * {@value #SKIN_COLOR_SHIFT_WARN}（组图肤色漂移）。</p>
     *
     * @param comparison 已算好各项指标的对比结果
     * @return 中文判定结论，永不为空
     */
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

    /** 若已有内容则先补一个空格，避免多条告警文字粘连。 */
    private void appendSpace(StringBuilder builder) {
        if (builder.length() > 0) {
            builder.append(' ');
        }
    }

    /**
     * 计算两张图肤色均值的欧氏距离。
     *
     * <p>任一张图没有检出肤色像素时直接返回 0：没有肤色基准就无法比较，
     * 返回 0 可避免把“风景图”误报成肤色漂移。距离在 RGB 空间按三通道平方和
     * 除以 3 再开方，量级与单通道差异一致，便于用 0-255 尺度设阈值。</p>
     *
     * @param baseline  修图前指标
     * @param retouched 修图后指标
     * @return 肤色色差；任一方无肤色时为 0
     */
    private double skinColorDistance(Metrics baseline, Metrics retouched) {
        if (baseline.getSkinRatio() <= 0.0d || retouched.getSkinRatio() <= 0.0d) {
            return 0.0d;
        }
        double dRed = baseline.getSkinRed() - retouched.getSkinRed();
        double dGreen = baseline.getSkinGreen() - retouched.getSkinGreen();
        double dBlue = baseline.getSkinBlue() - retouched.getSkinBlue();
        return Math.sqrt((dRed * dRed + dGreen * dGreen + dBlue * dBlue) / 3.0d);
    }

    /**
     * 计算两张图的纹理熵比值。
     *
     * <p>与纹理保留率互补：保留率看高频能量强弱，熵看高频分布是否被压扁。
     * 基准熵为 0（原片本身就极平滑）时返回 1.0，不做无意义的除法。</p>
     *
     * @param baseImage   修图前图片
     * @param resultImage 修图后图片
     * @param baseLuma    修图前亮度数组
     * @param resultLuma  修图后亮度数组
     * @return 修图后熵 / 修图前熵，未舍入
     */
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

    /**
     * 把图片像素转成亮度数组（行优先）。
     *
     * <p>亮度按 ITU-R BT.601 系数 {@code 0.299R + 0.587G + 0.114B} 计算，单位为 0-255。
     * 带 alpha 的图片中，透明度低于 128 的像素按纯白（255）处理，
     * 避免透明底被当成黑色而拉低亮度、制造虚假的高频边缘。</p>
     *
     * @param image 输入图片
     * @return 长度为 {@code width * height} 的亮度数组
     */
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

    /**
     * 计算 5 点拉普拉斯响应（4 邻域，中心权重 {@value #LAPLACIAN_CENTER}）。
     *
     * <p>只遍历内部像素，最外圈保持 0，因此后续统计都跳过边界一圈，
     * 避免把边框当成高频。响应值可正可负，各指标分别按绝对值或平方使用。</p>
     *
     * @param values 亮度数组
     * @param width  图片宽度
     * @param height 图片高度
     * @return 与输入等长的响应数组
     */
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

    /** 算术平均值；空数组返回 0，避免调用方处理 {@code NaN}。 */
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

    /**
     * 总体标准差（除以 {@code n}，不是样本标准差的 {@code n-1}）。
     *
     * @param values 数组
     * @param mean   已算好的均值
     * @return 标准差；空数组返回 0
     */
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

    /**
     * 方差（标准差的平方）。
     *
     * <p>锐度与噪声都在拉普拉斯响应上取方差，因此复用该方法；
     * 先开方再平方会带来极小的浮点误差，但结果差异远低于保留的 3 位小数。</p>
     *
     * @param values 数组
     * @return 方差；空数组返回 0
     */
    private double varianceOf(double[] values) {
        double mean = mean(values);
        double standardDeviation = stdDev(values, mean);
        return standardDeviation * standardDeviation;
    }

    /**
     * 皮尔逊相关系数，用作结构保持度。
     *
     * <p>对亮度数组逐像素比较：越接近 1 说明明暗结构越一致，构图、五官位置偏移都会拉低该值。
     * 两个数组为空或长度不一致（理论上不会发生）时返回 0.0；任一方方差为 0（纯色图）时
     * 返回 1.0，避免把“无结构可比较”误判为结构漂移。</p>
     *
     * @param left  修图前亮度
     * @param right 修图后亮度
     * @return 相关系数，范围 -1 到 1；退化情况见上
     */
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

    /**
     * 统计肤色像素占比与平均 RGB。
     *
     * <p>全图逐像素扫描，透明像素（alpha 低于 128）不计入分母，避免 PNG 透明区域稀释占比。
     * 没有任何肤色像素或全部透明时占比与均值都返回 0，此时肤色漂移判定会被跳过。</p>
     *
     * @param image 输入图片
     * @return 肤色统计（占比 0-1，均值为 0-255 且保留 3 位小数）
     */
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

    /**
     * 把任意色彩模型转成 {@code TYPE_INT_RGB}。
     *
     * <p>已是目标类型时直接返回原对象（不复制），因此调用方不能继续修改返回的图片。
     * 其他类型（含带 alpha 的 PNG）通过一次绘制完成转换：目标画布初始为黑色，
     * 半透明与全透明像素会与黑色合成，之后的指标都基于合成结果。</p>
     *
     * @param image 输入图片
     * @return {@code TYPE_INT_RGB} 图片，可能是原对象
     */
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

    /**
     * 统一保留 3 位小数。
     *
     * <p>{@code NaN} 与无穷大（例如除零产生的值）一律归零，保证序列化到 JSON 时
     * 不会出现非数字字面量导致前端解析失败。</p>
     *
     * @param value 原始值
     * @return 四舍五入到 3 位小数；非法值返回 0
     */
    private double round(double value) {
        if (Double.isNaN(value) || Double.isInfinite(value)) {
            return 0.0d;
        }
        return Math.round(value * 1000.0d) / 1000.0d;
    }

    /**
     * 拉普拉斯响应数组的轻量包装。
     *
     * <p>只用于把响应在多个指标（锐度、噪点、纹理熵、纹理能量）之间传递，
     * 不含计算方法，避免对同一张图重复卷积。</p>
     */
    private static final class Lap {

        private final double[] response;

        /**
         * @param response 与图片等长、边界为 0 的响应数组
         */
        private Lap(double[] response) {
            this.response = response;
        }
    }

    /** 肤色统计的中间结果：占比 0-1，RGB 均值为 0-255。 */
    private static final class SkinStats {

        private double ratio;

        private double red;

        private double green;

        private double blue;
    }

    /**
     * 单图绝对指标。
     *
     * <p>由 {@link #analyze} 产出的纯数据对象，字段之间没有约束关系，直接序列化返回。
     * 量纲分三类：{@code brightness}/{@code contrast} 与肤色均值为 0-255 的像素尺度；
     * {@code sharpness}/{@code noise} 是拉普拉斯响应的方差或均方，量纲为像素差的平方；
     * {@code textureEntropy} 以 bit 为单位，{@code skinRatio} 是 0-1 的占比。</p>
     */
    public static class Metrics {

        /** 分析用图片宽度；超过 {@value #NORMALIZED_WIDTH} 的图已被等比缩小，可能不等于原图。 */
        private int width;

        /** 分析用图片高度，随宽度等比缩放。 */
        private int height;

        /** 分析用像素总数（{@code width * height}），与用户上传体积无关。 */
        private long pixelCount;

        /** 平均亮度，0-255 尺度；越大越亮。 */
        private double brightness;

        /** 亮度标准差，0-255 尺度；越大明暗反差越强。 */
        private double contrast;

        /** 锐度：拉普拉斯响应的方差；越大边缘越锐利。 */
        private double sharpness;

        /** 噪点：平坦区（局部方差最低的 10%）上的拉普拉斯响应均方值，量纲为像素差的平方。 */
        private double noise;

        /** 纹理熵，单位 bit，上限为 {@code log2(64) = 6}；过度平滑时明显下降。 */
        private double textureEntropy;

        /** 肤色像素占比 0-1；为 0 时肤色相关判定不参与结论。 */
        private double skinRatio;

        /** 肤色像素平均红色分量，0-255。 */
        private double skinRed;

        /** 肤色像素平均绿色分量，0-255。 */
        private double skinGreen;

        /** 肤色像素平均蓝色分量，0-255。 */
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
     *
     * <p>包含两张图各自的绝对指标、四个对比指标与一段可直接展示的中文结论。
     * 对比指标的量纲：{@code brightnessShift} 与 {@code skinColorShift} 为 0-255 尺度，
     * {@code structureRetention} 为相关系数（-1 到 1，实践中接近 1），
     * {@code textureRetention} 与 {@code textureEntropyRatio} 为比值（1 表示无损）。</p>
     */
    public static class Comparison {

        /** 修图前的单图指标。 */
        private Metrics baseline;

        /** 修图后的单图指标。 */
        private Metrics retouched;

        /** 两图平均亮度之差的绝对值，0-255 尺度；越大曝光越不一致。 */
        private double brightnessShift;

        /** 两图肤色平均 RGB 的欧氏距离，0-255 尺度；任一方无肤色时为 0。 */
        private double skinColorShift;

        /** 结构保持度：两图亮度的皮尔逊相关系数，越低越可能改动了五官或脸型。 */
        private double structureRetention;

        /** 纹理保留率：修图后 / 修图前的分块高频能量，低于 0.75 疑似过度磨皮。 */
        private double textureRetention;

        /** 纹理熵比值：修图后 / 修图前的拉普拉斯响应熵。 */
        private double textureEntropyRatio;

        /** 中文判定结论，由 {@link #judge} 生成，可能包含多条告警。 */
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
