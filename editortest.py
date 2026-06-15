import os
import sys
import numpy as np
from moviepy.editor import VideoFileClip

# =======================
# CONFIG — AJUSTA AQUÍ
# =======================
INPUT_PATH = "C:\\Users\\Gigabyte\\PycharmProjects\\SteamNewsVideos\\video_final.mp4"            # e.g. r"C:\ruta\video.mp4" | None = toma el primer .mp4 del directorio
OUTPUT_PATH = "blurred_test.mp4"
TEST_DURATION = 5.0          # segundos
FPS = 24
BITRATE = "5000k"

# Fuerza del blur
GAUSSIAN_SIGMA = 12.0        # 8–20 = fuerte; sube si quieres más crema
SAVE_DEBUG_FRAMES = True     # guarda frame_before.jpg / frame_after.jpg

# =======================
# HELPERS
# =======================
def find_first_mp4():
    for f in os.listdir("."):
        if f.lower().endswith(".mp4"):
            return f
    return None

def to_uint8(img):
    """Asegura uint8 en [0,255] para evitar videos negros."""
    if img.dtype == np.uint8:
        return img
    # Soporta floats en [0,1] o [0,255]
    if issubclass(img.dtype.type, np.floating):
        # Si los valores parecen 0..1, escala a 255
        if img.max() <= 1.0:
            img = img * 255.0
        img = np.clip(img, 0, 255)
        return img.astype(np.uint8)
    # Ints de mayor profundidad
    img = np.clip(img, 0, 255)
    return img.astype(np.uint8)

def try_import_skimage():
    try:
        from skimage.filters import gaussian
        return gaussian
    except Exception:
        return None

def try_import_pillow():
    try:
        from PIL import Image, ImageFilter
        return (Image, ImageFilter)
    except Exception:
        return (None, None)

def blur_frame_skimage(image: np.ndarray, sigma: float):
    """
    Blur con scikit-image, cuidando rango/color:
    - preserve_range=True para no normalizar 0..1
    - channel_axis=-1 para RGB
    - devuelve uint8
    """
    from skimage.filters import gaussian
    out = gaussian(image, sigma=sigma, preserve_range=True, channel_axis=-1)
    return to_uint8(out)

def blur_frame_pillow(image: np.ndarray, radius: float):
    """
    Blur con Pillow (GaussianBlur). radius≈sigma.
    Convertimos ida/vuelta y devolvemos uint8.
    """
    from PIL import Image, ImageFilter
    im = Image.fromarray(to_uint8(image))
    im = im.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.array(im, dtype=np.uint8)

def build_blur_function(sigma: float):
    """
    Devuelve una función blur(img)->img_uint8 según lo disponible:
    1) skimage (preferido)
    2) pillow
    3) si nada, levanta error con explicación
    """
    gaussian = try_import_skimage()
    if gaussian is not None:
        def _f(img):
            return blur_frame_skimage(img, sigma)
        print("[INFO] Usando scikit-image gaussian (sigma=%.2f)" % sigma)
        return _f

    Image, ImageFilter = try_import_pillow()
    if Image is not None:
        def _f(img):
            return blur_frame_pillow(img, sigma)
        print("[INFO] Usando Pillow GaussianBlur (radius=%.2f)" % sigma)
        return _f

    def _fail(_img):
        raise RuntimeError(
            "No hay scikit-image ni Pillow disponibles. Instala uno de estos para aplicar blur:\n"
            "  pip install scikit-image\n"
            "  (o) pip install pillow"
        )
    print("[WARN] Ni scikit-image ni Pillow presentes.")
    return _fail

def save_debug_frames(original_clip, blurred_clip, t=0.0):
    try:
        # Preferimos Pillow para guardar; si no, imageio
        try:
            from PIL import Image
            use_pil = True
        except Exception:
            import imageio.v2 as imageio
            use_pil = False

        f_before = original_clip.get_frame(t)
        f_after  = blurred_clip.get_frame(t)
        f_before = to_uint8(f_before)
        f_after  = to_uint8(f_after)

        if use_pil:
            Image.fromarray(f_before).save("frame_before.jpg")
            Image.fromarray(f_after).save("frame_after.jpg")
        else:
            imageio.imwrite("frame_before.jpg", f_before)
            imageio.imwrite("frame_after.jpg", f_after)

        print("[INFO] Guardados: frame_before.jpg / frame_after.jpg")
    except Exception as e:
        print(f"[WARN] No se pudieron guardar frames de debug: {e}")

# =======================
# MAIN
# =======================
def main():
    input_path = INPUT_PATH or find_first_mp4()
    if not input_path or not os.path.exists(input_path):
        print("ERROR: No se encontró un .mp4. Pon la ruta en INPUT_PATH o deja un .mp4 junto al script.")
        sys.exit(1)

    print("=== TEST BLUR POR FRAME ===")
    print(f"Input         : {input_path}")
    print(f"Output        : {OUTPUT_PATH}")
    print(f"Duración test : {TEST_DURATION}s")
    print(f"Sigma         : {GAUSSIAN_SIGMA}")

    clip = VideoFileClip(input_path)
    d = min(TEST_DURATION, clip.duration)
    base = clip.subclip(0, d)

    blur_f = build_blur_function(GAUSSIAN_SIGMA)

    # Aplica blur por frame de forma segura (devuelve uint8)
    blurred = base.fl_image(blur_f)

    # Guarda un par de frames para ver que NO queda negro
    if SAVE_DEBUG_FRAMES:
        save_debug_frames(base, blurred, t=0.0)

    print("[INFO] Exportando…")
    blurred.write_videofile(
        OUTPUT_PATH,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        bitrate=BITRATE
    )
    print("[OK] Listo. Revisa 'blurred_test.mp4' y los frames before/after.")

if __name__ == "__main__":
    main()
