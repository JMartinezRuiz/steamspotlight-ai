import os
import requests
from colorama import init, Fore

def narrate_with_elevenlabs():
    init(autoreset=True)

    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY no esta configurada.")
    if not VOICE_ID:
        raise RuntimeError("ELEVENLABS_VOICE_ID no esta configurada.")

    def generate_audio_from_text(text, output_path):
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
            response.raise_for_status()  # Lanza una excepciÃ³n si la respuesta no es 200
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(Fore.GREEN + f"Archivo de audio generado: '{output_path}'")
        except requests.exceptions.HTTPError as errh:
            print(Fore.RED + f"Error HTTP: {errh}")
        except requests.exceptions.ConnectionError as errc:
            print(Fore.RED + f"Error de conexiÃ³n: {errc}")
        except requests.exceptions.Timeout as errt:
            print(Fore.RED + f"Timeout: {errt}")
        except requests.exceptions.RequestException as err:
            print(Fore.RED + f"Error en la solicitud: {err}")
        except Exception as e:
            print(Fore.RED + f"OcurriÃ³ un error al generar el audio: {e}")

    def process_file(file_path):
        if not os.path.isfile(file_path):
            print(Fore.RED + f"El archivo '{file_path}' no existe.")
            return

        nombre_archivo_audio = os.path.splitext(os.path.basename(file_path))[0] + ".mp3"
        ruta_archivo_audio = os.path.join(os.path.dirname(file_path), nombre_archivo_audio)

        if os.path.exists(ruta_archivo_audio):
            txt_mtime = os.path.getmtime(file_path)
            audio_mtime = os.path.getmtime(ruta_archivo_audio)
            audio_has_content = os.path.getsize(ruta_archivo_audio) > 0
            if audio_has_content and audio_mtime >= txt_mtime:
                print(Fore.YELLOW + f"El archivo de audio '{ruta_archivo_audio}' ya existe y esta actualizado. Omite la generacion.")
                return
            print(Fore.YELLOW + f"El archivo de audio '{ruta_archivo_audio}' esta desactualizado. Regenerando...")

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                texto = file.read()
        except Exception as e:
            print(Fore.RED + f"Error al leer el archivo '{file_path}': {e}")
            return

        if not texto.strip():
            print(Fore.YELLOW + f"El archivo '{file_path}' estÃ¡ vacÃ­o. Omite la generaciÃ³n de audio.")
            return

        generate_audio_from_text(texto, ruta_archivo_audio)

    def main():
        base_directory = os.path.join(os.getcwd(), 'currentgames')
        print(Fore.BLUE + f"Ruta base establecida en: '{base_directory}'")

        archivos_objetivo = ['intro.txt', 'outro.txt', 'description.txt']

        for root, dirs, files in os.walk(base_directory):
            for archivo in archivos_objetivo:
                if archivo in files:
                    ruta_archivo = os.path.join(root, archivo)
                    print(Fore.BLUE + f"\nProcesando archivo: '{ruta_archivo}'")
                    process_file(ruta_archivo)

        print(Fore.GREEN + "\nTodos los archivos de audio han sido generados.")

    main()

# Si deseas que el script se pueda ejecutar directamente
if __name__ == '__main__':
    narrate_with_elevenlabs()

