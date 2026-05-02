"""
pytiled.loader
~~~~~~~~~~~~~~
Tiled JSON ファイルと tileset の読み込み・解析。
pygame に依存しない純粋なデータ処理層。

properties について
-------------------
Tiled の properties は以下の型を持つ:
  string / int / float / bool / color / file / object

load_map() / load_tileset() 後、各データクラスの
``.properties`` 辞書から値を取得できる。

例::

    layer = tmap.map_data.get_layer("ground")
    layer.properties["speed_multiplier"]   # float

    tile_props = tmap.get_tile_props(tx, ty, "ground")
    tile_props.get("type")                 # str など
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
#  properties ユーティリティ
# ─────────────────────────────────────────────────────────────────────────────

def _parse_properties(raw_props: list[dict]) -> dict[str, Any]:
    """
    Tiled の ``properties`` 配列 → ``{name: value}`` 辞書に変換。

    type が "bool" / "int" / "float" / "color" / "file" / "object" / "string"
    に対応。color は "#aarrggbb" 文字列のまま保持。
    """
    result: dict[str, Any] = {}
    for p in raw_props:
        name  = p.get("name", "")
        ptype = p.get("type", "string")
        value = p.get("value")
        if ptype == "bool":
            value = bool(value)
        elif ptype == "int":
            value = int(value)
        elif ptype == "float":
            value = float(value)
        # "string" / "color" / "file" / "object" はそのまま
        result[name] = value
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  データクラス
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TilesetData:
    """パース済みタイルセット情報"""
    firstgid:        int
    name:            str
    image:           str               # 画像の絶対パス（存在しない場合は空文字）
    tile_w:          int
    tile_h:          int
    columns:         int
    rows:            int
    tilecount:       int
    spacing:         int
    margin:          int
    img_w:           int
    img_h:           int
    properties:      dict[str, Any]    = field(default_factory=dict)
    # local_id → {name: value}  (Tiled の "tiles" 配列から取得)
    tile_properties: dict[int, dict[str, Any]] = field(default_factory=dict)


@dataclass
class LayerData:
    """パース済みタイルレイヤー情報"""
    name:       str
    data:       list[int]          # フラットな GID リスト
    width:      int
    height:     int
    visible:    bool               = True
    opacity:    float              = 1.0
    offsetx:    int                = 0
    offsety:    int                = 0
    properties: dict[str, Any]    = field(default_factory=dict)

    def get_gid(self, tx: int, ty: int) -> int:
        """タイル座標の生 GID を返す。範囲外は 0。"""
        if 0 <= tx < self.width and 0 <= ty < self.height:
            return self.data[ty * self.width + tx]
        return 0


@dataclass
class ObjectData:
    """Tiled オブジェクト（矩形・点など）の情報"""
    name:       str
    x:          float
    y:          float
    width:      float              = 0.0
    height:     float              = 0.0
    obj_type:   str                = ""
    properties: dict[str, Any]    = field(default_factory=dict)


@dataclass
class ObjectLayerData:
    """Tiled の objectlayer（objectgroup）情報"""
    name:       str
    objects:    list[ObjectData]   = field(default_factory=list)
    visible:    bool               = True
    properties: dict[str, Any]    = field(default_factory=dict)


@dataclass
class MapData:
    """パース済みマップ全体情報"""
    map_w:         int
    map_h:         int
    tile_w:        int
    tile_h:        int
    tilesets:      list[TilesetData]       = field(default_factory=list)
    layers:        list[LayerData]         = field(default_factory=list)
    object_layers: list[ObjectLayerData]   = field(default_factory=list)
    properties:    dict[str, Any]         = field(default_factory=dict)

    def get_object_layer(self, name: str) -> Optional["ObjectLayerData"]:
        """名前でオブジェクトレイヤーを取得（大文字小文字不問）。見つからなければ None。"""
        name_l = name.lower()
        return next((l for l in self.object_layers if l.name.lower() == name_l), None)

    def get_layer(self, name: str) -> Optional["LayerData"]:
        """名前でレイヤーを取得（大文字小文字不問）。見つからなければ None。"""
        name_l = name.lower()
        return next((l for l in self.layers if l.name.lower() == name_l), None)

    def get_layers_by_property(self, key: str, value: Any = None) -> list["LayerData"]:
        """
        指定プロパティを持つレイヤーの一覧を返す。
        value を指定した場合はその値と一致するものだけを返す。
        """
        result = []
        for layer in self.layers:
            if key in layer.properties:
                if value is None or layer.properties[key] == value:
                    result.append(layer)
        return result


# ─────────────────────────────────────────────────────────────────────────────
#  GID ユーティリティ
# ─────────────────────────────────────────────────────────────────────────────

FLIP_H_BIT = 0x80000000
FLIP_V_BIT = 0x40000000
FLIP_D_BIT = 0x20000000
GID_MASK   = 0x1FFFFFFF


def strip_flags(raw_gid: int) -> int:
    """フリップフラグを除いた純粋な GID を返す"""
    return raw_gid & GID_MASK


def get_flip_flags(raw_gid: int) -> tuple[bool, bool, bool]:
    """(flip_h, flip_v, flip_diagonal) を返す"""
    return (
        bool(raw_gid & FLIP_H_BIT),
        bool(raw_gid & FLIP_V_BIT),
        bool(raw_gid & FLIP_D_BIT),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  ローダー
# ─────────────────────────────────────────────────────────────────────────────

def _read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _parse_tileset(firstgid: int, ts_raw: dict, base_dir: str,
                   map_tile_w: int, map_tile_h: int) -> TilesetData:
    tw        = ts_raw.get("tilewidth",  map_tile_w)
    th        = ts_raw.get("tileheight", map_tile_h)
    spacing   = ts_raw.get("spacing",  0)
    margin    = ts_raw.get("margin",   0)
    columns   = ts_raw.get("columns",  0)
    tilecount = ts_raw.get("tilecount", 0)
    img_w     = ts_raw.get("imagewidth",  0)
    img_h     = ts_raw.get("imageheight", 0)

    img_rel = ts_raw.get("image", "")
    img_abs = ""
    if img_rel:
        img_abs = os.path.normpath(os.path.join(base_dir, img_rel))

    if columns == 0 and tw > 0 and img_w > 0:
        columns = (img_w - margin * 2 + spacing) // (tw + spacing)

    rows = 0
    if th > 0 and img_h > 0:
        rows = (img_h - margin * 2 + spacing) // (th + spacing)

    # タイルセット自体の properties
    ts_props = _parse_properties(ts_raw.get("properties", []))

    # per-tile properties: "tiles" 配列 [{id, properties:[...]}, ...]
    tile_props: dict[int, dict[str, Any]] = {}
    for tile_entry in ts_raw.get("tiles", []):
        local_id = tile_entry.get("id")
        raw_p    = tile_entry.get("properties", [])
        if local_id is not None and raw_p:
            tile_props[int(local_id)] = _parse_properties(raw_p)

    return TilesetData(
        firstgid        = firstgid,
        name            = ts_raw.get("name", ""),
        image           = img_abs,
        tile_w          = tw,
        tile_h          = th,
        columns         = max(columns, 1),
        rows            = rows,
        tilecount       = tilecount,
        spacing         = spacing,
        margin          = margin,
        img_w           = img_w,
        img_h           = img_h,
        properties      = ts_props,
        tile_properties = tile_props,
    )


def load_map(json_path: str) -> MapData:
    """
    Tiled JSON ファイルを読み込んで MapData を返す。

    Parameters
    ----------
    json_path:
        Tiled が書き出した .json ファイルへのパス。

    Returns
    -------
    MapData
        マップのメタ情報・タイルセット・全レイヤー・properties を保持する。
    """
    json_path = os.path.abspath(json_path)
    base_dir  = os.path.dirname(json_path)
    raw       = _read_json(json_path)

    map_w  = raw["width"]
    map_h  = raw["height"]
    tile_w = raw["tilewidth"]
    tile_h = raw["tileheight"]

    # マップ自体の properties
    map_props = _parse_properties(raw.get("properties", []))

    # ── tilesets ──
    tilesets: list[TilesetData] = []
    for entry in raw.get("tilesets", []):
        firstgid = entry["firstgid"]
        if "source" in entry:
            ts_path = os.path.normpath(os.path.join(base_dir, entry["source"]))
            ts_raw  = _read_json(ts_path)
        else:
            ts_raw = entry
        tilesets.append(_parse_tileset(firstgid, ts_raw, base_dir, tile_w, tile_h))

    tilesets.sort(key=lambda t: t.firstgid, reverse=True)

    # ── layers（tilelayer のみ、全件）──
    layers: list[LayerData] = []
    for layer in raw.get("layers", []):
        if layer.get("type") != "tilelayer":
            continue
        layers.append(LayerData(
            name       = layer["name"],
            data       = layer["data"],
            width      = layer.get("width",   map_w),
            height     = layer.get("height",  map_h),
            visible    = layer.get("visible", True),
            opacity    = layer.get("opacity", 1.0),
            offsetx    = layer.get("offsetx", 0),
            offsety    = layer.get("offsety", 0),
            properties = _parse_properties(layer.get("properties", [])),
        ))

    # ── object layers（objectgroup）──
    object_layers: list[ObjectLayerData] = []
    for layer in raw.get("layers", []):
        if layer.get("type") != "objectgroup":
            continue
        objs: list[ObjectData] = []
        for obj in layer.get("objects", []):
            objs.append(ObjectData(
                name       = obj.get("name", ""),
                x          = float(obj.get("x", 0)),
                y          = float(obj.get("y", 0)),
                width      = float(obj.get("width",  0)),
                height     = float(obj.get("height", 0)),
                obj_type   = obj.get("type", obj.get("class", "")),
                properties = _parse_properties(obj.get("properties", [])),
            ))
        object_layers.append(ObjectLayerData(
            name       = layer["name"],
            objects    = objs,
            visible    = layer.get("visible", True),
            properties = _parse_properties(layer.get("properties", [])),
        ))

    return MapData(
        map_w         = map_w,
        map_h         = map_h,
        tile_w        = tile_w,
        tile_h        = tile_h,
        tilesets      = tilesets,
        layers        = layers,
        object_layers = object_layers,
        properties    = map_props,
    )


def find_tileset(tilesets: list[TilesetData], gid: int) -> Optional[TilesetData]:
    """GID に対応する TilesetData を返す（firstgid 降順リスト前提）"""
    for ts in tilesets:
        if gid >= ts.firstgid:
            return ts
    return None


def get_tile_properties(
    tilesets: list[TilesetData], gid: int
) -> dict[str, Any]:
    """
    GID に対応するタイルの per-tile properties を返す。
    存在しない場合は空辞書。
    """
    ts = find_tileset(tilesets, gid)
    if ts is None:
        return {}
    local_id = gid - ts.firstgid
    return ts.tile_properties.get(local_id, {})
