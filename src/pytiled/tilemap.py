"""
pytiled.tilemap
~~~~~~~~~~~~~~~
TiledMap: loader / renderer / collision / camera をまとめた
ワンストップ・ファサードクラス。

最小の使い方::

    import pygame
    import pytiled

    pygame.init()
    screen = pygame.display.set_mode((800, 600))

    tmap = pytiled.TiledMap("maps/dungeon.json")
    tmap.load()
    tmap.build()   # pygame.init() 後に呼ぶ

    camera = tmap.make_camera(800, 600)

    # ゲームループ
    while True:
        camera.follow(player.px, player.py)
        tmap.draw(screen, camera)
        if tmap.is_wall(tx, ty):
            ...
"""

from __future__ import annotations

from .loader    import load_map, MapData, get_tile_properties
from .collision import CollisionMap
from .renderer  import MapRenderer
from .camera    import Camera


class TiledMap:
    """
    Tiled JSON マップのオールインワン管理クラス。

    Parameters
    ----------
    json_path:
        Tiled が書き出した .json ファイルへのパス。
    collision_layer:
        壁判定に使うレイヤー名（デフォルト ``"collision"``）。
    solid_gids:
        collision レイヤーがない場合に壁とみなす GID の集合。
    skip_layers:
        描画をスキップするレイヤー名のセット
        （デフォルトで ``{"collision"}`` を除外）。
    scale:
        描画スケール倍率（デフォルト 1.0）。
    """

    def __init__(
        self,
        json_path: str,
        collision_layer: str = "collision",
        solid_gids: set | None = None,
        skip_layers: set | None = None,
        scale: float = 1.0,
    ):
        self._json_path       = json_path
        self._collision_layer = collision_layer
        self._solid_gids      = solid_gids
        self._skip_layers     = skip_layers
        self._scale           = scale

        self._map_data:  MapData | None      = None
        self._collision: CollisionMap | None = None
        self._renderer:  MapRenderer | None  = None

    # ── ロード・ビルド ───────────────────────────────────────────────────────

    def load(self):
        """JSON を読み込む。pygame.init() より前でも呼べる。"""
        self._map_data  = load_map(self._json_path)
        self._collision = CollisionMap(
            self._map_data,
            collision_layer = self._collision_layer,
            solid_gids      = self._solid_gids,
        )
        self._renderer = MapRenderer(
            self._map_data,
            skip_layers = self._skip_layers,
            scale       = self._scale,
        )

    def build(self):
        """
        タイルセット画像をロードして Surface を焼き込む。
        ``pygame.init()`` と ``pygame.display.set_mode()`` の後に呼ぶこと。
        """
        if self._renderer is None:
            raise RuntimeError("load() を先に呼んでください")
        self._renderer.build()

    def reload(self, json_path: str | None = None):
        """
        マップファイルを再ロードする（ホットリロード・マップ切り替え用）。

        Parameters
        ----------
        json_path:
            新しいマップファイルのパス。省略すると同じファイルを再ロード。
        """
        if json_path:
            self._json_path = json_path
        self.load()
        if self._renderer and self._renderer.is_built:
            self._renderer.build()

    # ── 描画 ────────────────────────────────────────────────────────────────

    def draw(self, screen, camera: Camera):
        """Camera を使ってスクリーンに描画する。"""
        if self._renderer:
            self._renderer.draw(screen, camera)

    def draw_raw(self, screen, camera_ox: int, camera_oy: int):
        """Camera オブジェクトなしで直接 ox/oy を渡す版。"""
        if self._renderer:
            self._renderer.draw_raw(screen, camera_ox, camera_oy)

    # ── 壁判定 ──────────────────────────────────────────────────────────────

    def is_wall(self, tx: int, ty: int) -> bool:
        """タイル座標 (tx, ty) が壁かどうかを返す。"""
        if self._collision is None:
            return False
        return self._collision.is_wall(tx, ty)

    def set_wall(self, tx: int, ty: int, value: bool = True):
        """ランタイムで壁を書き換える（扉の開閉など）。"""
        if self._collision:
            self._collision.set_wall(tx, ty, value)

    # ── ワープ ──────────────────────────────────────────────────────────────

    def get_warps(
        self,
        layer_name: str = "warps",
        tile_w: int | None = None,
        tile_h: int | None = None,
    ):
        """
        オブジェクトレイヤーからワープ定義を読み込んで WarpLayer を返す。

        Tiled の objectlayer に矩形を置き、Custom Properties として
        ``map``（遷移先 JSON パス）・``spawn_tx``・``spawn_ty`` を設定すること。

        Parameters
        ----------
        layer_name:
            ワープオブジェクトを置いた objectlayer の名前（デフォルト ``"warps"``）。
        tile_w, tile_h:
            タイルサイズ（ピクセル）。省略時はマップの値を使う。

        Returns
        -------
        WarpLayer
            ワープ判定オブジェクト。

        Example
        -------
        ::

            warps = tmap.get_warps()
            dest  = warps.check(player.tx, player.ty)
            if dest:
                mgr.transition_to(dest.map_path)
        """
        from .warp import WarpLayer
        return WarpLayer.from_map(self, layer_name=layer_name,
                                  tile_w=tile_w, tile_h=tile_h)

    # ── レイヤー参照 ────────────────────────────────────────────────────────

    def get_layer(self, name: str):
        """
        名前でレイヤーを取得する（大文字小文字不問）。

        Returns
        -------
        LayerData | None
        """
        return self.map_data.get_layer(name)

    def get_layers_by_property(self, key: str, value=None):
        """
        指定プロパティを持つレイヤー一覧を返す。

        Parameters
        ----------
        key:
            プロパティ名。
        value:
            指定するとその値と一致するものだけを返す。
        """
        return self.map_data.get_layers_by_property(key, value)

    # ── properties アクセサ ──────────────────────────────────────────────────

    @property
    def properties(self):
        """マップ自体の properties 辞書"""
        return self.map_data.properties

    def layer_properties(self, name: str) -> dict:
        """
        指定レイヤーの properties 辞書を返す。
        レイヤーが存在しない場合は空辞書。
        """
        layer = self.map_data.get_layer(name)
        return layer.properties if layer else {}

    def tileset_properties(self, name: str) -> dict:
        """
        指定タイルセットの properties 辞書を返す（名前で検索）。
        見つからない場合は空辞書。
        """
        for ts in self.map_data.tilesets:
            if ts.name == name:
                return ts.properties
        return {}

    def get_tile_props(self, tx: int, ty: int, layer_name: str) -> dict:
        """
        指定レイヤーの (tx, ty) にあるタイルの per-tile properties を返す。

        Tiled でタイルに設定したカスタムプロパティ（type, damage など）を
        取得するのに使う。タイルがない・プロパティがない場合は空辞書。

        Parameters
        ----------
        tx, ty:
            タイル座標。
        layer_name:
            レイヤー名。

        Example
        -------
        ::

            props = tmap.get_tile_props(5, 3, "ground")
            if props.get("slippery"):
                player.apply_ice_physics()
        """
        layer = self.map_data.get_layer(layer_name)
        if layer is None:
            return {}
        raw_gid = layer.get_gid(tx, ty)
        gid     = raw_gid & 0x1FFFFFFF
        if gid == 0:
            return {}
        return get_tile_properties(self.map_data.tilesets, gid)

    def get_gid(self, tx: int, ty: int, layer_name: str) -> int:
        """
        指定レイヤーの (tx, ty) の GID を返す（フリップフラグなし）。
        レイヤー・座標が不正な場合は 0。
        """
        layer = self.map_data.get_layer(layer_name)
        if layer is None:
            return 0
        return layer.get_gid(tx, ty) & 0x1FFFFFFF

    def get_object_layer(self, name: str):
        """
        名前でオブジェクトレイヤーを取得する（大文字小文字不問）。

        Returns
        -------
        ObjectLayerData | None
        """
        return self.map_data.get_object_layer(name)

    def get_objects_by_type(self, obj_type: str, layer_name: str = "") -> list:
        """
        指定 type を持つオブジェクトを全オブジェクトレイヤーから収集して返す。

        Parameters
        ----------
        obj_type:
            検索する Tiled オブジェクトの type（class）文字列。
        layer_name:
            指定するとそのレイヤーのみ検索。省略時は全レイヤー。

        Returns
        -------
        list[ObjectData]

        Example
        -------
        ::

            enemies = tmap.get_objects_by_type("enemy")
            for obj in enemies:
                spawn_enemy(obj.x, obj.y, obj.properties)
        """
        results = []
        for layer in self.map_data.object_layers:
            if layer_name and layer.name.lower() != layer_name.lower():
                continue
            for obj in layer.objects:
                if obj.obj_type == obj_type:
                    results.append(obj)
        return results

    def get_object_props(self, name: str, layer_name: str = "") -> dict:
        """
        名前でオブジェクトを検索して properties 辞書を返す。

        Parameters
        ----------
        name:
            Tiled オブジェクトの name 文字列。
        layer_name:
            指定するとそのレイヤーのみ検索。省略時は全レイヤー。

        Returns
        -------
        dict  見つからない場合は空辞書。

        Example
        -------
        ::

            props = tmap.get_object_props("chest_01")
            if props.get("contains") == "key":
                player.give_item("key")
        """
        for layer in self.map_data.object_layers:
            if layer_name and layer.name.lower() != layer_name.lower():
                continue
            for obj in layer.objects:
                if obj.name == name:
                    return obj.properties
        return {}

    # ── カメラファクトリ ────────────────────────────────────────────────────

    def make_camera(self, screen_w: int, screen_h: int) -> Camera:
        """
        このマップのサイズに合わせたカメラを生成して返す。

        Parameters
        ----------
        screen_w, screen_h:
            画面サイズ（ピクセル）。
        """
        if self._renderer is None:
            raise RuntimeError("load() を先に呼んでください")
        return Camera(
            screen_w = screen_w,
            screen_h = screen_h,
            world_w  = self._renderer.pixel_width,
            world_h  = self._renderer.pixel_height,
        )

    # ── プロパティ ───────────────────────────────────────────────────────────

    @property
    def map_data(self) -> MapData:
        if self._map_data is None:
            raise RuntimeError("load() を先に呼んでください")
        return self._map_data

    @property
    def tile_w(self) -> int:
        if self._renderer:
            return self._renderer.tile_w
        return self._map_data.tile_w if self._map_data else 0

    @property
    def tile_h(self) -> int:
        if self._renderer:
            return self._renderer.tile_h
        return self._map_data.tile_h if self._map_data else 0

    @property
    def map_w(self) -> int:
        return self._map_data.map_w if self._map_data else 0

    @property
    def map_h(self) -> int:
        return self._map_data.map_h if self._map_data else 0

    @property
    def pixel_width(self) -> int:
        return self._renderer.pixel_width if self._renderer else 0

    @property
    def pixel_height(self) -> int:
        return self._renderer.pixel_height if self._renderer else 0

    @property
    def collision(self) -> CollisionMap:
        if self._collision is None:
            raise RuntimeError("load() を先に呼んでください")
        return self._collision
