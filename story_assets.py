"""ストーリーモードの画像と背景（CSS）

- 敵の画像は assets/story/enemies/ に置き、data URI にして HTML に埋め込む。
- 味方の画像は assets/story/allies/（全身）と ally_icons/（顔）に置く。
- Lv.1〜4・9 は背景を透過した画像なので、背景画像（assets/story/backgrounds/）に重ね、
  松明のゆらぎ・霧・魔法陣の光・星のまたたきは CSS で動かす。
- それ以外は画像そのものを背景として使う。

- 敵の絵（切り抜いていないもの）は、絵をまるごと見せ（contain）、余った部分は同じ絵をぼかして埋める。
  横長の絵（エクストラ）は fit="cover" で画面を埋め、focus の位置を中心に見せる。
- アイテム・装備・状態異常のアイコンは items/ equipment/ status/ にある（ファイル名はIDと同じ）。

stage_html(enemy) が返す HTML を、戦闘コンポーネントの背景として使う。
"""
import base64
from functools import lru_cache
from pathlib import Path

import story_data

ASSET_DIR = Path(__file__).resolve().parent / "assets" / "story"


@lru_cache(maxsize=None)
def image_uri(relative_path):
    """assets/story/ からの相対パスで画像を読み、data URI にする（1回読んだら覚えておく）"""
    path = ASSET_DIR / relative_path
    mime = {"webp": "image/webp", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}[path.suffix[1:].lower()]
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def get_enemy(enemy):
    """敵のデータ。Lv の数字を渡したときは、その Lv の最初の敵（Lv.11 は難易度で違うので、dict を渡すこと）"""
    if isinstance(enemy, dict):
        return enemy
    return next(e for e in story_data.ENEMIES if e["lv"] == enemy)


def ally_image_path(lv):
    """味方の全身の絵（キャラ選択画面で st.image に渡す）"""
    return ASSET_DIR / "allies" / story_data.ALLIES[lv - 1]["image"]


def ally_icon_uri(lv):
    """味方の顔の絵（戦闘画面のHPバーの横に出す）"""
    return image_uri(f"ally_icons/{story_data.ALLIES[lv - 1]['image']}")


@lru_cache(maxsize=None)
def emoji_icon_uri(emoji, color="#2a2230"):
    """画像がまだないときの代わりのアイコン（四角いわくに絵文字）"""
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 96'><rect x='3' y='3' width='90' height='90' rx='14' "
           f"fill='{color}' stroke='#c9a24a' stroke-width='4'/><text x='48' y='64' font-size='48' text-anchor='middle'>{emoji}</text></svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _item_emoji(item_id):
    return next((i["icon"] for i in story_data.ITEMS if i["id"] == item_id), "❔")


def _equip_emoji(equip_id):
    return next((e["icon"] for e in story_data.EQUIPMENT if e["id"] == equip_id), "❔")


def item_icon_uri(item_id):
    if not (ASSET_DIR / "items" / f"{item_id}.webp").exists():
        return emoji_icon_uri(_item_emoji(item_id))
    return image_uri(f"items/{item_id}.webp")


def item_icon_path(item_id):
    """st.image に渡す絵（画像がまだなければ代わりのアイコン）"""
    path = ASSET_DIR / "items" / f"{item_id}.webp"
    return str(path) if path.exists() else emoji_icon_uri(_item_emoji(item_id))


def equipment_icon_uri(equipment_id):
    if not (ASSET_DIR / "equipment" / f"{equipment_id}.webp").exists():
        return emoji_icon_uri(_equip_emoji(equipment_id))
    return image_uri(f"equipment/{equipment_id}.webp")


def equipment_icon_path(equipment_id):
    path = ASSET_DIR / "equipment" / f"{equipment_id}.webp"
    return str(path) if path.exists() else emoji_icon_uri(_equip_emoji(equipment_id))


def enemy_image_path(enemy):
    return ASSET_DIR / "enemies" / get_enemy(enemy)["image"]


@lru_cache(maxsize=None)
def thumb_uri(relative_path, size=96):
    """アイコンを小さくした data URI（画面にたくさん並べるとき用。1回作ったら覚えておく）"""
    import io

    from PIL import Image

    path = ASSET_DIR / relative_path
    if not path.exists():
        return None
    with Image.open(path) as im:
        im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
        im.thumbnail((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=85)
    return f"data:image/webp;base64,{base64.b64encode(buf.getvalue()).decode()}"


def item_thumb(item_id, size=96):
    return thumb_uri(f"items/{item_id}.webp", size) or emoji_icon_uri(_item_emoji(item_id))


def equipment_thumb(equip_id, size=96):
    return thumb_uri(f"equipment/{equip_id}.webp", size) or emoji_icon_uri(_equip_emoji(equip_id))


def status_thumb(status_id, size=48):
    return thumb_uri(f"status/{status_id}.webp", size)


def ally_thumb(lv, size=240):
    return thumb_uri(f"allies/{story_data.ALLIES[lv - 1]['image']}", size)


@lru_cache(maxsize=None)
def silhouette_uri(enemy_key, width=360):
    """謎の敵の「形だけ」の絵（当たりマスクから作る。黒い影に紫のにじみ）"""
    import io

    from PIL import Image, ImageFilter

    mask = Image.open(ASSET_DIR / "hitmasks" / f"{enemy_key}.png").convert("L")
    mask = mask.resize((width, round(mask.height * width / mask.width)), Image.LANCZOS)
    w, h = mask.size
    bg = Image.new("RGB", (w, h), (12, 10, 18))
    glow = mask.filter(ImageFilter.GaussianBlur(10))
    purple = Image.new("RGB", (w, h), (120, 70, 200))
    bg = Image.composite(purple, bg, glow.point(lambda v: int(min(255, v * 0.9))))
    body = Image.new("RGB", (w, h), (6, 5, 10))
    bg = Image.composite(body, bg, mask.filter(ImageFilter.GaussianBlur(1)))
    buf = io.BytesIO()
    bg.save(buf, "WEBP", quality=85)
    return f"data:image/webp;base64,{base64.b64encode(buf.getvalue()).decode()}"


def status_icon_uri(status_id):
    """状態異常のアイコン。メテオは一瞬なのでアイコンなし（そのあとの黒炎で表示する）"""
    path = ASSET_DIR / "status" / f"{status_id}.webp"
    return image_uri(f"status/{status_id}.webp") if path.exists() else None


def hit_mask_uri(enemy):
    """敵の当たりマスク（白＝敵、黒＝背景）。画像と同じファイル名の .png。enemy は敵のデータ"""
    name = Path(get_enemy(enemy)["image"]).with_suffix(".png").name
    return image_uri(f"hitmasks/{name}")


# ---------------------------------------------------------------------------
# 背景の CSS
#   .st-scene            : 1ステージ分の画面（正方形）
#   .st-layer.<名前>     : 背景画像の上に重ねる、動く光・霧・粒子
# ---------------------------------------------------------------------------
SCENE_CSS = """
.st-scene {
  position: relative; width: 100%; aspect-ratio: 1 / 1; overflow: hidden;
  border-radius: 14px; background: #0c0b10; isolation: isolate;
  box-shadow: 0 10px 30px rgba(0,0,0,.45); user-select: none; -webkit-user-select: none;
}
.st-scene img { -webkit-user-drag: none; }
.st-scene > .st-layer { position: absolute; inset: 0; pointer-events: none; }
.st-scene::after {  /* 共通：周辺を暗くする */
  content: ""; position: absolute; inset: 0; z-index: 5; pointer-events: none;
  background: radial-gradient(ellipse 78% 72% at 50% 48%, transparent 58%, rgba(0,0,0,.55) 100%);
}
.st-bg, .st-photo, .st-photo-bg { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 0; }
.st-photo { object-fit: contain; z-index: 1; }
.st-photo-bg { filter: blur(22px) brightness(.5) saturate(1.1); transform: scale(1.15); }

/* 透過した敵（Lv.1〜4・9） */
.st-enemy {
  position: absolute; left: 50%; bottom: 4%; height: 86%; width: auto; max-width: 96%;
  object-fit: contain; object-position: bottom center; transform: translateX(-50%); z-index: 3;
}
.st-shadow {
  position: absolute; left: 50%; bottom: 2.4%; width: 44%; height: 7%; transform: translateX(-50%); z-index: 2;
  background: radial-gradient(ellipse at center, rgba(0,0,0,.8) 0%, rgba(0,0,0,.4) 45%, transparent 72%);
}
.st-enemy.floating { bottom: 1%; height: 92%; animation: st-float 5s ease-in-out infinite; }
@keyframes st-float { 0%,100% { transform: translate(-50%, 0); } 50% { transform: translate(-50%, -1.6%); } }

/* 動く光（背景画像の上に重ねる） */
.st-layer.torch {
  z-index: 1; mix-blend-mode: screen;
  background:
    radial-gradient(circle at 12% 32%, rgba(255,150,60,.45), transparent 16%),
    radial-gradient(circle at 88% 32%, rgba(255,150,60,.45), transparent 16%);
  animation: st-flicker 2.2s infinite steps(1);
}
.st-layer.candle {
  z-index: 1; mix-blend-mode: screen;
  background:
    radial-gradient(circle at 20% 43%, rgba(255,190,110,.40), transparent 9%),
    radial-gradient(circle at 79% 25%, rgba(255,190,110,.40), transparent 9%),
    radial-gradient(circle at 58% 61%, rgba(255,190,110,.35), transparent 8%);
  animation: st-flicker 3.1s infinite steps(1);
}
@keyframes st-flicker { 0%{opacity:1} 18%{opacity:.7} 30%{opacity:.95} 55%{opacity:.78} 72%{opacity:1} 86%{opacity:.85} }
.st-layer.moon {
  z-index: 1; mix-blend-mode: screen;
  background: linear-gradient(127deg, transparent 6%, rgba(150,175,230,.10) 16%, transparent 40%);
  animation: st-breathe 7s ease-in-out infinite;
}
.st-layer.fog {
  z-index: 4; top: 60%;
  background:
    radial-gradient(ellipse 30% 40% at 20% 60%, rgba(170,190,180,.22), transparent 70%),
    radial-gradient(ellipse 35% 45% at 70% 70%, rgba(170,190,180,.20), transparent 70%),
    radial-gradient(ellipse 25% 35% at 45% 85%, rgba(170,190,180,.18), transparent 70%);
  background-size: 200% 100%; animation: st-fog 18s linear infinite alternate;
}
@keyframes st-fog { from { background-position: 0 0; } to { background-position: 100% 0; } }
.st-layer.rune {
  z-index: 1; mix-blend-mode: screen;
  background: radial-gradient(ellipse 46% 13% at 50% 88.5%, rgba(170,90,255,.55), transparent 72%);
  animation: st-breathe 3.2s ease-in-out infinite;
}
.st-layer.sparks {
  z-index: 4; top: 45%;
  background-image:
    radial-gradient(circle, rgba(225,190,255,.95) 0 1.4px, transparent 2.4px),
    radial-gradient(circle, rgba(190,140,255,.8) 0 1px, transparent 2px);
  background-size: 37% 41%, 23% 29%; background-position: 11% 0, 63% 17%;
  -webkit-mask: linear-gradient(to top, #000 30%, transparent 100%); mask: linear-gradient(to top, #000 30%, transparent 100%);
  animation: st-rise 8s linear infinite;
}
@keyframes st-rise { from { background-position: 11% 0, 63% 17%; } to { background-position: 11% -205%, 63% -158%; } }
.st-layer.twinkle {
  z-index: 1;
  background-image:
    radial-gradient(circle, #fff 0 1.2px, transparent 2px),
    radial-gradient(circle, rgba(230,215,255,.9) 0 1px, transparent 1.8px),
    radial-gradient(circle, rgba(210,190,255,.9) 0 1.4px, transparent 2.4px);
  background-size: 37% 41%, 29% 23%, 53% 47%; background-position: 7% 13%, 61% 37%, 83% 71%;
  animation: st-breathe 3.6s ease-in-out infinite;
}
@keyframes st-breathe { 0%,100% { opacity: .55; } 50% { opacity: 1; } }
"""

# 背景の種類ごとに重ねる層
_SCENE_LAYERS = {
    "corridor": ["torch"],
    "prison": ["moon"],
    "catacomb": ["candle", "fog"],
    "altar": ["rune", "sparks"],
    "nebula": ["twinkle"],
    "image": [],
}


def stage_html(enemy):
    """敵1体分の画面（背景＋敵）の HTML。enemy は敵のデータ。CSS は SCENE_CSS を別に読み込むこと。"""
    enemy = get_enemy(enemy)
    uri = image_uri(f"enemies/{enemy['image']}")
    scene = enemy["scene"]
    layers = "".join(f'<div class="st-layer {name}"></div>' for name in _SCENE_LAYERS[scene])
    if not enemy["cutout"]:
        # 絵をまるごと見せ（contain）、余った部分は同じ絵をぼかして埋める
        layers = f'<img class="st-photo-bg" src="{uri}" alt="" draggable="false">' + layers
        fit = ""
        if enemy.get("fit") == "cover":   # 横長の絵などは、画面を埋めるように拡大して focus の位置を見せる
            fit = f' style="object-fit:cover;object-position:{enemy.get("focus", "50% 50%")}"'
        body = f'<img class="st-photo st-target" src="{uri}" alt="{enemy["name"]}" draggable="false"{fit}>'
    else:
        layers = f'<img class="st-bg" src="{image_uri(f"backgrounds/bg_{scene}.webp")}" alt="" draggable="false">' + layers
        shadow = "" if enemy["floating"] else '<div class="st-shadow"></div>'
        floating = " floating" if enemy["floating"] else ""
        body = f'{shadow}<img class="st-enemy st-target{floating}" src="{uri}" alt="{enemy["name"]}" draggable="false">'
    return f'<div class="st-scene {scene}" data-enemy="{Path(enemy["image"]).stem}">{layers}{body}</div>'


# ---------------------------------------------------------------------------
# 味方
#   カード（キャラ選択画面）: 背景つきの全身。上部の名札で、元の絵のタイトル部分を隠す
#   アイコン（戦闘画面）   : 顔のまわりを丸く切り取った画像
# ---------------------------------------------------------------------------
def get_ally(lv):
    return next(ally for ally in story_data.ALLIES if ally["lv"] == lv)


def ally_image_uri(lv):
    return image_uri(f"allies/ally_{lv:02d}.webp")


def ally_icon_uri(lv):
    return image_uri(f"ally_icons/ally_{lv:02d}.webp")


ALLY_CARD_CSS = """
.st-card { position: relative; width: 100%; aspect-ratio: 700 / 768; overflow: hidden; border-radius: 14px;
  background: #0c0b10; box-shadow: 0 8px 24px rgba(0,0,0,.45); }
.st-card img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: center top; }
.st-card .plate { position: absolute; left: 0; right: 0; top: 0; padding: 4% 6% 9%;
  background: linear-gradient(to bottom, rgba(10,8,14,.94) 0%, rgba(10,8,14,.88) 62%, rgba(10,8,14,0) 100%);
  font-family: "Hiragino Mincho ProN","Yu Mincho","Noto Serif JP","Noto Serif CJK JP",serif; color: #f1e3bf;
  text-shadow: 0 1px 3px #000; }
.st-card .plate .lv { font-size: clamp(11px, 3.2cqw, 15px); letter-spacing: .08em; color: #d4bd86; }
.st-card .plate .name { font-size: clamp(14px, 5.2cqw, 24px); font-weight: 700; line-height: 1.25; }
.st-card { container-type: inline-size; }
.st-card.locked img { filter: grayscale(1) brightness(.35); }
.st-card.locked::after { content: "🔒"; position: absolute; inset: 0; display: grid; place-items: center; font-size: 42px; }
"""


def ally_card_html(lv, locked=False):
    """キャラ選択画面のカード（CSS は ALLY_CARD_CSS）"""
    ally = get_ally(lv)
    title, _, name = ally["name"].rpartition("、")
    locked_class = " locked" if locked else ""
    return (
        f'<div class="st-card{locked_class}"><img src="{ally_image_uri(lv)}" alt="{ally["name"]}" draggable="false">'
        f'<div class="plate"><div class="lv">Lv.{lv}　{title}</div><div class="name">{name}</div></div></div>'
    )


def page_html(inner_html, extra_css=""):
    """components.html にそのまま渡せる1ページ分の HTML"""
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<style>html,body{{margin:0;background:transparent;font-family:sans-serif}}{SCENE_CSS}{extra_css}</style>"
        f"</head><body>{inner_html}</body></html>"
    )
