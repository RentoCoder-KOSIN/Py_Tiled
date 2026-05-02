"""
pytiled.renderer
~~~~~~~~~~~~~~~~
Tiled マップの pygame 描画層。

MapData を受け取り、全レイヤーを1枚の pygame.Surface に焼き込む。
ゲームループでは Camera を使って差分領域だけ blit する。
"""

from __future__ import annotations

import pygame

from .loader import MapData, TilesetData, find_tileset, strip_flags, get_flip_flags
from .camera import Camera


# ─────────────────────────────────────────────────────────────────────────────
#  タイルセット画像キャッシュ
# ─────────────────────────────────────────────────────────────────────────────

_image_cache: dict[str, pygame.Surface] = {}


def _load_image(path: str) -> pygame.Surface | None:
    if not path:
        return None
    if path in _image_cache:
        return _image_cache[path]
    try:
        surf = pygame.image.load(path).convert_alpha()
        _image_cache[path] = surf
        return surf
    except (pygame.error, FileNotFoundError):
        return None


def clear_image_cache():
    """キャッシュをクリアする。テストや動的リロード用。"""
    _image_cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
#  フォールバックカラー
# ─────────────────────────────────────────────────────────────────────────────

def _gid_color(gid: int) -> tuple[int, int, int]:
    r = (gid * 97  + 50) % 180 + 40
    g = (gid * 53  + 80) % 180 + 40
    b = (gid * 131 + 30) % 180 + 40
    return (r, g, b)


# ─────────────────────────────────────────────────────────────────────────────
#  1 タイル描画
# ─────────────────────────────────────────────────────────────────────────────

def _blit_tile(
    surface: pygame.Surface,
    raw_gid: int,
    ts: TilesetData,
    ts_image: pygame.Surface,
    dest_x: int,
    dest_y: int,
    dest_tile_w: int,
    dest_tile_h: int,
):
    gid      = strip_flags(raw_gid)
    local_id = gid - ts.firstgid
    src_col  = local_id % ts.columns
    src_row  = local_id // max(ts.columns, 1)
    src_x    = ts.margin + src_col * (ts.tile_w + ts.spacing)
    src_y    = ts.margin + src_row * (ts.tile_h + ts.spacing)

    # 安全チェック
    if (src_x + ts.tile_w > ts_image.get_width() or
            src_y + ts.tile_h > ts_image.get_height()):
        return

    tile = ts_image.subsurface((src_x, src_y, ts.tile_w, ts.tile_h))

    flip_h, flip_v, flip_d = get_flip_flags(raw_gid)
    if flip_h or flip_v or flip_d:
        tile = tile.copy()
        if flip_d:
            tile   = pygame.transform.rotate(tile, -90)
            flip_h = not flip_h
        tile = pygame.transform.flip(tile, flip_h, flip_v)

    if ts.tile_w != dest_tile_w or ts.tile_h != dest_tile_h:
        tile = pygame.transform.scale(tile, (dest_tile_w, dest_tile_h))

    surface.blit(tile, (dest_x, dest_y))


# ─────────────────────────────────────────────────────────────────────────────
#  MapRenderer
# ─────────────────────────────────────────────────────────────────────────────

class MapRenderer:
    """
    MapData を pygame.Surface に焼き込み、カメラを使って描画する。

    Parameters
    ----------
    map_data:
        ``loader.load_map()`` が返す MapData。
    skip_layers:
        描画しないレイヤー名のセット（デフォルトで ``{"collision"}``）。
    scale:
        タイルの描画スケール倍率（デフォルト 1.0）。
        2.0 にするとタイルを2倍サイズで焼き込む。

    使い方::

        renderer = MapRenderer(map_data)
        renderer.build()                  # 初期化時に1回
        renderer.draw(screen, camera)     # ゲームループ内
    """

    def __init__(
        self,
        map_data: MapData,
        skip_layers: set[str] | None = None,
        scale: float = 1.0,
    ):
        self._md          = map_data
        self._skip_layers = {s.lower() for s in (skip_layers or {"collision"})}
        self._scale       = scale
        self._tile_w      = int(map_data.tile_w * scale)
        self._tile_h      = int(map_data.tile_h * scale)
        self._surface: pygame.Surface | None = None
        self._built = False

        # タイルセットごとに画像を事前ロード
        self._ts_images: dict[int, pygame.Surface | None] = {}

    # ── 焼き込み ────────────────────────────────────────────────────────────

    def build(self):
        """全レイヤーを順番に Surface に焼き込む。pygame.init() 後に呼ぶこと。"""
        md = self._md
        tw = self._tile_w
        th = self._tile_h

        total_w = md.map_w * tw
        total_h = md.map_h * th
        # SRCALPHA で透明背景として初期化
        self._surface = pygame.Surface((total_w, total_h), pygame.SRCALPHA)

        # 画像を一括ロード
        for ts in md.tilesets:
            self._ts_images[ts.firstgid] = _load_image(ts.image)

        for layer in md.layers:
            if not layer.visible:
                continue
            if layer.name.lower() in self._skip_layers:
                continue

            ox = int(layer.offsetx * self._scale)
            oy = int(layer.offsety * self._scale)

            # opacity が 1.0 未満のときだけ中間 Surface を使う
            # （set_alpha は Surface 全体にかかるため blit 前に適用する）
            if layer.opacity < 1.0:
                tmp = pygame.Surface((total_w, total_h), pygame.SRCALPHA)
                self._draw_layer_to(tmp, layer, tw, th, ox, oy)
                # BLEND_RGBA_MULT で opacity を乗算してから合成
                tmp.set_alpha(int(layer.opacity * 255))
                self._surface.blit(tmp, (0, 0))
            else:
                # 不透明レイヤーは直接 _surface に描く（高速・メモリ節約）
                self._draw_layer_to(self._surface, layer, tw, th, ox, oy)

        self._built = True

    def _draw_layer_to(
        self,
        target: pygame.Surface,
        layer,
        tw: int,
        th: int,
        ox: int,
        oy: int,
    ):
        """レイヤーのタイルを target Surface に描く内部メソッド"""
        md = self._md
        for ty in range(layer.height):
            for tx in range(layer.width):
                raw_gid = layer.data[ty * layer.width + tx]
                gid     = strip_flags(raw_gid)
                if gid == 0:
                    continue

                dest_x = tx * tw + ox
                dest_y = ty * th + oy

                ts  = find_tileset(md.tilesets, gid)
                img = self._ts_images.get(ts.firstgid) if ts else None

                if ts and img:
                    _blit_tile(target, raw_gid, ts, img, dest_x, dest_y, tw, th)
                else:
                    pygame.draw.rect(target, _gid_color(gid),
                                     (dest_x, dest_y, tw, th))

    def rebuild(self):
        """マップデータ変更後に再焼き込みする。"""
        clear_image_cache()
        self._ts_images.clear()
        self._built = False
        self.build()

    # ── 描画 ────────────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface, camera: Camera):
        """Camera を使ってスクリーンに描画する。"""
        if not self._built or self._surface is None:
            return

        ox, oy, sw, sh = camera.rect
        src_rect = pygame.Rect(ox, oy, sw, sh).clip(self._surface.get_rect())
        if src_rect.width == 0 or src_rect.height == 0:
            return

        dst_x = src_rect.x - ox
        dst_y = src_rect.y - oy
        screen.blit(self._surface.subsurface(src_rect), (dst_x, dst_y))

    def draw_raw(self, screen: pygame.Surface, camera_ox: int, camera_oy: int):
        """Camera オブジェクトなしで直接 ox/oy を渡す版。後方互換用。"""
        if not self._built or self._surface is None:
            return
        sw = screen.get_width()
        sh = screen.get_height()
        src_rect = pygame.Rect(camera_ox, camera_oy, sw, sh).clip(
            self._surface.get_rect()
        )
        if src_rect.width == 0 or src_rect.height == 0:
            return
        screen.blit(self._surface.subsurface(src_rect),
                    (src_rect.x - camera_ox, src_rect.y - camera_oy))

    # ── プロパティ ───────────────────────────────────────────────────────────

    @property
    def pixel_width(self) -> int:
        return self._md.map_w * self._tile_w

    @property
    def pixel_height(self) -> int:
        return self._md.map_h * self._tile_h

    @property
    def tile_w(self) -> int:
        return self._tile_w

    @property
    def tile_h(self) -> int:
        return self._tile_h

    @property
    def is_built(self) -> bool:
        return self._built
