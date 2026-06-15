from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    concatenate_videoclips,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip
)
import os
import sqlite3
import unicodedata
from colorama import init, Fore
import random
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Initialize colorama
init(autoreset=True)

# ===========================
# Configuración de Salida
# ===========================
# 'vertical' para TikTok (9:16), 'horizontal' para YouTube (16:9)
OUTPUT_ASPECT = 'vertical'  # 'vertical' | 'horizontal'

if OUTPUT_ASPECT == 'vertical':
    TARGET_RESOLUTION = (1080, 1920)  # (ancho, alto)
else:
    TARGET_RESOLUTION = (1920, 1080)

DESIGN_RESOLUTION = TARGET_RESOLUTION

def _resolution_from_env(default_resolution):
    raw_value = os.getenv("STEAM_VIDEO_RESOLUTION", "").strip().lower()
    if not raw_value:
        return default_resolution

    if OUTPUT_ASPECT == "vertical":
        presets = {
            "1080p": (1080, 1920),
            "720p": (720, 1280),
            "540p": (540, 960),
        }
    else:
        presets = {
            "1080p": (1920, 1080),
            "720p": (1280, 720),
            "540p": (960, 540),
        }

    if raw_value in presets:
        return presets[raw_value]

    normalized = raw_value.replace("*", "x").replace(" ", "")
    if "x" in normalized:
        width, height = normalized.split("x", 1)
        if width.isdigit() and height.isdigit():
            return (int(width), int(height))

    print(Fore.YELLOW + f"[WARN] STEAM_VIDEO_RESOLUTION invalida: {raw_value}. Usando {default_resolution}.")
    return default_resolution

TARGET_RESOLUTION = _resolution_from_env(TARGET_RESOLUTION)

# Modo de fondo:
# - blur: fondo del clip con desenfoque por frame (mejor estética, más lento)
# - cover: fondo del clip en cover + oscurecido, sin blur por frame (rápido)
# - black: barras negras
_DEFAULT_BACKGROUND_MODE = 'cover' if OUTPUT_ASPECT == 'vertical' else 'black'
BACKGROUND_MODE = os.getenv("STEAM_VIDEO_BACKGROUND", _DEFAULT_BACKGROUND_MODE).strip().lower()
if BACKGROUND_MODE not in {"blur", "cover", "black"}:
    BACKGROUND_MODE = _DEFAULT_BACKGROUND_MODE

# ====== Parámetros del fondo (blur + zoom + oscurecido) ======
BG_ZOOM_EXTRA = 1.20       # zoom para cubrir
# Intensidad del blur (¡AGRESIVO para que se note!)
BG_BLUR_SIGMA = 5.0       # si usa scikit-image (8–24)
BG_BLUR_RADIUS = 30.0      # si usa Pillow (40–90)
BG_BLUR_PASSES = 1         # pasadas extra para reforzar (1–2)
BG_BLUR_WORK_SCALE = 0.35  # downscale durante blur (0.3–0.6; menor = más blur + más rápido)
# Oscurecer fondo: 1.0 sin cambio; valores menores lo oscurecen (se traduce a overlay)
BG_DARKEN = 0.70           # 0.75–0.90 es típico

# ===========================
# Variables de Audio/Video
# ===========================
MUSIC_FILE = 'track1.mp3'  # Música intro/outro
OUTPUT_FILE = os.getenv("STEAM_VIDEO_OUTPUT", "video_final.mp4")
OUTPUT_FPS = int(os.getenv("STEAM_VIDEO_FPS", "24"))
OUTPUT_THREADS = int(os.getenv("STEAM_VIDEO_THREADS", "4"))
OUTPUT_BITRATE = os.getenv("STEAM_VIDEO_BITRATE", "5000k")
OUTPUT_PRESET = os.getenv("STEAM_VIDEO_PRESET", "medium")
CONCAT_METHOD = os.getenv("STEAM_CONCAT_METHOD", "chain").strip().lower()
if CONCAT_METHOD not in {"chain", "compose"}:
    CONCAT_METHOD = "chain"
MUSIC_VOLUME = 0.1
MUSIC_START_TIME = 15
MUSIC_FADE_DURATION = 3

NARRATION_VOLUME = 1.0
SHOW_VISUAL_OVERLAYS = os.getenv("STEAM_VIDEO_OVERLAYS", "1") != "0"
SUBTITLE_MAX_WORDS = 9

VIDEO_VOLUME = 0.0       # Intro/Outro media
GAME_VIDEO_VOLUME = 0.25 # Audio de gameplay bajo vs narración

# Segmentos para intro/outro
INTRO_FRAGMENT_START = 0.5
OUTRO_FRAGMENT_START = 0.75

# ===========================
# Utils de blur (robustos)
# ===========================
def to_uint8(img):
    """Asegura uint8 en [0,255] para evitar videos negros."""
    if isinstance(img, np.ndarray) and img.dtype == np.uint8:
        return img
    if isinstance(img, np.ndarray) and issubclass(img.dtype.type, np.floating):
        if img.max() <= 1.0:
            img = img * 255.0
        img = np.clip(img, 0, 255)
        return img.astype(np.uint8)
    if isinstance(img, np.ndarray):
        img = np.clip(img, 0, 255)
        return img.astype(np.uint8)
    return img

def _skimage_gaussian_func():
    try:
        # skimage ≥ 0.19
        from skimage.filters import gaussian
        # probamos firma nueva con channel_axis
        def blur_sk(img, sigma):
            return to_uint8(gaussian(img, sigma=sigma, preserve_range=True, channel_axis=-1))
        # test mínimo sobre un array chiquito para detectar firmas viejas
        _ = blur_sk(np.zeros((2,2,3), dtype=np.uint8), 1.0)
        return blur_sk, "skimage(channel_axis)"
    except TypeError:
        # versión vieja: multichannel=True
        from skimage.filters import gaussian
        def blur_sk_old(img, sigma):
            return to_uint8(gaussian(img, sigma=sigma, preserve_range=True, multichannel=True))
        return blur_sk_old, "skimage(multichannel)"
    except Exception:
        return None, None

def _pillow_gaussian_func():
    try:
        from PIL import Image, ImageFilter
        def blur_pil(img, radius):
            im = Image.fromarray(to_uint8(img))
            im = im.filter(ImageFilter.GaussianBlur(radius=radius))
            return np.array(im, dtype=np.uint8)
        return blur_pil
    except Exception:
        return None

def build_blur_function():
    """
    Devuelve (func, desc, uses_radius)
      - func(frame) -> frame_uint8
      - desc: texto para logging
      - uses_radius: True si el parámetro es 'radius' (Pillow), False si es 'sigma' (skimage)
    """
    sk_func, sk_desc = _skimage_gaussian_func()
    if sk_func is not None:
        print(Fore.CYAN + f"[BG BLUR] Usando {sk_desc} sigma={BG_BLUR_SIGMA}, passes={BG_BLUR_PASSES}, work_scale={BG_BLUR_WORK_SCALE}")
        def f(img):
            out = sk_func(img, BG_BLUR_SIGMA)
            # pasadas extra si se piden
            for _ in range(max(0, int(BG_BLUR_PASSES)-1)):
                out = sk_func(out, BG_BLUR_SIGMA)
            return to_uint8(out)
        return f, sk_desc, False

    pil_func = _pillow_gaussian_func()
    if pil_func is not None:
        print(Fore.CYAN + f"[BG BLUR] Usando Pillow GaussianBlur radius={BG_BLUR_RADIUS}, passes={BG_BLUR_PASSES}, work_scale={BG_BLUR_WORK_SCALE}")
        def f(img):
            out = pil_func(img, BG_BLUR_RADIUS)
            for _ in range(max(0, int(BG_BLUR_PASSES)-1)):
                out = pil_func(out, BG_BLUR_RADIUS)
            return to_uint8(out)
        return f, "pillow", True

    print(Fore.YELLOW + "[WARN] Ni scikit-image ni Pillow disponibles. Fondo sin blur.")
    def identity(img):
        return to_uint8(img)
    return identity, "none", False

def apply_clip_blur(clip):
    """
    Aplica blur por frame al clip:
      - downscale temporal (para acelerar y aumentar efecto)
      - fl_image con función robusta (skimage/pillow)
      - upscale de vuelta si hicimos downscale
    """
    fn, desc, _ = build_blur_function()
    work = clip.resize(BG_BLUR_WORK_SCALE) if (0 < BG_BLUR_WORK_SCALE < 1.0) else clip
    blurred = work.fl_image(fn)
    if work is clip:
        return blurred
    else:
        return blurred.resize((clip.w, clip.h))

# ===========================
# Helpers de Layout
# ===========================
def _make_black_bg(duration):
    """Fondo negro del tamaño TARGET_RESOLUTION sin audio."""
    return ColorClip(size=TARGET_RESOLUTION, color=(0, 0, 0), duration=duration).set_audio(None)

def _make_blur_bg_from_source(src_clip, duration):
    """
    Genera un fondo a partir del propio src_clip:
      - COVER + zoom para llenar el canvas
      - Blur por frame (robusto) — MISMO método que el test que te funcionó
      - Oscurecer con overlay negro
      - Composición centrada al canvas
    """
    W, H = TARGET_RESOLUTION
    src = src_clip.set_audio(None)

    # COVER + zoom
    scale_factor = max(W / src.w, H / src.h) * BG_ZOOM_EXTRA
    covered = src.resize(scale_factor)

    # BLUR SEGURO (skimage/pillow) + downscale temporal
    blurred = apply_clip_blur(covered)

    # Oscurecer con overlay negro (fiable)
    overlay_alpha = max(0.0, min(1.0, 1.0 - BG_DARKEN))
    layers = [blurred.set_position('center')]
    if overlay_alpha > 0:
        black = ColorClip(size=TARGET_RESOLUTION, color=(0, 0, 0), duration=duration).set_opacity(overlay_alpha)
        layers.append(black)

    bg = CompositeVideoClip(layers, size=TARGET_RESOLUTION).set_duration(duration)
    return bg.set_audio(None)

def _make_cover_bg_from_source(src_clip, duration):
    W, H = TARGET_RESOLUTION
    src = src_clip.set_audio(None)
    scale_factor = max(W / src.w, H / src.h) * BG_ZOOM_EXTRA
    covered = src.resize(scale_factor).set_position('center')
    overlay_alpha = max(0.0, min(1.0, 1.0 - BG_DARKEN))
    layers = [covered]
    if overlay_alpha > 0:
        black = ColorClip(size=TARGET_RESOLUTION, color=(0, 0, 0), duration=duration).set_opacity(overlay_alpha)
        layers.append(black)
    return CompositeVideoClip(layers, size=TARGET_RESOLUTION).set_duration(duration).set_audio(None)

def fit_to_canvas(clip, bg_mode=BACKGROUND_MODE):
    """
    Empaqueta un clip en un lienzo TARGET_RESOLUTION con:
      - Fondo: mismo clip en COVER + blur + oscurecido
      - Frente: clip original en CONTAIN (sin recorte), centrado.
    """
    W, H = TARGET_RESOLUTION
    clip_ratio = clip.w / clip.h
    canvas_ratio = W / H

    if clip_ratio >= canvas_ratio:
        fg = clip.resize(width=W)
    else:
        fg = clip.resize(height=H)

    fg = fg.set_position(('center', 'center'))

    # Fondo
    if bg_mode == 'blur':
        bg = _make_blur_bg_from_source(clip, fg.duration)
    elif bg_mode == 'cover':
        bg = _make_cover_bg_from_source(clip, fg.duration)
    else:
        bg = _make_black_bg(fg.duration)

    comp = CompositeVideoClip([bg, fg], size=TARGET_RESOLUTION).set_duration(fg.duration)

    # Heredar audio del foreground si existe
    if hasattr(clip, 'audio') and clip.audio:
        comp = comp.set_audio(clip.audio)

    return comp

# ===========================
# DB helpers
# ===========================
def get_inuse_game_folders():
    print(Fore.BLUE + "Obtaining games from DB...")
    conn = sqlite3.connect('SR_BBDD.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM inusegames ORDER BY position")
    game_names = [row[0] for row in cursor.fetchall()]
    conn.close()
    if not game_names:
        print(Fore.RED + "No se encontraron juegos en la tabla 'inusegames'.")
        return []
    game_folders = ["".join([c for c in name if c not in '<>:\"/\\|?*']) for name in game_names]
    print(Fore.GREEN + f"Se encontraron {len(game_folders)} juegos en uso.")
    return game_folders

def sanitize_folder_name(name):
    return "".join([c for c in name if c not in '<>:"/\\|?*'])

def get_inuse_game_metadata():
    conn = sqlite3.connect('SR_BBDD.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.position, i.name, g.price, g.reviewcount, g.reviewvalue,
               s.twitchviewers, s.popular, s.score, g.tags
        FROM inusegames i
        LEFT JOIN games g ON g.name = i.name
        LEFT JOIN gamestats s ON s.name = i.name
        ORDER BY i.position
    """)
    rows = cursor.fetchall()
    conn.close()

    metadata = {}
    for row in rows:
        position, name, price, reviewcount, reviewvalue, twitchviewers, popular, score, tags = row
        metadata[sanitize_folder_name(name)] = {
            "position": position,
            "name": name,
            "price": price or "",
            "reviewcount": int(reviewcount or 0),
            "reviewvalue": reviewvalue or "",
            "twitchviewers": int(twitchviewers or 0),
            "popular": popular or "no",
            "score": float(score or 0),
            "tags": tags or "",
        }
    return metadata

def _font(size, bold=False):
    return max(1, int(round(size / 10)))

def _base_font():
    return ImageFont.load_default()

def _safe_overlay_text(text):
    value = str(text or "")
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "\uff08": "(",
        "\uff09": ")",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = unicodedata.normalize("NFKD", value)
    return value.encode("latin-1", "ignore").decode("latin-1")

def _text_size(text, draw_font):
    text = _safe_overlay_text(text)
    probe = Image.new("L", (1, 1), 0)
    probe_draw = ImageDraw.Draw(probe)
    bbox = probe_draw.textbbox((0, 0), text, font=_base_font())
    scale = max(1, int(draw_font))
    return (bbox[2] - bbox[0]) * scale, (bbox[3] - bbox[1]) * scale

def _draw_text(image, xy, text, fill, draw_font):
    text = _safe_overlay_text(text)
    scale = max(1, int(draw_font))
    base = _base_font()
    probe = Image.new("L", (1, 1), 0)
    probe_draw = ImageDraw.Draw(probe)
    bbox = probe_draw.textbbox((0, 0), text, font=base)
    base_w = max(1, bbox[2] - bbox[0] + 4)
    base_h = max(1, bbox[3] - bbox[1] + 4)
    layer = Image.new("RGBA", (base_w, base_h), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.text((2 - bbox[0], 2 - bbox[1]), text, fill=fill, font=base)
    if scale != 1:
        layer = layer.resize((base_w * scale, base_h * scale), Image.Resampling.NEAREST)
    image.alpha_composite(layer, dest=(int(xy[0]), int(xy[1])))

def _format_int(value):
    try:
        value = int(value or 0)
    except (TypeError, ValueError):
        value = 0
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)

def _format_score(value):
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "0"

def _clean_tags(tags, limit=3):
    values = []
    for tag in str(tags or "").split(","):
        clean = tag.strip()
        if clean and clean not in values:
            values.append(clean)
    return values[:limit]

def _wrap_text(draw, text, draw_font, max_width, max_lines=None):
    words = str(text or "").split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        width, _ = _text_size(test, draw_font)
        if width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and _text_size(lines[-1] + "...", draw_font)[0] > max_width:
            lines[-1] = lines[-1][:-1].rstrip()
        lines[-1] += "..."
    return lines

def _image_clip_from_rgba(image, duration, start=0):
    if image.size != TARGET_RESOLUTION:
        image = image.resize(TARGET_RESOLUTION, Image.Resampling.LANCZOS)
    return ImageClip(np.array(image), transparent=True).set_start(start).set_duration(duration)

def _make_canvas():
    return Image.new("RGBA", DESIGN_RESOLUTION, (0, 0, 0, 0))

def _draw_chip(image, draw, x, y, text, fill=(12, 16, 24, 210), accent=(0, 212, 255, 255)):
    chip_font = _font(34, bold=True)
    width = _text_size(text, chip_font)[0] + 44
    draw.rounded_rectangle((x, y, x + width, y + 58), radius=18, fill=fill)
    draw.rectangle((x, y, x + 8, y + 58), fill=accent)
    _draw_text(image, (x + 24, y + 10), text, (255, 255, 255, 255), chip_font)
    return x + width + 14

def make_game_overlay(metadata, duration):
    if not metadata or not SHOW_VISUAL_OVERLAYS:
        return None

    image = _make_canvas()
    draw = ImageDraw.Draw(image)
    width, _ = image.size
    name = metadata["name"]
    position = metadata["position"]

    draw.rounded_rectangle((46, 52, width - 46, 330), radius=28, fill=(4, 7, 12, 210))
    draw.rectangle((46, 52, 64, 330), fill=(0, 212, 255, 255))
    _draw_text(image, (88, 78), f"#{position}", (0, 212, 255, 255), _font(72, bold=True))
    _draw_text(image, (205, 88), "STEAM RELEASE RANKING", (210, 230, 240, 255), _font(28, bold=True))

    title_font = _font(50, bold=True)
    title_lines = _wrap_text(draw, name, title_font, width - 180, max_lines=2)
    y = 132
    for line in title_lines:
        _draw_text(image, (88, y), line, (255, 255, 255, 255), title_font)
        y += 56

    chips_y = 350
    x = 56
    if metadata["price"]:
        x = _draw_chip(image, draw, x, chips_y, metadata["price"], accent=(255, 196, 0, 255))
    x = _draw_chip(image, draw, x, chips_y, f"{_format_int(metadata['reviewcount'])} reviews")
    x = _draw_chip(image, draw, x, chips_y, f"{metadata['reviewvalue']}/10")

    x = 56
    chips_y += 72
    x = _draw_chip(image, draw, x, chips_y, f"Twitch {_format_int(metadata['twitchviewers'])}", accent=(145, 70, 255, 255))
    _draw_chip(image, draw, x, chips_y, f"Score {_format_score(metadata['score'])}", accent=(255, 70, 120, 255))

    tags = _clean_tags(metadata["tags"])
    if tags:
        _draw_text(image, (62, chips_y + 86), " / ".join(tags), (220, 232, 238, 230), _font(30))

    return _image_clip_from_rgba(image, min(duration, 9.0))

def _read_script_text(path):
    if not path or not os.path.exists(path):
        return ""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return text.strip().strip('"')

def _caption_chunks(text):
    words = text.replace("\n", " ").split()
    chunks = []
    while words:
        take = min(SUBTITLE_MAX_WORDS, len(words))
        if len(words) - take <= 3:
            take = len(words)
        chunks.append(" ".join(words[:take]))
        words = words[take:]
    return chunks

def make_caption_clips(script_path, duration, start_offset=1.2):
    if not SHOW_VISUAL_OVERLAYS:
        return []
    chunks = _caption_chunks(_read_script_text(script_path))
    if not chunks:
        return []

    available = max(0.5, duration - start_offset)
    per_chunk = max(1.2, available / len(chunks))
    clips = []
    cursor = start_offset
    width, height = DESIGN_RESOLUTION
    caption_font = _font(44, bold=True)

    for chunk in chunks:
        if cursor >= duration - 0.2:
            break
        image = _make_canvas()
        draw = ImageDraw.Draw(image)
        lines = _wrap_text(draw, chunk, caption_font, width - 130, max_lines=2)
        line_height = 56
        box_h = 38 + line_height * len(lines)
        y0 = height - box_h - 82
        draw.rounded_rectangle((48, y0, width - 48, height - 72), radius=24, fill=(0, 0, 0, 190))
        y = y0 + 18
        for line in lines:
            text_w, _ = _text_size(line, caption_font)
            x = (width - text_w) // 2
            _draw_text(image, (x + 2, y + 2), line, (0, 0, 0, 180), caption_font)
            _draw_text(image, (x, y), line, (255, 255, 255, 255), caption_font)
            y += line_height
        clip_duration = min(per_chunk, duration - cursor)
        clips.append(_image_clip_from_rgba(image, clip_duration, start=cursor))
        cursor += clip_duration
    return clips

def add_game_visuals(video_clip, carpeta_medios, metadata):
    if not SHOW_VISUAL_OVERLAYS:
        return video_clip
    overlays = [video_clip]
    overlay = make_game_overlay(metadata, video_clip.duration)
    if overlay:
        overlays.append(overlay)
    script_path = os.path.join(carpeta_medios, "description.txt")
    overlays.extend(make_caption_clips(script_path, video_clip.duration, start_offset=2.0))
    final = CompositeVideoClip(overlays, size=TARGET_RESOLUTION).set_duration(video_clip.duration)
    if video_clip.audio:
        final = final.set_audio(video_clip.audio)
    return final

def make_intro_overlay(metadata_by_folder, duration):
    if not SHOW_VISUAL_OVERLAYS:
        return None
    items = sorted(metadata_by_folder.values(), key=lambda item: item["position"])
    image = _make_canvas()
    draw = ImageDraw.Draw(image)
    width, height = image.size

    draw.rounded_rectangle((52, 108, width - 52, 548), radius=34, fill=(3, 8, 14, 220))
    draw.rectangle((52, 108, 70, 548), fill=(0, 212, 255, 255))
    _draw_text(image, (96, 142), f"TOP {len(items)}", (0, 212, 255, 255), _font(86, bold=True))
    _draw_text(image, (96, 238), "NEW STEAM RELEASES", (255, 255, 255, 255), _font(58, bold=True))
    _draw_text(image, (96, 314), "Ranked by reviews, Twitch traction and Steam momentum", (220, 232, 238, 240), _font(32))

    y = 620
    for item in items[:5]:
        draw.rounded_rectangle((66, y, width - 66, y + 86), radius=20, fill=(0, 0, 0, 165))
        _draw_text(image, (96, y + 18), f"#{item['position']}", (0, 212, 255, 255), _font(40, bold=True))
        _draw_text(image, (192, y + 18), item["name"][:34], (255, 255, 255, 255), _font(40, bold=True))
        y += 100

    _draw_text(image, (84, height - 130), "Quick picks for what is moving on Steam right now", (235, 240, 245, 235), _font(32))
    return _image_clip_from_rgba(image, min(duration, 8.0))

def make_outro_overlay(metadata_by_folder, duration):
    if not SHOW_VISUAL_OVERLAYS:
        return None
    items = sorted(metadata_by_folder.values(), key=lambda item: item["position"])
    image = _make_canvas()
    draw = ImageDraw.Draw(image)
    width, height = image.size

    draw.rounded_rectangle((54, 130, width - 54, height - 160), radius=34, fill=(3, 8, 14, 215))
    _draw_text(image, (92, 178), "FINAL RANKING", (255, 255, 255, 255), _font(64, bold=True))
    _draw_text(image, (92, 252), "Steam releases worth checking", (0, 212, 255, 255), _font(36, bold=True))

    y = 350
    for item in items[:5]:
        draw.rounded_rectangle((88, y, width - 88, y + 118), radius=22, fill=(15, 22, 32, 220))
        _draw_text(image, (122, y + 24), f"#{item['position']}", (0, 212, 255, 255), _font(44, bold=True))
        _draw_text(image, (220, y + 22), item["name"][:29], (255, 255, 255, 255), _font(40, bold=True))
        _draw_text(image, (220, y + 70), f"Score {_format_score(item['score'])}  |  {_format_int(item['reviewcount'])} reviews", (220, 232, 238, 235), _font(28))
        y += 136

    return _image_clip_from_rgba(image, min(duration, 10.0))

# ===========================
# Sección de Juegos
# ===========================
def procesar_seccion(carpeta_medios, archivo_audio, metadata=None):
    print(Fore.BLUE + f"\nProcessing: {os.path.basename(carpeta_medios)}")
    print(Fore.BLUE + f"Audio: {archivo_audio}")

    # Reunir media1..media9
    archivos_media = []
    for i in range(1, 10):
        media_mp4 = os.path.join(carpeta_medios, f"media{i}.mp4")
        media_jpg = os.path.join(carpeta_medios, f"media{i}.jpg")
        media_png = os.path.join(carpeta_medios, f"media{i}.png")
        media_jpeg = os.path.join(carpeta_medios, f"media{i}.jpeg")
        if os.path.exists(media_mp4):
            archivos_media.append(media_mp4)
        elif os.path.exists(media_jpg):
            archivos_media.append(media_jpg)
        elif os.path.exists(media_png):
            archivos_media.append(media_png)
        elif os.path.exists(media_jpeg):
            archivos_media.append(media_jpeg)

    if not archivos_media:
        print(Fore.RED + f"No se encontraron archivos de medios en {carpeta_medios}")
        return None

    # Cargar narración
    if not os.path.exists(archivo_audio):
        print(Fore.RED + f"No se encontró el archivo de audio {archivo_audio}")
        return None

    try:
        narration_clip = AudioFileClip(archivo_audio).volumex(NARRATION_VOLUME)
        duracion_audio = narration_clip.duration
        print(Fore.GREEN + f"Audio duration: {duracion_audio:.2f} sec")
    except Exception as e:
        print(Fore.RED + f"Error al cargar el audio {archivo_audio}: {e}")
        return None

    clips = []
    duracion_total_clips = 0

    # Usar primero videos si hay
    mp4_files = [f for f in archivos_media if f.endswith('.mp4')]

    for mp4_file in mp4_files:
        print(Fore.BLUE + f"Trying to use video file: {mp4_file}")
        try:
            video = VideoFileClip(mp4_file)
            # Cortar los primeros 7s para evitar intros del tráiler
            if video.duration > 7:
                start_time = 7
                end_time = video.duration
                video_duration = end_time - start_time
                if video_duration >= duracion_audio:
                    base = video.subclip(start_time, start_time + duracion_audio).volumex(GAME_VIDEO_VOLUME)
                    clip = fit_to_canvas(base)
                    duracion_total_clips += duracion_audio
                    clips.append(clip)
                    print(Fore.GREEN + f"Using video {mp4_file} from {start_time}s to cover the audio.")
                    break
                else:
                    base = video.subclip(start_time, end_time).volumex(GAME_VIDEO_VOLUME)
                    clip = fit_to_canvas(base)
                    duracion_total_clips += video_duration
                    clips.append(clip)
                    duracion_audio -= video_duration
                    print(Fore.YELLOW + f"Video {mp4_file} no es suficiente, quedan {duracion_audio:.2f}s por cubrir.")
            else:
                print(Fore.YELLOW + f"El video {mp4_file} es demasiado corto tras cortar 7s.")
                continue
        except Exception as e:
            print(Fore.RED + f"Error al procesar el archivo {mp4_file}: {e}")
            continue

    if duracion_total_clips < narration_clip.duration:
        # Rellenamos con imágenes
        duracion_restante = narration_clip.duration - duracion_total_clips
        print(Fore.BLUE + f"Necesitamos cubrir {duracion_restante:.2f}s con imágenes.")
        image_files = [f for f in archivos_media if f.endswith(('.jpg', '.jpeg', '.png'))]
        num_images = len(image_files)
        if num_images == 0:
            print(Fore.RED + "No hay imágenes disponibles para cubrir el audio restante.")
            return None
        duracion_por_imagen = duracion_restante / num_images
        for image_file in image_files:
            try:
                base = ImageClip(image_file).set_duration(duracion_por_imagen)
                clip = fit_to_canvas(base)
                clips.append(clip)
                print(Fore.GREEN + f"Agregada imagen {image_file} ({duracion_por_imagen:.2f}s).")
            except Exception as e:
                print(Fore.RED + f"Error al procesar la imagen {image_file}: {e}")
                continue

    if clips:
        try:
            video_concat = concatenate_videoclips(clips, method="compose")
            # Audio de gameplay bajo + narración
            video_audio = video_concat.audio.volumex(GAME_VIDEO_VOLUME) if video_concat.audio else None
            if video_audio:
                video_audio = video_audio.set_duration(narration_clip.duration)
            final_audio = CompositeAudioClip([a for a in [video_audio, narration_clip] if a is not None])
            video_final = video_concat.set_audio(final_audio).fadein(1).fadeout(1)
            video_final = add_game_visuals(video_final, carpeta_medios, metadata)
            print(Fore.GREEN + "Concatenated successfully.")
        except Exception as e:
            print(Fore.RED + f"Error al concatenar los clips: {e}")
            return None
    else:
        print(Fore.RED + f"No se pudieron crear clips para {carpeta_medios}")
        narration_clip.close()
        return None

    return video_final

# ===========================
# Intro
# ===========================
def procesar_intro(carpeta_intro_outro, game_folders, current_dir, metadata_by_folder=None):
    print(Fore.BLUE + "\nProcessing Intro...")
    intro_audio_path = os.path.join(carpeta_intro_outro, 'intro.mp3')
    if not os.path.exists(intro_audio_path):
        print(Fore.RED + f"No se encontró el archivo de audio para la intro: {intro_audio_path}")
        return None

    try:
        narration_clip = AudioFileClip(intro_audio_path).volumex(NARRATION_VOLUME)
        duracion_audio = narration_clip.duration
        print(Fore.GREEN + f"Duration for intro: {duracion_audio:.2f} sec")
    except Exception as e:
        print(Fore.RED + f"Error al cargar el audio de la intro: {e}")
        return None

    # Música
    music_path = os.path.join(os.getcwd(), 'music', MUSIC_FILE)
    if not os.path.exists(music_path):
        print(Fore.RED + f"No se encontró el archivo de música: {music_path}")
        return None

    try:
        music_clip = AudioFileClip(music_path)
        if music_clip.duration > MUSIC_START_TIME:
            music_clip = music_clip.subclip(MUSIC_START_TIME)
        else:
            print(Fore.RED + "La música es más corta que el tiempo de inicio especificado.")
            return None
        music_clip = music_clip.set_duration(duracion_audio).volumex(MUSIC_VOLUME)
        music_clip = music_clip.audio_fadein(MUSIC_FADE_DURATION).audio_fadeout(MUSIC_FADE_DURATION)
        combined_audio = CompositeAudioClip([narration_clip, music_clip])
    except Exception as e:
        print(Fore.RED + f"Error al procesar la música: {e}")
        return None

    num_games = len(game_folders)
    duracion_por_juego = duracion_audio / max(num_games, 1)

    clips = []
    random.shuffle(game_folders)

    for game_folder in game_folders:
        game_path = os.path.join(current_dir, game_folder)
        # elegir el mp4 con mayor índice
        mp4_files = []
        for i in reversed(range(1, 10)):
            media_mp4 = os.path.join(game_path, f"media{i}.mp4")
            if os.path.exists(media_mp4):
                mp4_files.append(media_mp4)

        if mp4_files:
            mp4_file = mp4_files[0]
            print(Fore.BLUE + f"Using video {mp4_file} for intro")
            try:
                base = VideoFileClip(mp4_file).without_audio()
                start_time = base.duration * INTRO_FRAGMENT_START
                end_time = base.duration
                clip_duration = end_time - start_time
                if clip_duration >= duracion_por_juego:
                    sub = base.subclip(start_time, start_time + duracion_por_juego)
                    clip = fit_to_canvas(sub).volumex(VIDEO_VOLUME)
                    clips.append(clip)
                    print(Fore.GREEN + f"Adding clip {mp4_file} to the intro.")
                else:
                    print(Fore.YELLOW + f"El video {mp4_file} es corto para la intro.")
                    # fallback a imágenes
                    image_files = []
                    for i in range(1, 10):
                        media_jpg = os.path.join(game_path, f"media{i}.jpg")
                        media_png = os.path.join(game_path, f"media{i}.png")
                        media_jpeg = os.path.join(game_path, f"media{i}.jpeg")
                        if os.path.exists(media_jpg):
                            image_files.append(media_jpg)
                        elif os.path.exists(media_png):
                            image_files.append(media_png)
                        elif os.path.exists(media_jpeg):
                            image_files.append(media_jpeg)
                    if image_files:
                        duracion_por_imagen = duracion_por_juego / len(image_files)
                        for image_file in image_files:
                            img_clip = fit_to_canvas(ImageClip(image_file).set_duration(duracion_por_imagen)).volumex(0)
                            clips.append(img_clip)
                            print(Fore.GREEN + f"Agregada imagen {image_file} a la intro.")
            except Exception as e:
                print(Fore.RED + f"Error al procesar el archivo {mp4_file}: {e}")
                continue
        else:
            # Solo imágenes
            image_files = []
            for i in range(1, 10):
                media_jpg = os.path.join(game_path, f"media{i}.jpg")
                media_png = os.path.join(game_path, f"media{i}.png")
                media_jpeg = os.path.join(game_path, f"media{i}.jpeg")
                if os.path.exists(media_jpg):
                    image_files.append(media_jpg)
                elif os.path.exists(media_png):
                    image_files.append(media_png)
                elif os.path.exists(media_jpeg):
                    image_files.append(media_jpeg)
            if image_files:
                duracion_por_imagen = duracion_por_juego / len(image_files)
                for image_file in image_files:
                    img_clip = fit_to_canvas(ImageClip(image_file).set_duration(duracion_por_imagen)).volumex(0)
                    clips.append(img_clip)
                    print(Fore.GREEN + f"Agregada imagen {image_file} a la intro.")

    if clips:
        try:
            video_concat = concatenate_videoclips(clips, method="compose")
            # silencio base
            silent_audio = video_concat.audio.set_duration(duracion_audio).volumex(0) if video_concat.audio else None
            video_final = video_concat.set_audio(silent_audio)
            # añadir narración + música
            video_final = video_final.set_audio(combined_audio)
            overlay = make_intro_overlay(metadata_by_folder or {}, video_final.duration)
            if overlay:
                video_final = CompositeVideoClip([video_final, overlay], size=TARGET_RESOLUTION).set_audio(combined_audio)
            print(Fore.GREEN + "Intro created successfully!!.")
            return video_final
        except Exception as e:
            print(Fore.RED + f"Error al crear el video de intro: {e}")
            return None
    else:
        print(Fore.RED + "No se pudieron crear clips para la intro.")
        return None

# ===========================
# Outro
# ===========================
def procesar_outro(carpeta_intro_outro, game_folders, current_dir, metadata_by_folder=None):
    print(Fore.BLUE + "\nProcessing Outro...")
    outro_audio_path = os.path.join(carpeta_intro_outro, 'outro.mp3')
    if not os.path.exists(outro_audio_path):
        print(Fore.RED + f"No se encontró el archivo de audio para la outro: {outro_audio_path}")
        return None

    try:
        narration_clip = AudioFileClip(outro_audio_path).volumex(NARRATION_VOLUME)
        duracion_audio = narration_clip.duration
        print(Fore.GREEN + f"Outro audio duration: {duracion_audio:.2f} s")
    except Exception as e:
        print(Fore.RED + f"Error al cargar el audio de la outro: {e}")
        return None

    music_path = os.path.join(os.getcwd(), 'music', MUSIC_FILE)
    if not os.path.exists(music_path):
        print(Fore.RED + f"No se encontró el archivo de música: {music_path}")
        return None

    try:
        music_clip = AudioFileClip(music_path)
        if music_clip.duration > MUSIC_START_TIME:
            music_clip = music_clip.subclip(MUSIC_START_TIME)
        else:
            print(Fore.RED + "La música es más corta que el tiempo de inicio especificado.")
            return None
        music_clip = music_clip.set_duration(duracion_audio).volumex(MUSIC_VOLUME)
        music_clip = music_clip.audio_fadein(MUSIC_FADE_DURATION).audio_fadeout(MUSIC_FADE_DURATION)
        combined_audio = CompositeAudioClip([narration_clip, music_clip])
    except Exception as e:
        print(Fore.RED + f"Error al procesar la música: {e}")
        return None

    num_games = len(game_folders)
    duracion_por_juego = duracion_audio / max(num_games, 1)

    clips = []
    random.shuffle(game_folders)

    for game_folder in game_folders:
        game_path = os.path.join(current_dir, game_folder)
        mp4_files = []
        for i in reversed(range(1, 10)):
            media_mp4 = os.path.join(game_path, f"media{i}.mp4")
            if os.path.exists(media_mp4):
                mp4_files.append(media_mp4)

        if mp4_files:
            mp4_file = mp4_files[0]
            print(Fore.BLUE + f"Using video {mp4_file} in outro")
            try:
                base = VideoFileClip(mp4_file).without_audio()
                start_time = base.duration * OUTRO_FRAGMENT_START
                end_time = base.duration
                clip_duration = end_time - start_time
                if clip_duration >= duracion_por_juego:
                    sub = base.subclip(start_time, start_time + duracion_por_juego)
                    clip = fit_to_canvas(sub).volumex(VIDEO_VOLUME)
                    clips.append(clip)
                    print(Fore.GREEN + f"Adding clip {mp4_file} to outro.")
                else:
                    print(Fore.YELLOW + f"El video {mp4_file} es corto para la outro.")
                    # Fallback a imágenes
                    image_files = []
                    for i in range(1, 10):
                        media_jpg = os.path.join(game_path, f"media{i}.jpg")
                        media_png = os.path.join(game_path, f"media{i}.png")
                        media_jpeg = os.path.join(game_path, f"media{i}.jpeg")
                        if os.path.exists(media_jpg):
                            image_files.append(media_jpg)
                        elif os.path.exists(media_png):
                            image_files.append(media_png)
                        elif os.path.exists(media_jpeg):
                            image_files.append(media_jpeg)
                    if image_files:
                        duracion_por_imagen = duracion_por_juego / len(image_files)
                        for image_file in image_files:
                            img_clip = fit_to_canvas(ImageClip(image_file).set_duration(duracion_por_imagen)).volumex(0)
                            clips.append(img_clip)
                            print(Fore.GREEN + f"Agregada imagen {image_file} a la outro.")
            except Exception as e:
                print(Fore.RED + f"Error al procesar el archivo {mp4_file}: {e}")
                continue
        else:
            # Solo imágenes
            image_files = []
            for i in range(1, 10):
                media_jpg = os.path.join(game_path, f"media{i}.jpg")
                media_png = os.path.join(game_path, f"media{i}.png")
                media_jpeg = os.path.join(game_path, f"media{i}.jpeg")
                if os.path.exists(media_jpg):
                    image_files.append(media_jpg)
                elif os.path.exists(media_png):
                    image_files.append(media_png)
                elif os.path.exists(media_jpeg):
                    image_files.append(media_jpeg)
            if image_files:
                duracion_por_imagen = duracion_por_juego / len(image_files)
                for image_file in image_files:
                    img_clip = fit_to_canvas(ImageClip(image_file).set_duration(duracion_por_imagen)).volumex(0)
                    clips.append(img_clip)
                    print(Fore.GREEN + f"Agregada imagen {image_file} a la outro.")

    if clips:
        try:
            video_concat = concatenate_videoclips(clips, method="compose")
            silent_audio = video_concat.audio.set_duration(duracion_audio).volumex(0) if video_concat.audio else None
            video_final = video_concat.set_audio(silent_audio)
            video_final = video_final.set_audio(combined_audio)
            overlay = make_outro_overlay(metadata_by_folder or {}, video_final.duration)
            if overlay:
                video_final = CompositeVideoClip([video_final, overlay], size=TARGET_RESOLUTION).set_audio(combined_audio)
            print(Fore.GREEN + "Outro created successfully!.")
            return video_final
        except Exception as e:
            print(Fore.RED + f"Error al crear el video de outro: {e}")
            return None
    else:
        print(Fore.RED + "No se pudieron crear clips para la outro.")
        return None

# ===========================
# Montaje Final
# ===========================
def create_final_video():
    print(Fore.BLUE + "Starting video editing...")
    current_dir = os.path.join(os.getcwd(), 'currentgames')
    if not os.path.exists(current_dir):
        print(Fore.RED + f"No se encontró el directorio 'currentgames' en {os.getcwd()}")
        return

    game_folders = get_inuse_game_folders()
    if not game_folders:
        print(Fore.RED + "No hay juegos para procesar.")
        return
    metadata_by_folder = get_inuse_game_metadata()

    carpeta_intro_outro = os.path.join(current_dir, 'intro_and_outro')
    if not os.path.exists(carpeta_intro_outro):
        print(Fore.RED + f"No se encontró la carpeta 'intro_and_outro' en {current_dir}")
        return

    # Intro
    intro_clip = procesar_intro(carpeta_intro_outro, game_folders, current_dir, metadata_by_folder)

    # Juegos
    game_clips = []
    for game_folder in game_folders:
        game_path = os.path.join(current_dir, game_folder)
        description_audio_path = os.path.join(game_path, 'description.mp3')
        if not os.path.exists(description_audio_path):
            print(Fore.YELLOW + f"No se encontró 'description.mp3' en {game_folder}. Saltando...")
            continue
        print(Fore.BLUE + f"\nProcessing juego: {game_folder}")
        game_clip = procesar_seccion(game_path, description_audio_path, metadata_by_folder.get(game_folder))
        if game_clip:
            game_clips.append(game_clip)

    # Outro
    outro_clip = procesar_outro(carpeta_intro_outro, game_folders, current_dir, metadata_by_folder)

    # Pausa entre secciones
    pause_clip = ColorClip(size=TARGET_RESOLUTION, color=(0, 0, 0), duration=0.5).set_audio(None)

    if intro_clip:
        intro_clip = intro_clip.fadeout(2)
        print(Fore.GREEN + "Fadeout applied in intro.")

    if outro_clip:
        outro_clip = outro_clip.fadein(2)
        print(Fore.GREEN + "Fadein applied outro.")

    final_clips = []
    if intro_clip:
        final_clips.append(intro_clip)
        final_clips.append(pause_clip)
        print(Fore.GREEN + "Intro clip added with pause.")

    for i, game_clip in enumerate(game_clips):
        final_clips.append(game_clip)
        if i < len(game_clips) - 1:
            final_clips.append(pause_clip)
        else:
            if outro_clip:
                final_clips.append(pause_clip)

    if outro_clip:
        final_clips.append(outro_clip)
        print(Fore.GREEN + "Outro clip added to final video.")

    if final_clips:
        print(Fore.BLUE + f"\nTotal clips to concatenate: {len(final_clips)}")
        try:
            print(Fore.BLUE + "\nConcatenating clips...")
            output_path = os.path.join(os.getcwd(), OUTPUT_FILE)
            final_video = concatenate_videoclips(final_clips, method=CONCAT_METHOD)
            print(Fore.BLUE + f"Exporting final video: {output_path}")
            final_video.write_videofile(
                output_path,
                fps=OUTPUT_FPS,
                codec="libx264",
                audio_codec="aac",
                threads=OUTPUT_THREADS,
                bitrate=OUTPUT_BITRATE,
                preset=OUTPUT_PRESET
            )
            final_video.close()
            print(Fore.GREEN + "Video generated!.")
        except Exception as e:
            print(Fore.RED + f"Error al concatenar los clips finales: {e}")

# Para ejecutar directo:
# create_final_video()
