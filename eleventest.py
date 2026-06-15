import os
import requests
from pydub import AudioSegment

def test_elevenlabs_api():
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY no esta configurada.")
    if not VOICE_ID:
        raise RuntimeError("ELEVENLABS_VOICE_ID no esta configurada.")

    text = "This is a test text to verify audio generation with ElevenLabs"

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        # Guardar el audio original
        with open('test_output.mp3', 'wb') as f:
            f.write(response.content)
        print("Archivo de audio 'test_output.mp3' generado exitosamente.")

        # Aumentar el volumen en aproximadamente un 25%
        increase_volume('test_output.mp3', 'test_output_louder.mp3', 2)  # Incremento de 2 dB
        print("Archivo de audio 'test_output_louder.mp3' con volumen aumentado generado exitosamente.")
    except requests.exceptions.HTTPError as errh:
        print(f"Error HTTP: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error de conexiÃ³n: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"Error en la solicitud: {err}")
    except Exception as e:
        print(f"OcurriÃ³ un error al generar el audio: {e}")

def increase_volume(input_file, output_file, increase_db):
    try:
        sound = AudioSegment.from_file(input_file)
        louder_sound = sound + increase_db  # Aumentar el volumen
        louder_sound.export(output_file, format='mp3')
    except Exception as e:
        print(f"Error al aumentar el volumen: {e}")

if __name__ == '__main__':
    test_elevenlabs_api()

