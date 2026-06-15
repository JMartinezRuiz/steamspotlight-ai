import argparse
import sys
import os
from colorama import init, Fore

# Inicializar colorama
init(autoreset=True)


def main():
    # Parsear argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Ejecuta el proyecto de Steam Games')
    parser.add_argument('start_date', help='Fecha de inicio en formato DD MMM YYYY (e.g., 17 OCT 2024)')
    parser.add_argument('end_date', help='Fecha de fin en formato DD MMM YYYY (e.g., 18 OCT 2024)')
    parser.add_argument('ngames', type=int, help='Número de juegos a procesar basado en analíticas')
    parser.add_argument('--elevenlabsnarrator', action='store_true', help='Usar elevenlabs narrator')

    # Nuevos argumentos para scriptcreator
    parser.add_argument('--model', choices=['gpt-4o-mini', 'gpt-4o'], default='gpt-4o',
                        help='Modelo de OpenAI a utilizar (default: gpt-4o)')
    parser.add_argument('--intro_prompt', choices=['standard', 'variant1', 'variant2', 'top5month'], default='standard',
                        help='Tipo de prompt para la intro (default: standard)')
    parser.add_argument('--games_prompt', choices=['standard', 'variant1', 'variant2'], default='standard',
                        help='Tipo de prompt para los games (default: standard)')
    parser.add_argument('--outro_prompt', choices=['standard', 'variant1', 'variant2'], default='standard',
                        help='Tipo de prompt para la outro (default: standard)')

    # NUEVO: límite de juegos a scrapear para debug
    parser.add_argument('--max', dest='max_games', type=int, default=None,
                        help='Máximo de juegos a scrapear (solo para debug).')

    args = parser.parse_args()

    start_date_str = args.start_date
    end_date_str = args.end_date
    ngames = args.ngames
    elevenlabsnarrator = args.elevenlabsnarrator
    model = args.model
    intro_prompt = args.intro_prompt
    games_prompt = args.games_prompt
    outro_prompt = args.outro_prompt
    max_games = args.max_games

    # Mostrar los parámetros
    print(Fore.BLUE + f"Starting Video proyect with following parameters:")
    print(Fore.GREEN + f"Starting scrapping date: {start_date_str}")
    print(Fore.GREEN + f"Ending scrapping date: {end_date_str}")
    print(Fore.GREEN + f"ngames: {ngames}")
    print(Fore.GREEN + f"Eleven Labs Narrator: {elevenlabsnarrator}")
    print(Fore.GREEN + f"OpenAI: {model}")
    print(Fore.GREEN + f"intro prompt: {intro_prompt}")
    print(Fore.GREEN + f"games prompt: {games_prompt}")
    print(Fore.GREEN + f"outro prompt: {outro_prompt}")
    print(Fore.GREEN + f"Max steam games (debug): {max_games if max_games is not None else 'No limit'}")

    # Ejecutar los pasos
    try:
        # Paso 1: Ejecutar el scraper para obtener los juegos dentro del rango de fechas
        from scrapper import scrape_steam
        scrape_steam(start_date_str, end_date_str, max_games=max_games)

        # Paso 2: Extraer detalles de los juegos dentro del rango de fechas
        from scrapper2 import scrape_all_game_details
        scrape_all_game_details(start_date_str, end_date_str, max_games=max_games)

        # Paso 3: Calcular los puntajes de los juegos dentro del rango de fechas
        from analytics import calculate_game_scores
        calculate_game_scores(start_date_str, end_date_str, ngames, max_games=max_games)

        # Paso 4: Preparar carpetas y descargar medios basado en analíticas
        from folderpreparation import prepare_folders_and_download_media
        prepare_folders_and_download_media()

        # Paso 5: Generar guiones basado en analíticas con parámetros adicionales
        from scriptcreator import generate_scripts
        generate_scripts(elevenlabsnarrator, model, intro_prompt, games_prompt, outro_prompt)

        # Paso 6: Ejecutar el narrador
        if elevenlabsnarrator:
            print(Fore.BLUE + "Using Eleven Labs Narrator...")
            from narratoreleven import narrate_with_elevenlabs
            narrate_with_elevenlabs()
        else:
            print(Fore.BLUE + "Using Narrator Local...")
            from narratorlocal import narrate_locally
            narrate_locally()

        # Paso 7: Ejecutar el editor para generar el video final
        from editor import create_final_video
        create_final_video()

        print(Fore.BLUE + "Video has been created")

    except Exception as e:
        print(Fore.RED + f"Ocurrió un error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
