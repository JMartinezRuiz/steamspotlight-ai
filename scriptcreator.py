import sqlite3
import requests
from colorama import init, Fore
import os
import datetime
from datetime import timedelta  # Añadido para usar timedelta
import calendar

def generate_scripts(elevenlabsnarrator, model, intro_prompt_type, games_prompt_type, outro_prompt_type):
    init(autoreset=True)

    # Configurar la clave de API de OpenAI desde una variable de entorno
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        print(Fore.RED + "Error: La clave de API de OpenAI no está configurada. Establece la variable de entorno 'OPENAI_API_KEY'.")
        return

    # Encabezados para las solicitudes a la API de OpenAI
    openai_headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }

    # Conectar a la base de datos
    conn = sqlite3.connect('SR_BBDD.db')
    cursor = conn.cursor()

    # Obtener juegos de la tabla 'inusegames'
    cursor.execute("SELECT name, position FROM inusegames ORDER BY position")
    inuse_games = cursor.fetchall()

    if not inuse_games:
        print(Fore.YELLOW + "No se encontraron juegos en la tabla 'inusegames'.")
        conn.close()
        return

    ngames = len(inuse_games)

    print(Fore.GREEN + "\nGames to process:")
    for position, (name, _) in enumerate(inuse_games, start=1):
        print(Fore.BLUE + f"{position}. game: {name}")

    # Crear carpeta intermedia 'currentgames'
    currentgames_dir = os.path.join(os.getcwd(), 'currentgames')

    # Definir prompts para cada sección y variante
    prompt_templates = {
        'intro': {
            'standard': f"""You are a content writer for YouTube current affairs videos. Create a concise and modern script introduction in English for a video that will present the top {{ngames}} latest game releases on Steam. The introduction should be no longer than 10-20 seconds in read time. Maintain an informative and engaging tone. The script should be formatted exclusively for a narrator without including sound effects or any extraneous elements.""",
            'standard_day': f"""You are a content writer for YouTube current affairs videos. Create a concise and modern script introduction in English for a video that will present the top {{ngames}} latest game releases on Steam. The introduction should be no longer than 10-20 seconds in read time. Maintain an informative and engaging tone, and mention that today is {{weekday}}. The script should be formatted exclusively for a narrator without including sound effects or any extraneous elements.""",
            'toplasweek': """Generate a short, dynamic intro script in English for a YouTube video featuring the latest top games released this week on Steam. The intro should be between 10-20 seconds of read time, with an engaging and informative tone, mentioning that today is {{weekday}}. Format the script specifically for a narrator, excluding any sound effects or extraneous details.""",
            'toplastweek': """Generate a short, dynamic intro script in English for a YouTube video featuring the latest top games released this week on Steam. The intro should be between 10-20 seconds of read time, with an engaging and informative tone, mentioning that today is {{weekday}}. Format the script specifically for a narrator, excluding any sound effects or extraneous details.""",
            'top5month': """You are a content writer for YouTube current affairs videos, develop a brief and captivating script intro in English for a video highlighting the top 3 game releases of the last month on Steam. The intro should last between 10-20 seconds of read time, maintain an exciting yet informative tone, acknowledge that the current month is October.The script should be formatted exclusively for a narrator without including sound effects or any elment which is outside the narration""",
            'variant1': f"""As a skilled content creator for YouTube, craft a brief and engaging intro in English for a video showcasing the top {{ngames}} newest Steam game releases. The intro should last between 10-20 seconds of read time, maintain an informative yet captivating tone, and acknowledge that today is {{currentmonth}}. Ensure the script is tailored for a narrator without incorporating sound effects or unrelated elements.""",
            'variant2': f"""Generate a short, modern intro script in English for a YouTube video featuring the top {{ngames}} latest game releases on Steam. The intro should be between 10-20 seconds of read time, with an engaging and informative tone, mentioning that today is {{weekday}}. Format the script specifically for a narrator, excluding any sound effects or extraneous details."""
        },
        'games': {
            'short': f"""You are a content writer for YouTube current affairs videos. Write an informative, modern, and dynamic script description in English for the game '{{name}}'. Use the following information:

- Short Description: {{short_description}}
- Long Description: {{long_description}}
- Tags: {{tags}}

Identify and mention the game's genre based on the tags. The description should be concise, suitable for a 20 to 30-second read time. Ensure the script is strictly formatted for a narrator without including sound effects or any extraneous elements.""",
            'standard': f"""As a creative content writer for YouTube, compose an engaging and concise script in English for the game '{{name}}'. Utilize the provided details:

- Short Description: {{short_description}}
- Long Description: {{long_description}}
- Tags: {{tags}}

Highlight the game's genre inferred from the tags. The script should be clear and succinct, VERY VERY SHORT fitting a 10 second narration. ensure it's formatted solely for a narrator without adding sound effects or anything that the narrator doesnt need to read.""",
            'variant2': f"""Craft an informative and lively script in English for YouTube, describing the game '{{name}}'. Incorporate the following information:

- Short Description: {{short_description}}
- Long Description: {{long_description}}
- Tags: {{tags}}

Determine and state the game's genre based on its tags and desciption. The script should be brief, ideal for a 15 to 20-second narration. and format it exclusively for a narrator, omitting any sound effects or extraneous elements."""
        },
        'outro': {
            'standard': f"""You are a content writer for YouTube current affairs videos. Write a concise and modern script outro in English for the video, bidding farewell to the audience. Briefly mention the games covered: {{games_list}}. Keep the tone brief and engaging. The script should be strictly formatted for a narrator without including sound effects or any extraneous elements. It should be shorter than 15s in real time.""",
            'variant1': f"""As a proficient content writer for YouTube, develop a short and engaging outro script in English for the video. Bid farewell to the viewers, wish them a happy {{weekday}}, and briefly recap the games discussed: {{games_list}}. Maintain an engaging and concise tone, formatting the script exclusively for a narrator without any sound effects or unrelated content. The outro should be under 15 seconds in real time.""",
            'variant2': f"""Generate a brief and modern outro script in English for YouTube, thanking the audience and wishing them a happy {{weekday}}. Summarize the games featured: {{games_list}}. Ensure the tone is engaging and concise, formatted solely for a narrator without incorporating sound effects or extraneous elements. Keep the duration under 15 seconds in real time."""
        }
    }

    # Mapeo de modelos
    model_mapping = {
        'gpt-4o-mini': 'gpt-4o-mini',
        'gpt-4o': 'gpt-4o'
    }

    selected_model = model_mapping.get(model, 'gpt-4o')

    print(Fore.GREEN + f"Selected model for OpenAI API: {selected_model}")

    # Función para llamar a la API de OpenAI
    def call_openai_api(prompt, headers, max_tokens=5000, model='gpt-4'):
        openai_url = 'https://api.openai.com/v1/chat/completions'
        data = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': 'You are a helpful and creative assistant.'},
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': max_tokens,
            'temperature': 0.7,
        }

        response = requests.post(openai_url, headers=headers, json=data)

        if response.status_code == 200:
            response_data = response.json()
            chat_response = response_data['choices'][0]['message']['content']
            return chat_response
        else:
            print(Fore.RED + f"Error from OpenAI API: {response.status_code}")
            try:
                error_details = response.json()
                print(error_details)
            except ValueError:
                print(response.text)
            return ""

    # Generar introducción
    intro_text = generate_intro(ngames, openai_headers, selected_model, intro_prompt_type, prompt_templates)

    # Guardar introducción en un archivo txt dentro de 'currentgames/intro_and_outro'
    intro_outro_dir = os.path.join(currentgames_dir, 'intro_and_outro')
    os.makedirs(intro_outro_dir, exist_ok=True)
    with open(os.path.join(intro_outro_dir, 'intro.txt'), 'w', encoding='utf-8') as f:
        f.write(intro_text)
    print(Fore.GREEN + "\nIntro saved and generated 'currentgames/intro_and_outro/intro.txt'.")

    # Generar y guardar descripciones de juegos
    for idx, (name, position) in enumerate(inuse_games, start=1):
        # Obtener información del juego de la tabla 'games'
        cursor.execute("SELECT short_description, long_description, tags, price, reviewcount, reviewvalue FROM games WHERE name = ?", (name,))
        result = cursor.fetchone()
        if result:
            short_description, long_description, tags, price, reviewcount, reviewvalue = result
        else:
            print(Fore.YELLOW + f"wasnt able to find info for '{name}', omitiendo.")
            continue

        # Generar descripción usando OpenAI con tipo de prompt seleccionado
        game_text = generate_game_description(idx, ngames, name, short_description, long_description, tags,
                                             price, reviewcount, reviewvalue,
                                             openai_headers, selected_model, games_prompt_type, prompt_templates)

        # Guardar descripción en la carpeta del juego
        folder_name = "".join([c for c in name if c not in '<>:"/\\|?*'])
        game_folder_path = os.path.join(currentgames_dir, folder_name)
        os.makedirs(game_folder_path, exist_ok=True)
        file_path = os.path.join(game_folder_path, 'description.txt')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(game_text)
        print(Fore.GREEN + f"Game description for '{name}' saved '{file_path}'.")

    # Generar outro
    outro_text = generate_outro(ngames, [name for name, _ in inuse_games], openai_headers, selected_model, outro_prompt_type, prompt_templates)

    # Guardar outro en un archivo txt
    with open(os.path.join(intro_outro_dir, 'outro.txt'), 'w', encoding='utf-8') as f:
        f.write(outro_text)
    print(Fore.GREEN + "Outro generated and saved 'currentgames/intro_and_outro/outro.txt'.")

    # Cerrar conexión a la base de datos
    conn.close()
    print(Fore.GREEN + "\nProcess complete.")

def generate_intro(ngames, openai_headers, model, intro_prompt_type, prompt_templates):
    # Obtener el día de la semana
    today = datetime.date.today()
    weekday = today.strftime('%A')
    # Mes actual
    currentmonth = today.strftime('%B')  # Nombre del mes actual, como 'October'

    # Mes anterior
    first_day_of_current_month = today.replace(day=1)
    last_day_of_last_month = first_day_of_current_month - timedelta(days=1)
    lastmonth = last_day_of_last_month.strftime('%B')  # Nombre del mes anterior, como 'September'

    # Seleccionar el prompt basado en el tipo
    intro_prompt_template = prompt_templates['intro'].get(intro_prompt_type, prompt_templates['intro']['standard'])

    # Crear el prompt para la introducción en inglés sin efectos de sonido y con duración limitada
    prompt = intro_prompt_template.format(ngames=ngames, weekday=weekday)

    response = call_openai_api(prompt, openai_headers, max_tokens=150, model=model)

    intro_text = response.strip()
    return intro_text

def generate_game_description(position, total_games, name, short_description, long_description, tags, price, reviewcount, reviewvalue, openai_headers, model, games_prompt_type, prompt_templates):
    # Determinar la posición en texto
    if position == 1:
        position_text = "Firstly,"
    elif position == total_games:
        position_text = "Lastly,"
    else:
        position_text = f"In position number {position},"

    # Seleccionar el prompt basado en el tipo
    games_prompt_template = prompt_templates['games'].get(games_prompt_type, prompt_templates['games']['standard'])

    # Crear el prompt para la descripción del juego en inglés sin efectos de sonido y formato de guion
    prompt = games_prompt_template.format(
        position_text=position_text,
        name=name,
        short_description=short_description,
        long_description=long_description,
        tags=tags
    )
    prompt += (
        f"\n\nRanking context for the narrator:"
        f"\n- Position: #{position} of {total_games}"
        f"\n- Steam price: {price or 'unknown'}"
        f"\n- Steam reviews: {reviewcount or 0}"
        f"\n- Steam rating value: {reviewvalue or 'unknown'}/10"
        "\nMention the position and one concrete metric naturally. "
        "Avoid generic hype, keep it useful, and do not say anything that is not supported by the data."
    )

    response = call_openai_api(prompt, openai_headers, max_tokens=200, model=model)

    game_text = response.strip()
    return game_text

def generate_outro(ngames, game_names, openai_headers, model, outro_prompt_type, prompt_templates):
    # Puedes utilizar los nombres de los juegos para hacer un breve resumen
    games_list = ', '.join(game_names)
    # Obtener el día de la semana
    today = datetime.date.today()
    weekday = today.strftime('%A')

    # Mes actual
    currentmonth = today.strftime('%B')  # Nombre del mes actual, como 'October'

    # Mes anterior
    first_day_of_current_month = today.replace(day=1)
    last_day_of_last_month = first_day_of_current_month - timedelta(days=1)
    lastmonth = last_day_of_last_month.strftime('%B')  # Nombre del mes anterior, como 'September'

    # Seleccionar el prompt basado en el tipo
    outro_prompt_template = prompt_templates['outro'].get(outro_prompt_type, prompt_templates['outro']['standard'])

    # Crear el prompt para el outro en inglés sin efectos de sonido y con formato de guion
    prompt = outro_prompt_template.format(
        weekday=weekday,
        games_list=games_list
    )

    response = call_openai_api(prompt, openai_headers, max_tokens=100, model=model)

    outro_text = response.strip()
    return outro_text

def call_openai_api(prompt, headers, max_tokens=500, model='gpt-4'):
    openai_url = 'https://api.openai.com/v1/chat/completions'
    data = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'You are a helpful and creative assistant.'},
            {'role': 'user', 'content': prompt}
        ],
        'max_tokens': max_tokens,
        'temperature': 0.7,
    }

    response = requests.post(openai_url, headers=headers, json=data)

    if response.status_code == 200:
        response_data = response.json()
        chat_response = response_data['choices'][0]['message']['content']
        return chat_response
    else:
        print(Fore.RED + f"Error from OpenAI API: {response.status_code}")
        try:
            error_details = response.json()
            print(error_details)
        except ValueError:
            print(response.text)
        return ""

if __name__ == '__main__':
    # Ejemplo de uso
    # generate_scripts(False, 'gpt-4o', 'standard', 'standard', 'standard')
    pass
