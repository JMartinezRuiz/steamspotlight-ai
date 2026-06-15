# folderpreparation.py
import sqlite3
import os
import requests
from colorama import init, Fore
from pathlib import Path
from time import sleep

# --------------------
# Parámetros de red
# --------------------
TIMEOUT = (10, 30)   # (connect, read) en segundos
RETRIES = 2          # reintentos por URL además del primer intento
BACKOFF = 2.0        # segundos entre reintentos
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

def _safe_download(url: str, dest_path: Path) -> bool:
    """Descarga con timeout, reintentos y logs. Devuelve True/False."""
    attempt = 0
    while True:
        attempt += 1
        try:
            print(Fore.CYAN + f"[DL] ({attempt}) {url}")
            with requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True) as r:
                r.raise_for_status()
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)
            print(Fore.GREEN + f"[OK] Guardado: {dest_path}")
            return True
        except requests.Timeout:
            print(Fore.YELLOW + f"[TIMEOUT] {url}")
        except requests.RequestException as e:
            print(Fore.YELLOW + f"[WARN] Fallo descargando {url}: {e}")

        if attempt > (1 + RETRIES):
            print(Fore.RED + f"[SKIP] No se pudo descargar tras {attempt-1} reintentos: {url}")
            return False
        sleep(BACKOFF)

def _detect_ext(media_url: str, response=None) -> str:
    """
    Determina extensión a partir de la URL o del Content-Type.
    """
    url = (media_url or "").lower()

    # 1) Por URL
    if ".mp4" in url:
        return ".mp4"
    if ".webm" in url:
        return ".webm"
    if ".jpeg" in url or ".jpg" in url:
        return ".jpg"
    if ".png" in url:
        return ".png"

    # 2) Por cabecera HTTP (si nos pasan response)
    if response is not None:
        ctype = (response.headers.get("Content-Type") or "").lower()
        if "video/mp4" in ctype:
            return ".mp4"
        if "video/webm" in ctype:
            return ".webm"
        if "image/jpeg" in ctype:
            return ".jpg"
        if "image/png" in ctype:
            return ".png"

    # 3) Fallback
    return ".bin"

def prepare_folders_and_download_media():
    init(autoreset=True)

    # Conectar a la base de datos
    conn = sqlite3.connect('SR_BBDD.db')
    cursor = conn.cursor()

    # Obtener los juegos de la tabla 'inusegames'
    cursor.execute("SELECT name, position FROM inusegames ORDER BY position")
    inuse_games = cursor.fetchall()

    if not inuse_games:
        print(Fore.YELLOW + "No se encontraron juegos en la tabla 'inusegames'.")
        conn.close()
        return

    print(Fore.GREEN + "\nJuegos a procesar:")
    for idx, (name, _) in enumerate(inuse_games, start=1):
        print(Fore.BLUE + f"{idx}. Juego: {name}")

    # Crear carpeta intermedia 'currentgames'
    currentgames_dir = Path(os.getcwd()) / "currentgames"
    currentgames_dir.mkdir(exist_ok=True)

    # Para cada juego, crear carpeta y descargar archivos multimedia
    for name, position in inuse_games:
        # Carpeta sanitizada
        folder_name = "".join([c for c in name if c not in '<>:"/\\|?*'])
        game_folder = currentgames_dir / folder_name
        game_folder.mkdir(parents=True, exist_ok=True)

        print(Fore.MAGENTA + f"\n[JUEGO] {position}. {name}")
        print(Fore.BLUE + f"Carpeta: {game_folder}")

        # === IMPORTANTE: usamos el esquema original (tabla 'games' con media1..media9) ===
        try:
            cursor.execute(
                "SELECT media1, media2, media3, media4, media5, media6, media7, media8, media9 "
                "FROM games WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
        except Exception as e:
            print(Fore.RED + f"[DB] Error leyendo columnas mediaX de 'games' para '{name}': {e}")
            row = None

        if not row:
            print(Fore.YELLOW + f"No se encontraron medios para el juego '{name}'")
            continue

        media_urls = [u for u in row if u]  # filtra None/''

        if not media_urls:
            print(Fore.YELLOW + f"No se encontraron URLs de medios para el juego '{name}'.")
            continue

        # Descarga cada archivo multimedia como media1..media9
        saved = 0
        for idx, media_url in enumerate(media_urls, start=1):
            if saved >= 9:
                break

            # Si ya existe un mediaX.* skip
            existing = list(game_folder.glob(f"media{idx}.*"))
            if existing:
                print(Fore.GREEN + f"[SKIP] Ya existe {existing[0].name}")
                saved += 1
                continue

            # Detectar extensión por URL primero
            ext = _detect_ext(media_url)

            # Descarga con reintentos
            attempt = 0
            ok = False
            while attempt <= RETRIES and not ok:
                attempt += 1
                try:
                    print(Fore.CYAN + f"[DL] ({attempt}) {media_url}")
                    with requests.get(media_url, headers=HEADERS, timeout=TIMEOUT, stream=True) as r:
                        r.raise_for_status()
                        # Si la URL no traía extensión reconocible, prueba por Content-Type:
                        if ext == ".bin":
                            ext = _detect_ext(media_url, response=r)
                        dest = game_folder / f"media{idx}{ext}"
                        with open(dest, "wb") as f:
                            for chunk in r.iter_content(chunk_size=1024 * 256):
                                if chunk:
                                    f.write(chunk)
                    print(Fore.GREEN + f"[OK] Guardado: {dest.name}")
                    ok = True
                    saved += 1
                except requests.Timeout:
                    print(Fore.YELLOW + f"[TIMEOUT] {media_url}")
                    if attempt <= RETRIES:
                        sleep(BACKOFF)
                except requests.RequestException as e:
                    print(Fore.YELLOW + f"[WARN] Fallo descargando {media_url}: {e}")
                    if attempt <= RETRIES:
                        sleep(BACKOFF)

        if saved == 0:
            print(Fore.YELLOW + f"[WARN] '{name}': no se descargó ningún fichero.")

    # Cerrar la conexión a la base de datos
    conn.close()

    # Crear carpeta para intro y outro dentro de 'currentgames'
    intro_outro_dir = currentgames_dir / 'intro_and_outro'
    intro_outro_dir.mkdir(parents=True, exist_ok=True)

    print(Fore.GREEN + "\n[READY] Preparación de carpetas y descargas terminada sin bloqueos.")

if __name__ == '__main__':
    # Llamado desde otros scripts; dejar pass para no cambiar tu pipeline.
    pass
