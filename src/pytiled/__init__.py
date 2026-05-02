"""
pytiled
~~~~~~~
Tiled JSON マップを pygame で使うためのライブラリ。

クイックスタート::

    import pygame
    import pytiled

    pygame.init()
    screen = pygame.display.set_mode((800, 600))

    tmap = pytiled.TiledMap("maps/dungeon.json")
    tmap.load()
    tmap.build()   # pygame.init() 後

    camera = tmap.make_camera(800, 600)

    while running:
        camera.follow(player.px, player.py)
        tmap.draw(screen, camera)
        if tmap.is_wall(tx, ty): ...

各クラスを直接使う場合::

    from pytiled.loader    import load_map
    from pytiled.collision import CollisionMap
    from pytiled.renderer  import MapRenderer
    from pytiled.camera    import Camera
"""

from .tilemap   import TiledMap
from .camera    import Camera
from .collision import CollisionMap
from .renderer  import MapRenderer, clear_image_cache
from .loader    import (
    load_map, MapData, TilesetData, LayerData,
    ObjectData, ObjectLayerData,
    get_tile_properties,
)
from .scene     import SceneManager
from .warp      import WarpLayer, WarpDest

__all__ = [
    "TiledMap",
    "Camera",
    "CollisionMap",
    "MapRenderer",
    "MapData",
    "TilesetData",
    "LayerData",
    "ObjectData",
    "ObjectLayerData",
    "load_map",
    "get_tile_properties",
    "clear_image_cache",
    "SceneManager",
    "WarpLayer",
    "WarpDest",
]

__version__ = "1.1.0"
