"""
pytiled.collision
~~~~~~~~~~~~~~~~~
壁判定マップの構築と参照。pygame に依存しない。

判定の優先順位:
  1. ``collision_layer`` 引数で指定した名前のレイヤー（タイルあり → 壁）
  2. ``solid_gids`` 引数で指定した GID セット（全レイヤーを走査）
  3. 両方なし → 全マス通行可能（マップ外のみ壁）
"""

from __future__ import annotations

from .loader import MapData, LayerData, strip_flags


class CollisionMap:
    """
    壁判定の二次元マップ。

    Parameters
    ----------
    map_data:
        ``loader.load_map()`` が返す MapData。
    collision_layer:
        壁判定に使うレイヤー名（大文字小文字不問）。
        デフォルトは ``"collision"``。
    solid_gids:
        このレイヤー名のレイヤーが存在しない場合に、
        「このGIDは壁」と見なす GID の集合。
        空の場合は全マス通行可能。
    """

    def __init__(
        self,
        map_data: MapData,
        collision_layer: str = "collision",
        solid_gids: set | None = None,
    ):
        self._w = map_data.map_w
        self._h = map_data.map_h
        self._grid = [
            [False] * self._w for _ in range(self._h)
        ]
        self._build(map_data, collision_layer, solid_gids or set())

    # ── 構築 ─────────────────────────────────────────────────────────────────

    def _build(self, md, col_name, solid_gids):
        col_layer = next(
            (l for l in md.layers if l.name.lower() == col_name.lower()),
            None,
        )
        if col_layer:
            self._fill_from_layer(col_layer)
            return

        if solid_gids:
            for layer in md.layers:
                self._fill_from_gids(layer, solid_gids)

    def _fill_from_layer(self, layer):
        for ty in range(layer.height):
            for tx in range(layer.width):
                raw = layer.data[ty * layer.width + tx]
                if strip_flags(raw) != 0:
                    self._grid[ty][tx] = True

    def _fill_from_gids(self, layer, solid_gids):
        for ty in range(layer.height):
            for tx in range(layer.width):
                raw = layer.data[ty * layer.width + tx]
                if strip_flags(raw) in solid_gids:
                    self._grid[ty][tx] = True

    # ── 判定 API ─────────────────────────────────────────────────────────────

    def is_wall(self, tx: int, ty: int) -> bool:
        """タイル座標 (tx, ty) が壁かどうかを返す。範囲外は壁扱い。"""
        if 0 <= ty < self._h and 0 <= tx < self._w:
            return self._grid[ty][tx]
        return True

    def set_wall(self, tx: int, ty: int, value: bool = True):
        """ランタイムで壁を追加・削除する（扉の開閉など）。"""
        if 0 <= ty < self._h and 0 <= tx < self._w:
            self._grid[ty][tx] = value

    def get_walls(self):
        """壁タイルの座標リストを返す。デバッグ用途など。"""
        return [
            (tx, ty)
            for ty in range(self._h)
            for tx in range(self._w)
            if self._grid[ty][tx]
        ]

    @property
    def width(self):
        return self._w

    @property
    def height(self):
        return self._h
