from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from anime_tools.config import AppSettings
from anime_tools.local_wan_video import LocalWanImageToVideoProvider
from anime_tools.modelscope_video import DashScopeImageToVideoClient, image_file_to_data_url


@dataclass(frozen=True)
class ImageToVideoRequest:
    project_dir: Path
    shot_id: str
    image_path: Path
    prompt: str
    duration: float
    resolution: str = "720P"


class ImageToVideoProvider:
    def generate(self, request: ImageToVideoRequest) -> bytes:
        """根据关键帧和镜头提示词生成单个镜头视频。"""
        raise NotImplementedError


class DashScopeImageToVideoProvider:
    def __init__(self, client: DashScopeImageToVideoClient):
        self.client = client

    def generate(self, request: ImageToVideoRequest) -> bytes:
        # DashScope 远端接口要求公网可访问图片；data URL 主要用于保留统一接口形状。
        image_url = image_file_to_data_url(request.image_path)
        return self.client.generate_video(image_url, request.prompt)


def create_image_to_video_provider(settings: AppSettings) -> ImageToVideoProvider | None:
    if not settings.image_to_video.enabled:
        return None

    provider = settings.image_to_video.provider
    if provider == "none":
        return None
    if provider == "local_wan":
        return LocalWanImageToVideoProvider(
            base_url=settings.local_wan_video.base_url,
            endpoint=settings.local_wan_video.endpoint,
            timeout_seconds=settings.local_wan_video.timeout_seconds,
        )
    if provider == "dashscope":
        return DashScopeImageToVideoProvider(DashScopeImageToVideoClient(settings.modelscope_video))

    raise ValueError(f"不支持的图生视频 Provider: {provider}")
