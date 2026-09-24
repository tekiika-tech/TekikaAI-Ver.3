"""
backend/tools/image_gen_tool.py

完全ローカルの画像生成ツール。
- 一次経路: ローカルで起動しているStable Diffusion WebUI (AUTOMATIC1111) の
  REST API (既定: http://localhost:7860) を使用。
- フォールバック: WebUIが未起動、またはリクエストに失敗した場合は、
  Pillowでプレースホルダー画像をローカル生成する（外部通信なし）。
"""

from __future__ import annotations

import base64
import io
import logging
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("tekika_ai.image_gen_tool")


class ImageGenerationError(Exception):
    """画像生成処理全般のエラー。"""


class LocalImageGenerator:
    """
    ローカル画像生成を担当するクラス。

    Attributes:
        webui_base_url: Stable Diffusion WebUI APIのベースURL。
        output_dir: 生成画像の保存先ディレクトリ。
        default_width: デフォルト画像幅。
        default_height: デフォルト画像高さ。
        default_steps: デフォルトのdiffusionステップ数。
        timeout: WebUIへのリクエストタイムアウト秒数。
    """

    def __init__(
        self,
        webui_base_url: str = "http://localhost:7860",
        output_dir: Optional[Path] = None,
        default_width: int = 512,
        default_height: int = 512,
        default_steps: int = 20,
        timeout: float = 120.0,
    ) -> None:
        self.webui_base_url = webui_base_url.rstrip("/")
        self.output_dir = Path(output_dir) if output_dir else Path("data/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_width = default_width
        self.default_height = default_height
        self.default_steps = default_steps
        self.timeout = timeout

    # ------------------------------------------------------------------
    # WebUI 起動確認
    # ------------------------------------------------------------------
    async def is_webui_available(self) -> bool:
        """ローカルのStable Diffusion WebUI APIが応答するかを確認する。"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.webui_base_url}/sdapi/v1/sd-models")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    # ------------------------------------------------------------------
    # メイン生成エントリポイント
    # ------------------------------------------------------------------
    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: Optional[int] = None,
        height: Optional[int] = None,
        steps: Optional[int] = None,
        seed: int = -1,
    ) -> Dict[str, Any]:
        """
        プロンプトから画像を生成する。ローカルWebUIが利用可能であればそちらを使用し、
        利用できない場合はPillowによるダミープレースホルダー画像を生成する。

        Args:
            prompt: 画像生成プロンプト。
            negative_prompt: ネガティブプロンプト。
            width: 出力画像の幅。
            height: 出力画像の高さ。
            steps: サンプリングステップ数。
            seed: 生成シード値（-1でランダム）。

        Returns:
            Dict[str, Any]: {"file_path", "source", "width", "height", "prompt"}
        """
        width = width or self.default_width
        height = height or self.default_height
        steps = steps or self.default_steps

        if await self.is_webui_available():
            try:
                return await self._generate_via_webui(
                    prompt, negative_prompt, width, height, steps, seed
                )
            except ImageGenerationError:
                logger.exception("WebUI経由の画像生成に失敗しました。フォールバックへ切り替えます。")

        return self._generate_placeholder(prompt, width, height)

    # ------------------------------------------------------------------
    # Stable Diffusion WebUI 経由の生成
    # ------------------------------------------------------------------
    async def _generate_via_webui(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        seed: int,
    ) -> Dict[str, Any]:
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "seed": seed,
            "sampler_name": "Euler a",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.webui_base_url}/sdapi/v1/txt2img", json=payload
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ImageGenerationError(f"WebUI APIリクエストに失敗しました: {exc}") from exc

        data = resp.json()
        images = data.get("images", [])
        if not images:
            raise ImageGenerationError("WebUIから画像データが返却されませんでした。")

        image_bytes = base64.b64decode(images[0])
        file_path = self._build_output_path()
        file_path.write_bytes(image_bytes)

        return {
            "file_path": str(file_path),
            "source": "stable_diffusion_webui",
            "width": width,
            "height": height,
            "prompt": prompt,
        }

    # ------------------------------------------------------------------
    # フォールバック: Pillowによるダミー画像生成
    # ------------------------------------------------------------------
    def _generate_placeholder(self, prompt: str, width: int, height: int) -> Dict[str, Any]:
        """
        ローカルの画像生成バックエンドが利用できない場合に、
        Pillowでプロンプトテキストを描画したプレースホルダー画像を生成する。
        """
        image = Image.new("RGB", (width, height), color=(30, 30, 46))
        draw = ImageDraw.Draw(image)

        try:
            font = ImageFont.load_default()
        except Exception:  # pragma: no cover - フォント読み込み失敗時の保険
            font = None

        margin = 20
        wrapped_lines = textwrap.wrap(prompt, width=max(10, (width - margin * 2) // 7))
        header = "[ローカル画像生成 未起動 - プレースホルダー]"
        lines = [header, ""] + wrapped_lines

        y = margin
        for line in lines:
            draw.text((margin, y), line, fill=(220, 220, 235), font=font)
            y += 16

        file_path = self._build_output_path()
        image.save(file_path, format="PNG")

        return {
            "file_path": str(file_path),
            "source": "pillow_placeholder",
            "width": width,
            "height": height,
            "prompt": prompt,
        }

    def _build_output_path(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique = uuid.uuid4().hex[:8]
        return self.output_dir / f"tekika_image_{timestamp}_{unique}.png"

    # ------------------------------------------------------------------
    # ユーティリティ
    # ------------------------------------------------------------------
    def image_to_base64(self, file_path: str) -> str:
        """生成済み画像ファイルをBase64文字列に変換する（API応答用）。"""
        path = Path(file_path)
        if not path.exists():
            raise ImageGenerationError(f"画像ファイルが見つかりません: {path}")
        with io.BytesIO(path.read_bytes()) as buffer:
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
