import sqlite3
from selenium import webdriver
from selenium.webdriver.common.by import By
from datetime import datetime
from colorama import init, Fore
import time
import argparse
import sys

def main(target_date_str, max_pages=100):
    init(autoreset=True)

    # Convertir la fecha objetivo de cadena a objeto datetime.date
    try:
        target_date = datetime.strptime(target_date_str, '%d %b %Y').date()
    except ValueError as ve:
        print(Fore.RED + f"Error al parsear la fecha objetivo: {ve}")
        sys.exit(1)

    # Conectar o crear la base de datos
    conn = sqlite3.connect('SR_BBDD.db')
    cursor = conn.cursor()

    # Crear la tabla 'popularupcoming' si no existe, con 'name' único para evitar duplicados
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS popularupcoming (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        release_date TEXT NOT NULL
    )
    ''')

    # Confirmar cambios
    conn.commit()
    print(Fore.GREEN + "Tabla 'popularupcoming' verificada o creada exitosamente.")

    # Configurar Selenium WebDriver (Chrome)
    driver = webdriver.Chrome()

    # Inicializar variables de paginación
    current_page = 1
    stop_scraping = False

    while current_page <= max_pages and not stop_scraping:
        # Construir la URL de Steam con filtros y paginación
        base_url = 'https://store.steampowered.com/search/'
        params = {
            'sort_by': 'Released_DESC',
            'supportedlang': 'english,spanish',
            'category1': '998',  # Juegos para PC
            'os': 'win',
            'filter': 'popularnew',
            'ndl': '1',
            'page': str(current_page)
        }
        url = f"{base_url}?sort_by={params['sort_by']}&supportedlang={params['supportedlang']}&category1={params['category1']}&os={params['os']}&filter={params['filter']}&ndl={params['ndl']}&page={params['page']}"

        print(Fore.BLUE + f"\nAbriendo la página {current_page} de Steam: {url}")
        driver.get(url)

        # Esperar a que la página cargue completamente
        time.sleep(2)  # Puedes ajustar este tiempo según tu conexión

        # Obtener todos los elementos de los juegos en la página
        print(Fore.BLUE + "Buscando los juegos populares en la página...")
        game_elements = driver.find_elements(By.CLASS_NAME, 'search_result_row')

        # Si no se encuentran juegos, terminar el scraping
        if not game_elements:
            print(Fore.RED + "No se encontraron juegos en la página. Terminando el scraping.")
            break
        else:
            print(Fore.GREEN + f"Se encontraron {len(game_elements)} juegos en la página {current_page}.")

        # Recorrer cada juego y extraer la información
        for game in game_elements:
            # Extraer el nombre del juego
            try:
                name = game.find_element(By.CLASS_NAME, 'title').text
                print(Fore.BLUE + f"Juego popular encontrado: {name}")
            except Exception as e:
                print(Fore.RED + f"Error al extraer el nombre del juego popular: {e}")
                continue

            # Extraer la fecha de lanzamiento y limpiar la coma extra si la tiene
            try:
                release_date_text = game.find_element(By.CLASS_NAME, 'search_released').text.strip().upper().replace(',', '')
                print(Fore.BLUE + f"Fecha de lanzamiento extraída: {release_date_text}")
            except Exception as e:
                print(Fore.RED + f"Error al extraer la fecha de lanzamiento del juego popular {name}: {e}")
                continue

            # Intentar parsear la fecha de lanzamiento
            try:
                if not release_date_text or release_date_text in ['PRÓXIMAMENTE', 'COMING SOON']:
                    print(Fore.YELLOW + f"Juego {name} no tiene fecha válida, saltando...")
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
                    print(Fore.YELLOW + f"Formato de fecha desconocido para el juego {name}, saltando...")
                    continue

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

                month = months.get(month_str, 0)
                if month == 0:
                    print(Fore.YELLOW + f"Mes desconocido '{month_str}' para el juego {name}, saltando...")
                    continue

                release_date = datetime(year, month, day).date()
                print(Fore.BLUE + f"Fecha de lanzamiento parseada: {release_date}")
            except Exception as e:
                print(Fore.RED + f"Error al parsear la fecha de lanzamiento para el juego {name}: {e}")
                continue

            # Insertar los datos en la tabla 'popularupcoming'
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO popularupcoming (name, release_date)
                    VALUES (?, ?)
                ''', (name, release_date_text))
                if cursor.rowcount == 1:
                    print(Fore.GREEN + f"Juego popular '{name}' insertado en la base de datos.")
                else:
                    print(Fore.YELLOW + f"Juego popular '{name}' ya existe en la base de datos, omitiendo inserción.")
            except Exception as e:
                print(Fore.RED + f"Error al insertar el juego popular '{name}' en la base de datos: {e}")

            # Verificar si la fecha de lanzamiento coincide con la fecha objetivo
            if release_date == target_date:
                print(Fore.GREEN + f"Se ha encontrado el juego con la fecha objetivo: {name} ({release_date})")
                stop_scraping = True
                break  # Salir del bucle de juegos

        # Confirmar los cambios
        conn.commit()

        # Incrementar la página y continuar
        if not stop_scraping:
            current_page += 1
            print(Fore.BLUE + f"Pasando a la página {current_page}...")
            time.sleep(2)  # Esperar antes de cargar la siguiente página
        else:
            print(Fore.BLUE + "Fecha objetivo encontrada, deteniendo el scraping.")
            break

    # Cerrar la conexión a la base de datos
    conn.close()
    print(Fore.GREEN + "\nDatos de juegos populares guardados en la base de datos.")

    # Cerrar el navegador
    driver.quit()
    print(Fore.GREEN + "Script finalizado y navegador cerrado.")

if __name__ == '__main__':
    # Configurar el analizador de argumentos
    parser = argparse.ArgumentParser(description='Scrapea juegos populares de Steam hasta encontrar una fecha específica.')
    parser.add_argument('target_date', help='Fecha objetivo en formato DD MMM YYYY (e.g., 1 AUG 2024)')
    parser.add_argument('--max_pages', type=int, default=100, help='Número máximo de páginas a scrappear (default: 100)')

    args = parser.parse_args()

    main(args.target_date, args.max_pages)
