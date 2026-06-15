import sqlite3
import requests
from colorama import init, Fore
import os
import datetime
import time  # Importar el mÃ³dulo time para las pausas

def calculate_game_scores(start_date_str, end_date_str, ngames, max_games=None):
    init(autoreset=True)

    # Convertir las fechas de cadena a objetos datetime.date
    try:
        start_date = datetime.datetime.strptime(start_date_str, '%d %b %Y').date()
        end_date = datetime.datetime.strptime(end_date_str, '%d %b %Y').date()
        print(Fore.CYAN + f"Rango de fechas: {start_date} a {end_date}")
    except ValueError as ve:
        print(Fore.RED + f"Error al parsear las fechas: {ve}")
        return

    def create_gamestats_table(conn):
        """Crea la tabla 'gamestats' si no existe."""
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS gamestats (
            name TEXT PRIMARY KEY,
            reviewcount INTEGER,
            reviewvalue REAL,
            twitchviewers INTEGER,
            popular TEXT,
            score REAL
        )
        ''')
        conn.commit()
        print(Fore.GREEN + "Tabla 'gamestats' verificada o creada exitosamente.")

    def get_games_data(conn):
        """Obtiene los datos 'name', 'reviewcount' y 'reviewvalue' de la tabla 'games' dentro del rango de fechas."""
        cursor = conn.cursor()
        query = '''
            SELECT name, 
                   COALESCE(reviewcount, 0) as reviewcount, 
                   COALESCE(reviewvalue, 0.0) as reviewvalue 
            FROM games
            WHERE release_date BETWEEN ? AND ?
              AND COALESCE(media1, '') <> ''
            ORDER BY CAST(COALESCE(reviewcount, 0) AS INTEGER) DESC
        '''
        params = [start_date_str.upper(), end_date_str.upper()]
        if max_games is not None:
            query += " LIMIT ?"
            params.append(max_games)
        cursor.execute(query, params)
        games = cursor.fetchall()
        print(Fore.GREEN + f"Consulta 'get_games_data' ejecutada. NÃºmero de juegos obtenidos: {len(games)}")
        return games

    def get_twitch_viewers(game_name, access_token, client_id):
        """Obtiene el nÃºmero total de espectadores en Twitch para un juego dado."""
        headers = {
            'Client-ID': client_id,
            'Authorization': f'Bearer {access_token}'
        }
        # Buscar el ID del juego en Twitch
        search_url = 'https://api.twitch.tv/helix/games'
        params = {'name': game_name}
        try:
            response = requests.get(search_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json().get('data')
            print(Fore.MAGENTA + f"Respuesta de bÃºsqueda de juego en Twitch para '{game_name}': {data}")
        except requests.exceptions.RequestException as e:
            print(Fore.RED + f"Error al buscar el juego '{game_name}' en Twitch: {e}")
            return 0

        if not data:
            print(Fore.YELLOW + f"El juego '{game_name}' no fue encontrado en Twitch.")
            return 0

        game_id = data[0]['id']
        print(Fore.BLUE + f"ID de Twitch para '{game_name}': {game_id}")

        # Obtener transmisiones en vivo relacionadas con el juego
        streams_url = 'https://api.twitch.tv/helix/streams'
        params = {'game_id': game_id}
        try:
            response = requests.get(streams_url, headers=headers, params=params)
            response.raise_for_status()
            stream_data = response.json().get('data', [])
            print(Fore.MAGENTA + f"Datos de streams para '{game_name}': {stream_data}")
        except requests.exceptions.RequestException as e:
            print(Fore.RED + f"Error al obtener streams para '{game_name}': {e}")
            return 0

        total_viewers = sum([stream['viewer_count'] for stream in stream_data])
        print(Fore.BLUE + f"Total de espectadores en Twitch para '{game_name}': {total_viewers}")
        return total_viewers

    def get_access_token(client_id, client_secret):
        """Obtiene un token de acceso de Twitch API."""
        url = 'https://id.twitch.tv/oauth2/token'
        params = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'client_credentials'
        }
        try:
            response = requests.post(url, params=params)
            response.raise_for_status()
            access_token = response.json().get('access_token')
            print(Fore.GREEN + "Token de acceso de Twitch obtenido exitosamente.")
            return access_token
        except requests.exceptions.RequestException as e:
            print(Fore.RED + f"Error al obtener el token de acceso de Twitch: {e}")
            return None

    def is_popular_game(conn, game_name):
        """Verifica si un juego estÃ¡ en la tabla 'popularupcoming'."""
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM popularupcoming WHERE name = ?', (game_name,))
        result = cursor.fetchone()
        print(Fore.BLUE + f"VerificaciÃ³n de popularidad para '{game_name}': {'SÃ­' if result else 'No'}")
        return result is not None

    def calculate_score(reviewcount, reviewvalue, twitchviewers, is_popular):
        """Calcula el puntaje segÃºn las reglas proporcionadas."""
        print(Fore.CYAN + f"Calculando puntaje con reviewcount={reviewcount}, reviewvalue={reviewvalue}, twitchviewers={twitchviewers}, is_popular={is_popular}")
        try:
            reviewvalue = float(reviewvalue)
        except (ValueError, TypeError) as e:
            print(Fore.YELLOW + f"Advertencia: 'reviewvalue' no se pudo convertir a float para reviewvalue='{reviewvalue}'. Se ha establecido a 0.0.")
            reviewvalue = 0.0

        base_score = reviewcount * 10 * (reviewvalue * 0.125) + reviewcount
        print(Fore.CYAN + f"Base score calculado: {base_score}")
        total_score = base_score + twitchviewers
        print(Fore.CYAN + f"Total score antes de popularidad: {total_score}")
        if is_popular:
            total_score += 1000
            print(Fore.CYAN + "Agregado 1000 al puntaje por popularidad.")
        print(Fore.CYAN + f"Puntaje total: {total_score}")
        return total_score

    def insert_or_update_gamestats(conn, game_stats):
        """Inserta o actualiza los datos en la tabla 'gamestats'."""
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO gamestats (name, reviewcount, reviewvalue, twitchviewers, popular, score)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                reviewcount=excluded.reviewcount,
                reviewvalue=excluded.reviewvalue,
                twitchviewers=excluded.twitchviewers,
                popular=excluded.popular,
                score=excluded.score
            ''', (
                game_stats['name'],
                game_stats['reviewcount'],
                game_stats['reviewvalue'],
                game_stats['twitchviewers'],
                game_stats['popular'],
                game_stats['score']
            ))
            conn.commit()
            print(Fore.GREEN + f"Juego '{game_stats['name']}' insertado o actualizado en 'gamestats'.")
        except sqlite3.Error as e:
            print(Fore.RED + f"Error al insertar/actualizar el juego '{game_stats['name']}': {e}")

    # Obtener credenciales de Twitch de variables de entorno o directamente (no recomendado)
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print(Fore.RED + "Error: Las credenciales de Twitch no estÃ¡n configuradas. Establece las variables de entorno 'TWITCH_CLIENT_ID' y 'TWITCH_CLIENT_SECRET'.")
        return

    # Obtener el token de acceso
    access_token = get_access_token(client_id, client_secret)
    if not access_token:
        return

    # Conectar a la base de datos
    try:
        conn = sqlite3.connect('SR_BBDD.db')
        print(Fore.GREEN + "ConexiÃ³n a la base de datos 'SR_BBDD.db' establecida exitosamente.")
    except sqlite3.Error as e:
        print(Fore.RED + f"Error al conectar a la base de datos: {e}")
        return

    # Crear la tabla 'gamestats' si no existe
    create_gamestats_table(conn)

    # Obtener los datos de los juegos dentro del rango de fechas
    games = get_games_data(conn)
    print(Fore.GREEN + f"Se encontraron {len(games)} juegos en la tabla 'games' dentro del rango de fechas.")

    for idx, game in enumerate(games, start=1):
        name, reviewcount, reviewvalue = game
        print(Fore.BLUE + f"\n[{idx}/{len(games)}] Procesando juego: {name}")
        print(Fore.YELLOW + f"Datos obtenidos - reviewcount: {reviewcount}, reviewvalue: {reviewvalue}")

        # Obtener espectadores de Twitch
        twitchviewers = get_twitch_viewers(name, access_token, client_id)
        print(Fore.BLUE + f"Espectadores en Twitch para '{name}': {twitchviewers}")

        # Verificar si el juego es popular
        popular = 'yes' if is_popular_game(conn, name) else 'no'
        print(Fore.BLUE + f"El juego '{name}' es popular: {popular}")

        # Calcular el puntaje
        score = calculate_score(reviewcount, reviewvalue, twitchviewers, popular == 'yes')
        print(Fore.BLUE + f"Puntaje calculado para '{name}': {score}")

        # Preparar los datos para insertar/actualizar
        game_stats = {
            'name': name,
            'reviewcount': reviewcount,
            'reviewvalue': reviewvalue,
            'twitchviewers': twitchviewers,
            'popular': popular,
            'score': score
        }

        # Insertar o actualizar en la tabla 'gamestats'
        insert_or_update_gamestats(conn, game_stats)

        # Pausa de 0.25 segundos entre juegos
        time.sleep(0.25)

    # DespuÃ©s de procesar todos los juegos, seleccionar los top ngames
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM gamestats
            WHERE name IN (
                SELECT name FROM games
                WHERE release_date BETWEEN ? AND ?
                  AND COALESCE(media1, '') <> ''
            )
            ORDER BY score DESC LIMIT ?
        """, (start_date_str.upper(), end_date_str.upper(), ngames))
        top_games = cursor.fetchall()
        print(Fore.GREEN + f"Top {ngames} juegos seleccionados basado en el puntaje.")
    except sqlite3.Error as e:
        print(Fore.RED + f"Error al seleccionar los top juegos: {e}")
        top_games = []

    # Crear la tabla 'inusegames' si no existe
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS inusegames (
            name TEXT PRIMARY KEY,
            position INTEGER
        )
        """)
        conn.commit()
        print(Fore.GREEN + "Tabla 'inusegames' verificada o creada exitosamente.")
    except sqlite3.Error as e:
        print(Fore.RED + f"Error al crear/verificar la tabla 'inusegames': {e}")

    # Limpiar la tabla 'inusegames'
    try:
        cursor.execute("DELETE FROM inusegames")
        conn.commit()
        print(Fore.GREEN + "Tabla 'inusegames' limpiada exitosamente.")
    except sqlite3.Error as e:
        print(Fore.RED + f"Error al limpiar la tabla 'inusegames': {e}")

    # Insertar los top juegos en la tabla 'inusegames'
    for position, (name,) in enumerate(top_games, start=1):
        try:
            cursor.execute("""
            INSERT INTO inusegames (name, position)
            VALUES (?, ?)
            """, (name, position))
            print(Fore.GREEN + f"Juego '{name}' insertado en 'inusegames' con posiciÃ³n {position}.")
        except sqlite3.Error as e:
            print(Fore.RED + f"Error al insertar '{name}' en 'inusegames': {e}")

    conn.commit()
    print(Fore.GREEN + f"Top {ngames} juegos insertados en la tabla 'inusegames'.")

    # Cerrar la conexiÃ³n a la base de datos
    try:
        conn.close()
        print(Fore.GREEN + "ConexiÃ³n a la base de datos cerrada exitosamente.")
    except sqlite3.Error as e:
        print(Fore.RED + f"Error al cerrar la conexiÃ³n a la base de datos: {e}")

    print(Fore.GREEN + "\nProceso completado.")

if __name__ == '__main__':
    # Ejemplo de uso
    # calculate_game_scores('17 OCT 2024', '18 OCT 2024', 3)
    pass

