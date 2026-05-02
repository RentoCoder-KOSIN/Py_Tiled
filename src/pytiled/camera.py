"""
pytiled.camera
~~~~~~~~~~~~~~
スクロールカメラ。pygame に依存しない座標計算層。
"""

from __future__ import annotations


class Camera:
    """
    ワールド座標 → スクリーン座標 の変換を管理する。

    Parameters
    ----------
    screen_w, screen_h:
        画面サイズ（ピクセル）。
    world_w, world_h:
        ワールド（マップ全体）のピクセルサイズ。
        0 以下にするとクランプを無効化。
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        world_w: int = 0,
        world_h: int = 0,
    ):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.world_w  = world_w
        self.world_h  = world_h
        self.ox: int  = 0   # ワールド上のカメラ左上 X
        self.oy: int  = 0   # ワールド上のカメラ左上 Y

    # ── 追従 ────────────────────────────────────────────────────────────────

    def follow(self, px: int, py: int):
        """
        ターゲット（ピクセル座標）をカメラ中央に追従させる。
        world_w / world_h が正の値ならマップ端でクランプ。
        """
        self.ox = px - self.screen_w // 2
        self.oy = py - self.screen_h // 2
        self._clamp()

    def set_position(self, ox: int, oy: int):
        """カメラ位置を直接セット（スクロール演出など）。"""
        self.ox = ox
        self.oy = oy
        self._clamp()

    def resize(self, screen_w: int, screen_h: int):
        """ウィンドウリサイズ時に呼ぶ。"""
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._clamp()

    def _clamp(self):
        if self.world_w > 0:
            self.ox = max(0, min(self.ox, self.world_w  - self.screen_w))
        if self.world_h > 0:
            self.oy = max(0, min(self.oy, self.world_h - self.screen_h))

    # ── 座標変換 ─────────────────────────────────────────────────────────────

    def apply(self, wx: int, wy: int) -> tuple[int, int]:
        """ワールド座標 → スクリーン座標"""
        return wx - self.ox, wy - self.oy

    def unapply(self, sx: int, sy: int) -> tuple[int, int]:
        """スクリーン座標 → ワールド座標"""
        return sx + self.ox, sy + self.oy

    def is_visible(self, wx: int, wy: int, w: int = 0, h: int = 0) -> bool:
        """
        ワールド座標の矩形がカメラ内に入っているか判定。
        カリング用途など。
        """
        return (
            wx + w > self.ox and wx < self.ox + self.screen_w and
            wy + h > self.oy and wy < self.oy + self.screen_h
        )

    # ── プロパティ ───────────────────────────────────────────────────────────

    @property
    def rect(self) -> tuple[int, int, int, int]:
        """カメラが映しているワールド上の矩形 (x, y, w, h)"""
        return self.ox, self.oy, self.screen_w, self.screen_h
