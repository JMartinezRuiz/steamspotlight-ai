# scrapper.py

import sqlite3
from selenium import webdriver
from selenium.webdriver.common.by import By
from datetime import datetime
from colorama import init, Fore
import time

def scrape_steam(start_date_str, end_date_str, max_games=None):
    """
    Scrapea la lista de juegos de Steam entre fechas.
    Si max_games está definido, se limita el número de INSERTs en la tabla 'games' a ese máximo.
    """
    init(autoreset=True)

    # Convertir las fechas de cadena a objetos datetime.date
    try:
        start_date = datetime.strptime(start_date_str, '%d %b %Y').date()
        end_date = datetime.strptime(end_date_str, '%d %b %Y').date()
    except ValueError as ve:
        print(Fore.RED + f"Error al parsear las fechas: {ve}")
        return

    # Conectar o crear la base de datos
    conn = sqlite3.connect('SR_BBDD.db')
    cursor = conn.cursor()

    # Crear la tabla 'games' si no existe
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        release_date TEXT,
        url TEXT,
        price TEXT
    )
    ''')
    conn.commit()
    print(Fore.GREEN + "Tabla 'games' verificada o creada exitosamente.")

    # Configurar Selenium WebDriver (Chrome)
    driver = webdriver.Chrome()

    # Construir la URL de Steam con filtros
    base_url = 'https://store.steampowered.com/search/'
    params = {
        'sort_by': 'Released_DESC',
        'supportedlang': 'spanish,english',
        'category1': '998',  # Juegos para PC
        'os': 'win',
        'ndl': '1'
    }

    # Función para construir la URL con parámetros
    def build_url(page):
        url = f"{base_url}?page={page}"
        for key, value in params.items():
            url += f"&{key}={value}"
        return url

    # Definir un mapeo de meses abreviados en inglés y español
    months = {
        'JAN': 1, 'ENE': 1,
        'FEB': 2, 'FEB.': 2,
        'MAR': 3,
        'ABR': 4, 'APR': 4,
        'MAY': 5, 'MAY.': 5,
        'JUN': 6,
        'JUL': 7,
        'AGO': 8, 'AUG': 8,
        'SEP': 9,
        'OCT': 10,
        'NOV': 11,
        'DIC': 12, 'DEC': 12
    }

    # Función para verificar si el juego ya existe en la base de datos
    def game_exists(name):
        cursor.execute('SELECT COUNT(1) FROM games WHERE name = ?', (name,))
        return cursor.fetchone()[0] > 0

    # Variables para la paginación y el conteo
    current_page = 1
    games_scraped = 0
    max_pages = 100  # Puedes ajustar este límite según tus necesidades

    # Agregar una bandera para detener el scraping
    stop_scraping = False

    while current_page <= max_pages and not stop_scraping:
        url = build_url(current_page)
        print(Fore.BLUE + f"Opening {current_page} Steam page...")
        driver.get(url)
        time.sleep(2)  # Esperar a que la página cargue completamente

        # Obtener todos los elementos de los juegos en la página
        print(Fore.BLUE + "Shearing games...")
        game_elements = driver.find_elements(By.CLASS_NAME, 'search_result_row')

        # Si no se encuentran juegos, terminar el scraping
        if not game_elements:
            print(Fore.RED + "Not more games, finishing scraping.")
            break
        else:
            print(Fore.GREEN + f"S{len(game_elements)} finded games in page {current_page}.")

        # Recorrer cada juego y extraer la información
        for game in game_elements:
            # Si ya alcanzamos el máximo, cortamos
            if max_games is not None and games_scraped >= max_games:
                print(Fore.GREEN + f"Max games ({max_games}) reached. Stopping early.")
                stop_scraping = True
                break

            # Extraer el nombre del juego
            try:
                name = game.find_element(By.CLASS_NAME, 'title').text
                print(Fore.BLUE + f"Game located: {name}")
            except Exception as e:
                print(Fore.RED + f"Error locating game: {e}")
                continue

            # Extraer la fecha de lanzamiento y limpiar la coma extra si la tiene
            try:
                release_date_text = game.find_element(By.CLASS_NAME, 'search_released').text.strip().upper().replace(',', '')
                print(Fore.BLUE + f"Release date extracted: {release_date_text}")
            except Exception as e:
                print(Fore.RED + f"Error with date: {e}")
                continue

            # Intentar parsear la fecha de lanzamiento
            try:
                if not release_date_text or release_date_text in ['PRÓXIMAMENTE', 'COMING SOON']:
                    print(Fore.YELLOW + f"Juego {name} no tiene fecha válida dentro del rango, saltando...")
                    continue

                # Dividir la fecha en partes
                date_parts = release_date_text.split(' ')

                if len(date_parts) == 3:
                    # Formato '15 OCT 2024'
                    day = int(date_parts[0])
                    month_str = date_parts[1]
                    year = int(date_parts[2])
                elif len(date_parts) == 2:
                    # Formato '15 OCT' (asumimos el año actual)
                    day = int(date_parts[0])
                    month_str = date_parts[1]
                    year = datetime.now().year
                else:
                    print(Fore.YELLOW + f"Format unknow {name}, saltando...")
                    continue

                month = months.get(month_str, 0)
                if month == 0:
                    print(Fore.YELLOW + f"Mes desconocido '{month_str}' para el juego {name}, saltando...")
                    continue

                release_date = datetime(year, month, day).date()

            except Exception as e:
                print(Fore.RED + f"Error with date parsing{name}: {e}")
                continue

            # **Nuevo código original** detener si encontramos fechas anteriores al inicio
            if release_date < start_date:
                print(Fore.YELLOW + f"Game {name} release in the starting date {start_date}. Finishing.")
                stop_scraping = True
                break  # Salir del bucle de juegos

            # Comprobar si la fecha de lanzamiento está dentro del rango
            if start_date <= release_date <= end_date:
                print(Fore.GREEN + f"Game {name} released between {start_date} and {end_date}. procesing...")

                # Verificar si el juego ya existe en la base de datos
                if game_exists(name):
                    print(Fore.YELLOW + f"game {name} already in DB..")
                    games_scraped += 1
                    if max_games is not None and games_scraped >= max_games:
                        print(Fore.GREEN + f"Max games ({max_games}) reached. Stopping early.")
                        stop_scraping = True
                        break
                    continue

                # Extraer la URL del juego
                try:
                    url = game.get_attribute('href')
                    print(Fore.BLUE + f"URL extracted: {url}")
                except Exception as e:
                    print(Fore.RED + f"Error al extraer la URL del juego {name}: {e}")
                    continue

                # Extraer el precio del juego (maneja gratuito)
                try:
                    price_element = game.find_element(By.CLASS_NAME, 'search_price')
                    price = price_element.text.strip()
                except Exception:
                    try:
                        price_element = game.find_element(By.CLASS_NAME, 'discount_final_price')
                        price = price_element.text.strip()
                    except Exception as e:
                        print(Fore.YELLOW + f"Error al extraer el precio del juego {name}: {e}. Asumiendo que el juego es gratuito.")
                        price = '0'

                print(Fore.BLUE + f"Precio extraído: {price}")

                # Insertar los datos en la base de datos
                try:
                    cursor.execute('''
                        INSERT INTO games (name, release_date, url, price)
                        VALUES (?, ?, ?, ?)
                    ''', (name, release_date_text, url, price))
                    conn.commit()
                    games_scraped += 1
                    print(Fore.GREEN + f"Juego {name} insertado en la base de datos. [{games_scraped}{'/' + str(max_games) if max_games else ''}]")

                    # Si alcanzamos el máximo, detenemos
                    if max_games is not None and games_scraped >= max_games:
                        print(Fore.GREEN + f"Max games ({max_games}) reached. Stopping early.")
                        stop_scraping = True
                        break
                except Exception as e:
                    print(Fore.RED + f"Error al insertar el juego {name} en la base de datos: {e}")

            else:
                print(Fore.YELLOW + f"El juego {name} fue lanzado fuera del rango {start_date} - {end_date}, saltando...")

        # **Salir del bucle de páginas si stop_scraping es True**
        if stop_scraping:
            break  # Salir del bucle de páginas

        # Incrementar la página y continuar
        current_page += 1

    # Confirmar los cambios y cerrar las conexiones
    conn.commit()
    conn.close()
    print(Fore.GREEN + "Data saved in BD!.")

    driver.quit()
    print(Fore.GREEN + "Scrapper-1 finished OK.")

if __name__ == '__main__':
    # Ejemplo de uso
    # scrape_steam('17 OCT 2024', '18 OCT 2024', max_games=5)
    pass
