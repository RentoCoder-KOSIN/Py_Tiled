# pytiled

Tiled JSON マップを pygame で使うための軽量ライブラリ。

## インストール

```bash
pip install pytiled
```

開発用（ローカルから）:

```bash
pip install -e .
```

## クイックスタート

```python
import pygame
import pytiled

pygame.init()
screen = pygame.display.set_mode((800, 600))

tmap = pytiled.TiledMap("maps/dungeon.json")
tmap.load()    # pygame.init() より前でも可
tmap.build()   # pygame.init() 後に呼ぶ

camera = tmap.make_camera(800, 600)

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    camera.follow(player_px, player_py)
    screen.fill((0, 0, 0))
    tmap.draw(screen, camera)
    pygame.display.flip()
```

## クラス一覧

### `TiledMap`（メインクラス）

```python
tmap = pytiled.TiledMap(
    "maps/dungeon.json",
    collision_layer="collision",  # 壁判定レイヤー名（デフォルト）
    solid_gids={1, 2, 3},         # GID 指定で壁にする場合
    skip_layers={"collision"},    # 描画スキップするレイヤー名
    scale=1.0,                    # 描画スケール倍率
)
tmap.load()
tmap.build()

tmap.is_wall(tx, ty)          # 壁判定
tmap.set_wall(tx, ty, False)  # ランタイムで壁を書き換え（扉など）
tmap.draw(screen, camera)     # 描画
tmap.reload("maps/map2.json") # マップ切り替え

tmap.tile_w   # タイル幅（px）
tmap.map_w    # マップ幅（タイル数）
tmap.pixel_width  # マップ幅（px）
```

### `Camera`

```python
camera = pytiled.Camera(screen_w=800, screen_h=600,
                        world_w=map_px_w, world_h=map_px_h)

camera.follow(px, py)          # ターゲットに追従
camera.apply(wx, wy)           # ワールド座標 → スクリーン座標
camera.unapply(sx, sy)         # スクリーン座標 → ワールド座標
camera.is_visible(wx, wy, w, h) # カリング判定
```

### `CollisionMap`（単体利用）

```python
from pytiled.loader import load_map
from pytiled.collision import CollisionMap

map_data = load_map("maps/dungeon.json")
col = CollisionMap(map_data, collision_layer="walls")
col.is_wall(tx, ty)
col.set_wall(tx, ty, True)
col.get_walls()  # 壁座標リスト
```

### `MapRenderer`（単体利用）

```python
from pytiled.renderer import MapRenderer

renderer = MapRenderer(map_data, skip_layers={"collision"}, scale=2.0)
renderer.build()
renderer.draw(screen, camera)
renderer.draw_raw(screen, camera_ox, camera_oy)  # ox/oy を直接渡す版
```

## Tiled 設定

| 設定 | 内容 |
|---|---|
| マップ形式 | Orthogonal（直交）|
| 出力形式 | JSON |
| 壁判定 | `collision` という名前のレイヤーを作る |
| タイルセット | 埋め込み・外部 `.tsj/.json` どちらも対応 |
| フリップ・回転 | Tiled のビットフラグに対応済み |

collision レイヤーがない場合、`solid_gids` で壁 GID を指定するか、
何も指定しなければ全マス通行可能（マップ外のみ壁）になります。

## ライセンス

MIT
