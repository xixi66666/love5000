import math
import wave
from array import array
from pathlib import Path


def main():
    output = Path("assets/default_bgm.mp3")
    output.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    duration = 20
    samples = array("h")
    for index in range(sample_rate * duration):
        t = index / sample_rate
        envelope = min(t / 2, 1.0, max((duration - t) / 3, 0.0))
        low = math.sin(2 * math.pi * 110 * t) * 0.24
        mid = math.sin(2 * math.pi * 220 * t) * 0.12
        pulse = math.sin(2 * math.pi * 55 * t) * 0.18
        value = int((low + mid + pulse) * envelope * 32767)
        samples.append(value)

    # 文件扩展名沿用 mp3，FFmpeg 会根据 WAV 头正确识别输入。
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())
    print(output)


if __name__ == "__main__":
    main()
