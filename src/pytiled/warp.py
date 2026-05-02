"""
pytiled.warp
~~~~~~~~~~~~
ワープ（マップ内の扉・出口・移動ポイント）の定義と判定。

Tiled 上での設定方法
--------------------
1. マップに **objectlayer** を追加し、名前を ``"warps"``（デフォルト）にする。
2. レイヤー上に **矩形オブジェクト** を置き、以下の Custom Properties を設定する：

   ==================  ===========  ==========================================
   プロパティ名         型           意味
   ==================  ===========  ==========================================
   ``map``             string       遷移先マップの JSON パス（必須）
   ``spawn_tx``        int          遷移先スポーン位置 タイル X（デフォルト 0）
   ``spawn_ty``        int          遷移先スポーン位置 タイル Y（デフォルト 0）
   ``id``              string       このワープの識別名（省略可）
   ==================  ===========  ==========================================

3. 矩形はタイル単位の整数に揃える必要はないが、``WarpLayer.check()`` は
   タイル座標で判定するため、タイルグリッドに合わせておくのが無難。

コード例::

    # ロード済み TiledMap から WarpLayer を作る
    from pytiled.warp import WarpLayer

    warp_layer = WarpLayer.from_map(tmap, tile_w=32, tile_h=32)

    # ゲームループ内
    dest = warp_layer.check(player.tx, player.ty)
    if dest:
        mgr.transition_to(
            dest.map_path,
            on_transition=lambda _: player.set_tile_pos(dest.spawn_tx, dest.spawn_ty),
        )

TiledMap に統合した使い方 (``tilemap.py`` の ``get_warps()``)::

    dest = tmap.get_warps(tile_w=32, tile_h=32).check(player.tx, player.ty)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tilemap import TiledMap


# ─────────────────────────────────────────────────────────────────────────────
#  データクラス
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WarpDest:
    """
    ワープの遷移先情報。

    Attributes
    ----------
    map_path:
        遷移先マップの Tiled JSON パス。
    spawn_tx, spawn_ty:
        遷移先でプレイヤーを置くタイル座標。
    warp_id:
        このワープの識別名（Tiled オブジェクトの ``id`` プロパティ or ``name``）。
    """
    map_path:  str
    spawn_tx:  int = 0
    spawn_ty:  int = 0
    warp_id:   str = ""
    label:     str = ""


# ─────────────────────────────────────────────────────────────────────────────
#  WarpLayer
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _WarpRect:
    """内部用：ワープ領域（ピクセル矩形）と遷移先"""
    px: int
    py: int
    pw: int
    ph: int
    dest: WarpDest


class WarpLayer:
    """
    Tiled objectlayer から読み込んだワープ定義のコレクション。

    ``check(tx, ty)`` でタイル座標がワープ領域内かを判定し、
    該当すれば ``WarpDest`` を返す。

    直接インスタンス化より ``WarpLayer.from_map()`` を使う方が簡単。
    """

    def __init__(self, tile_w: int, tile_h: int):
        self._tile_w = tile_w
        self._tile_h = tile_h
        self._warps: list[_WarpRect] = []

    # ── ファクトリ ───────────────────────────────────────────────────────────

    @classmethod
    def from_map(
        cls,
        tmap: "TiledMap",
        layer_name: str = "warps",
        tile_w: int | None = None,
        tile_h: int | None = None,
    ) -> "WarpLayer":
        """
        TiledMap のオブジェクトレイヤーから WarpLayer を生成する。

        Parameters
        ----------
        tmap:
            ロード済みの TiledMap。
        layer_name:
            Tiled 上のオブジェクトレイヤー名（デフォルト ``"warps"``）。
        tile_w, tile_h:
            タイルサイズ（ピクセル）。省略時は tmap から取得。
        """
        tw = tile_w if tile_w is not None else tmap.tile_w
        th = tile_h if tile_h is not None else tmap.tile_h

        instance = cls(tw, th)

        # loader の MapData から objectlayer を取得
        for raw_layer in tmap.map_data.object_layers:
            if raw_layer.name.lower() != layer_name.lower():
                continue
            for obj in raw_layer.objects:
                props = obj.properties
                map_path = props.get("map", "")
                if not map_path:
                    # "map" プロパティがなければスキップ
                    continue
                dest = WarpDest(
                    map_path = map_path,
                    spawn_tx = int(props.get("spawn_tx", 0)),
                    spawn_ty = int(props.get("spawn_ty", 0)),
                    warp_id  = props.get("id", obj.name),
                    label    = props.get("label", obj.name),
                )
                instance._warps.append(_WarpRect(
                    px   = int(obj.x),
                    py   = int(obj.y),
                    pw   = max(int(obj.width),  tw),
                    ph   = max(int(obj.height), th),
                    dest = dest,
                ))
        return instance

    # ── 手動追加 ────────────────────────────────────────────────────────────

    def add(
        self,
        tx: int,
        ty: int,
        map_path: str,
        spawn_tx: int = 0,
        spawn_ty: int = 0,
        warp_id: str = "",
        width_tiles: int = 1,
        height_tiles: int = 1,
    ):
        """
        コードからワープ領域を追加する（Tiled を使わない場合）。

        Parameters
        ----------
        tx, ty:
            ワープ領域の左上タイル座標。
        map_path:
            遷移先マップの JSON パス。
        spawn_tx, spawn_ty:
            遷移先スポーン位置。
        warp_id:
            識別名（省略可）。
        width_tiles, height_tiles:
            ワープ領域のタイル数（デフォルト 1×1）。
        """
        self._warps.append(_WarpRect(
            px   = tx * self._tile_w,
            py   = ty * self._tile_h,
            pw   = width_tiles  * self._tile_w,
            ph   = height_tiles * self._tile_h,
            dest = WarpDest(
                map_path = map_path,
                spawn_tx = spawn_tx,
                spawn_ty = spawn_ty,
                warp_id  = warp_id,
            ),
        ))

    # ── 判定 API ─────────────────────────────────────────────────────────────

    def check(self, tx: int, ty: int) -> WarpDest | None:
        """
        タイル座標 (tx, ty) がワープ領域内かを判定する。

        Parameters
        ----------
        tx, ty:
            判定するタイル座標（プレイヤーのタイル位置など）。

        Returns
        -------
        WarpDest | None
            ワープ領域内なら遷移先情報、なければ None。
        """
        px = tx * self._tile_w + self._tile_w // 2
        py = ty * self._tile_h + self._tile_h // 2
        for w in self._warps:
            if w.px <= px < w.px + w.pw and w.py <= py < w.py + w.ph:
                return w.dest
        return None

    def check_pixel(self, px: int, py: int) -> WarpDest | None:
        """
        ピクセル座標で判定する版。

        Parameters
        ----------
        px, py:
            判定するワールドピクセル座標。
        """
        for w in self._warps:
            if w.px <= px < w.px + w.pw and w.py <= py < w.py + w.ph:
                return w.dest
        return None

    def all_dests(self) -> list[WarpDest]:
        """登録されている全ワープ先を返す。"""
        return [w.dest for w in self._warps]

    def __len__(self) -> int:
        return len(self._warps)
