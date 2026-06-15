# narratorlocal.py
import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional

LANG = "es"               # idioma para gTTS
DEFAULT_RATE = 0          # -10..10 (SAPI)
DEFAULT_BITRATE = "192k"  # ffmpeg para MP3

def log(msg: str):
    print(f"[NarratorLocal] {msg}", flush=True)

def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None

def _tts_with_gtts(text: str, out_mp3_path: Path) -> Path:
    """Genera MP3 con gTTS (requiere estar en este intérprete/venv)."""
    from gtts import gTTS
    out_mp3_path.parent.mkdir(parents=True, exist_ok=True)
    tts = gTTS(text=text, lang=LANG)
    tts.save(str(out_mp3_path))
    return out_mp3_path

def _tts_with_windows_sapi_to_wav(text: str, out_wav_path: Path, voice: Optional[str] = None, rate: int = DEFAULT_RATE) -> Path:
    """
    Genera WAV usando el motor de Windows via PowerShell (.NET System.Speech).
    No requiere instalar paquetes de Python.
    """
    out_wav_path.parent.mkdir(parents=True, exist_ok=True)
    ps_text = text.replace('"', '`"')
    ps_script = f"""
Add-Type -AssemblyName System.Speech
$spk = New-Object System.Speech.Synthesis.SpeechSynthesizer
$spk.Rate = {rate}
"""
    if voice:
        ps_script += f'$spk.SelectVoice("{voice}")\n'
    ps_script += f'$spk.SetOutputToWaveFile("{str(out_wav_path)}")\n'
    ps_script += f'$spk.Speak("{ps_text}")\n'
    ps_script += '$spk.Dispose()\n'

    cp = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if cp.returncode != 0:
        raise RuntimeError(f"SAPI TTS error: {cp.stderr.strip()}")
    return out_wav_path

def _convert_wav_to_mp3(in_wav: Path, out_mp3: Path, bitrate: str = DEFAULT_BITRATE) -> Path:
    cp = subprocess.run(
        ["ffmpeg", "-y", "-i", str(in_wav), "-vn", "-ar", "44100", "-ac", "2", "-b:a", bitrate, str(out_mp3)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if cp.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {cp.stderr.splitlines()[-1] if cp.stderr else 'unknown'}")
    return out_mp3

def synthesize_to_audio(text: str, out_preferred_path: Path) -> Path:
    """
    Genera audio a partir de texto.
      1) Intenta gTTS -> MP3 (en este mismo intérprete).
      2) Si no hay gTTS, usa SAPI -> WAV; si hay ffmpeg, convierte a MP3.
    Devuelve la ruta final (mp3 o wav).
    """
    log(f"Python en uso: {sys.executable}")

    # 1) gTTS si está disponible en ESTE intérprete
    try:
        from gtts import gTTS  # noqa: F401
        log("Usando gTTS → MP3")
        return _tts_with_gtts(text, out_preferred_path.with_suffix(".mp3"))
    except Exception as e:
        log(f"gTTS no disponible en este intérprete ({type(e).__name__}: {e}). Usaré Windows SAPI (WAV).")

    # 2) SAPI -> WAV
    wav_path = out_preferred_path.with_suffix(".wav")
    out_wav = _tts_with_windows_sapi_to_wav(text, wav_path)
    log(f"WAV generado con SAPI: {out_wav}")

    # Convertir a MP3 si hay ffmpeg
    if _has_ffmpeg():
        try:
            mp3_path = out_preferred_path.with_suffix(".mp3")
            _convert_wav_to_mp3(out_wav, mp3_path)
            try:
                os.remove(out_wav)
            except Exception:
                pass
            log(f"Convertido a MP3 con ffmpeg: {mp3_path}")
            return mp3_path
        except Exception as conv_err:
            log(f"No se pudo convertir a MP3 con ffmpeg ({conv_err}). Me quedo con WAV.")

    return out_wav

# --------- utilidades para tu pipeline (lee .txt y genera audio) ---------
def _read_text_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="ignore").strip()

def narrate_all(currentgames_dir: Path) -> None:
    """
    Busca:
      - currentgames/intro_and_outro/intro.txt  -> intro.(mp3|wav)
      - currentgames/intro_and_outro/outro.txt  -> outro.(mp3|wav)
      - currentgames/<juego>/description.txt    -> description.(mp3|wav)
    """
    base = Path(currentgames_dir)
    log(f"Inicio narración en: {base}")

    # Intro
    intro_txt = base / "intro_and_outro" / "intro.txt"
    txt = _read_text_file(intro_txt)
    if txt:
        out = synthesize_to_audio(txt, intro_txt.with_name("intro"))
        log(f"Intro generada: {out}")
    else:
        log("Intro: no se encontró intro.txt o estaba vacío.")

    # Juegos
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name == "intro_and_outro":
            continue
        desc_txt = child / "description.txt"
        txt = _read_text_file(desc_txt)
        if txt:
            out = synthesize_to_audio(txt, child / "description")
            log(f"Descripción generada para '{child.name}': {out}")
        else:
            log(f"'{child.name}': sin description.txt (o vacío).")

    # Outro
    outro_txt = base / "intro_and_outro" / "outro.txt"
    txt = _read_text_file(outro_txt)
    if txt:
        out = synthesize_to_audio(txt, outro_txt.with_name("outro"))
        log(f"Outro generada: {out}")
    else:
        log("Outro: no se encontró outro.txt o estaba vacío.")

    log("Narración finalizada.")

# --------- COMPATIBILIDAD: nombre que espera tu orquestador ---------
def narrate_locally(currentgames_dir: Optional[str] = None) -> None:
    """
    Wrapper de compatibilidad: tu main probablemente importaba `narrate_locally`.
    Llama a `narrate_all(...)`. Si no pasas ruta, usa ./currentgames.
    """
    base = Path(currentgames_dir) if currentgames_dir else (Path(os.getcwd()) / "currentgames")
    log(f"narrate_locally() → usando carpeta: {base}")
    narrate_all(base)

# --------- CLI opcional ---------
def _main_cli():
    here = Path(os.getcwd())
    currentgames = here / "currentgames"
    if len(sys.argv) >= 2:
        currentgames = Path(sys.argv[1])
    narrate_all(currentgames)

if __name__ == "__main__":
    _main_cli()
