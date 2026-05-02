"""
pytiled.scene
~~~~~~~~~~~~~
シーン（マップ）切り替えの管理。

SceneManager はアクティブな TiledMap を1つ持ち、
``transition_to()`` で別のマップへフェードイン/アウト切り替えを行う。

最小の使い方::

    import pygame
    import pytiled
    from pytiled.scene import SceneManager

    pygame.init()
    screen = pygame.display.set_mode((800, 600))

    mgr = SceneManager(screen_w=800, screen_h=600)
    mgr.load("maps/field.json")

    camera = mgr.make_camera()

    while running:
        dt = clock.tick(60)
        mgr.update(dt)

        camera.follow(player.px, player.py)
        mgr.draw(screen, camera)

        # ワープ判定
        dest = mgr.current.get_warp_destination(player.tx, player.ty)
        if dest:
            player.tx, player.ty = dest.spawn_tx, dest.spawn_ty
            mgr.transition_to(dest.map_path)

フェードなしで即時切り替えたい場合::

    mgr.transition_to("maps/dungeon.json", fade_ms=0)
"""

from __future__ import annotations

from typing import Callable

import pygame

from .tilemap import TiledMap
from .camera import Camera


# ─────────────────────────────────────────────────────────────────────────────
#  フェードオーバーレイ（内部ヘルパー）
# ─────────────────────────────────────────────────────────────────────────────

class _FadeOverlay:
    """黒 Surface を使ったフェードイン／アウトの管理。"""

    def __init__(self, screen_w: int, screen_h: int):
        self._surf = pygame.Surface((screen_w, screen_h))
        self._surf.fill((0, 0, 0))
        self._alpha    = 0
        self._target   = 0
        self._speed    = 0.0    # alpha/ms
        self._callback: Callable | None = None
        self._triggered = False

    def resize(self, screen_w: int, screen_h: int):
        self._surf = pygame.Surface((screen_w, screen_h))
        self._surf.fill((0, 0, 0))

    def fade_out(self, duration_ms: int, callback: Callable | None = None):
        """黒くなる方向（フェードアウト）を開始。"""
        if duration_ms <= 0:
            self._alpha = 255
            if callback:
                callback()
            return
        self._alpha     = 0
        self._target    = 255
        self._speed     = 255.0 / duration_ms
        self._callback  = callback
        self._triggered = False

    def fade_in(self, duration_ms: int):
        """透明になる方向（フェードイン）を開始。"""
        if duration_ms <= 0:
            self._alpha = 0
            return
        self._alpha     = 255
        self._target    = 0
        self._speed     = 255.0 / duration_ms
        self._callback  = None
        self._triggered = False

    def update(self, dt_ms: int):
        if self._alpha == self._target:
            return
        step = self._speed * dt_ms
        if self._target > self._alpha:
            self._alpha = min(self._alpha + step, self._target)
            # フェードアウト完了時にコールバック
            if self._alpha >= 255 and not self._triggered:
                self._triggered = True
                if self._callback:
                    self._callback()
        else:
            self._alpha = max(self._alpha - step, self._target)

    def draw(self, screen: pygame.Surface):
        a = int(self._alpha)
        if a <= 0:
            return
        self._surf.set_alpha(a)
        screen.blit(self._surf, (0, 0))

    @property
    def is_fading(self) -> bool:
        return self._alpha != self._target

    @property
    def alpha(self) -> float:
        return self._alpha


# ─────────────────────────────────────────────────────────────────────────────
#  SceneManager
# ─────────────────────────────────────────────────────────────────────────────

class SceneManager:
    """
    アクティブシーン（TiledMap）を管理し、フェードトランジションで切り替える。

    Parameters
    ----------
    screen_w, screen_h:
        画面サイズ（ピクセル）。
    fade_ms:
        デフォルトのフェードアウト＋フェードイン時間（ミリ秒）。
        0 を指定すると即時切り替え。
    collision_layer, solid_gids, skip_layers, scale:
        TiledMap へ渡す共通設定。
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        fade_ms: int = 300,
        collision_layer: str = "collision",
        solid_gids: set | None = None,
        skip_layers: set | None = None,
        scale: float = 1.0,
    ):
        self._screen_w   = screen_w
        self._screen_h   = screen_h
        self._fade_ms    = fade_ms
        self._col_layer  = collision_layer
        self._solid_gids = solid_gids
        self._skip_layers = skip_layers
        self._scale      = scale

        self._current: TiledMap | None = None
        self._overlay = _FadeOverlay(screen_w, screen_h)

        # トランジション中に次のマップパスを保持
        self._next_path: str | None = None
        # トランジション完了後コールバック（外部から登録可）
        self._on_transition: Callable[[TiledMap], None] | None = None

        self._transitioning = False

    # ── ロード ──────────────────────────────────────────────────────────────

    def load(
        self,
        json_path: str,
        collision_layer: str | None = None,
        solid_gids: set | None = None,
        skip_layers: set | None = None,
        scale: float | None = None,
    ):
        """
        マップを即時ロード・ビルドしてアクティブシーンにする。
        フェードなしで最初のマップをセットアップするときに使う。

        Parameters
        ----------
        json_path:
            Tiled JSON ファイルのパス。
        collision_layer, solid_gids, skip_layers, scale:
            省略時はコンストラクタの設定を使う。
        """
        tmap = TiledMap(
            json_path,
            collision_layer = collision_layer or self._col_layer,
            solid_gids      = solid_gids      or self._solid_gids,
            skip_layers     = skip_layers     or self._skip_layers,
            scale           = scale           if scale is not None else self._scale,
        )
        tmap.load()
        tmap.build()
        self._current = tmap

    # ── トランジション ──────────────────────────────────────────────────────

    def transition_to(
        self,
        json_path: str,
        fade_ms: int | None = None,
        on_transition: Callable[["TiledMap"], None] | None = None,
    ):
        """
        フェードトランジションで新しいマップへ切り替える。

        フロー:
            1. フェードアウト開始
            2. フェードアウト完了 → 新マップをロード・ビルド
            3. フェードイン開始
            4. フェードイン完了 → 通常状態

        Parameters
        ----------
        json_path:
            切り替え先マップの Tiled JSON パス。
        fade_ms:
            フェード時間（ミリ秒）。None でデフォルト値を使用。
        on_transition:
            新マップがロードされた直後に呼ばれるコールバック。
            プレイヤー初期位置のセットなどに使う。
            引数として新しい TiledMap が渡される。

            例::

                def on_warp(new_map):
                    player.tx = spawn_tx
                    player.ty = spawn_ty

                mgr.transition_to("dungeon.json", on_transition=on_warp)
        """
        if self._transitioning:
            return  # 多重トランジション防止

        duration = fade_ms if fade_ms is not None else self._fade_ms
        self._next_path       = json_path
        self._on_transition   = on_transition
        self._transitioning   = True

        def _do_swap():
            # フェードアウト完了 → マップ交換
            tmap = TiledMap(
                self._next_path,
                collision_layer = self._col_layer,
                solid_gids      = self._solid_gids,
                skip_layers     = self._skip_layers,
                scale           = self._scale,
            )
            tmap.load()
            tmap.build()
            self._current = tmap

            if self._on_transition:
                self._on_transition(tmap)

            # フェードイン開始
            self._overlay.fade_in(duration)

        self._overlay.fade_out(duration, callback=_do_swap)

    # ── 更新 ────────────────────────────────────────────────────────────────

    def update(self, dt_ms: int):
        """
        毎フレーム呼ぶ。フェードの進行を更新する。

        Parameters
        ----------
        dt_ms:
            前フレームからの経過時間（ミリ秒）。
        """
        self._overlay.update(dt_ms)

        # フェードイン完了でトランジション終了
        if self._transitioning and not self._overlay.is_fading:
            if self._overlay.alpha <= 0:
                self._transitioning = False

    # ── 描画 ────────────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface, camera: Camera):
        """
        現在のマップを描画し、フェードオーバーレイを重ねる。

        Parameters
        ----------
        screen:
            描画先 pygame.Surface。
        camera:
            スクロールカメラ。
        """
        if self._current:
            self._current.draw(screen, camera)
        self._overlay.draw(screen)

    # ── カメラ生成 ──────────────────────────────────────────────────────────

    def make_camera(self) -> Camera:
        """
        現在のマップに合わせたカメラを生成して返す。
        ``load()`` 後に呼ぶこと。
        """
        if self._current is None:
            raise RuntimeError("load() を先に呼んでください")
        return self._current.make_camera(self._screen_w, self._screen_h)

    def resize(self, screen_w: int, screen_h: int):
        """ウィンドウリサイズ時に呼ぶ。"""
        self._screen_w = screen_w
        self._screen_h = screen_h
        self._overlay.resize(screen_w, screen_h)

    # ── プロパティ ───────────────────────────────────────────────────────────

    @property
    def current(self) -> TiledMap:
        """現在アクティブな TiledMap。load() 前にアクセスすると例外。"""
        if self._current is None:
            raise RuntimeError("load() を先に呼んでください")
        return self._current

    @property
    def is_transitioning(self) -> bool:
        """トランジション中かどうか。"""
        return self._transitioning
