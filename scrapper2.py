# scrapper2.py

import sqlite3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
from colorama import init, Fore
import datetime
import logging
from selenium.webdriver.remote.remote_connection import LOGGER

# Suppress selenium logs and warnings
LOGGER.setLevel(logging.CRITICAL)
logging.getLogger('WDM').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)

def scrape_all_game_details(start_date_str, end_date_str, max_games=None):
    """
    Extrae los detalles de los juegos ya presentes en 'games' dentro del rango de fechas y sin media procesada.
    Si max_games está definido, solo procesa hasta ese número de juegos (útil para debug, consistente con scrapper.py).
    """
    init(autoreset=True)

    # Convert the date strings to datetime.date objects
    try:
        start_date = datetime.datetime.strptime(start_date_str, '%d %b %Y').date()
        end_date = datetime.datetime.strptime(end_date_str, '%d %b %Y').date()
    except ValueError as ve:
        print(Fore.RED + f"Error parsing dates: {ve}")
        return

    def connect_db():
        """Connect to the SQLite database and ensure the table has the necessary columns."""
        conn = sqlite3.connect('SR_BBDD.db')
        cursor = conn.cursor()

        # Verify if the additional columns exist, and if not, add them
        cursor.execute("PRAGMA table_info(games)")
        columns = [info[1] for info in cursor.fetchall()]

        additional_columns = ['short_description', 'long_description', 'tags',
                              'media1', 'media2', 'media3', 'media4', 'media5',
                              'media6', 'media7', 'media8', 'media9',
                              'reviewcount', 'reviewvalue']

        for column in additional_columns:
            if column not in columns:
                cursor.execute(f"ALTER TABLE games ADD COLUMN {column} TEXT")
                print(Fore.GREEN + f"Column '{column}' added to the 'games' table.")

        conn.commit()
        return conn

    def update_game_info(game_id, short_description, long_description, tags, media_links, reviewcount, reviewvalue):
        """Update the game information in the database."""
        conn = connect_db()
        cursor = conn.cursor()

        # Convert the list of tags and media_links to comma-separated strings
        tags_str = ', '.join(tags)

        # Update the game's record
        cursor.execute('''
            UPDATE games
            SET short_description = ?, long_description = ?, tags = ?,
                media1 = ?, media2 = ?, media3 = ?, media4 = ?, media5 = ?,
                media6 = ?, media7 = ?, media8 = ?, media9 = ?,
                reviewcount = ?, reviewvalue = ?
            WHERE id = ?
        ''', (
            short_description,
            long_description,
            tags_str,
            media_links[0] if len(media_links) > 0 else None,
            media_links[1] if len(media_links) > 1 else None,
            media_links[2] if len(media_links) > 2 else None,
            media_links[3] if len(media_links) > 3 else None,
            media_links[4] if len(media_links) > 4 else None,
            media_links[5] if len(media_links) > 5 else None,
            media_links[6] if len(media_links) > 6 else None,
            media_links[7] if len(media_links) > 7 else None,
            media_links[8] if len(media_links) > 8 else None,
            reviewcount,
            reviewvalue,
            game_id
        ))

        conn.commit()
        conn.close()
        print(Fore.GREEN + f"Game with ID {game_id} updated in the database.")

    def scrape_game_details(url):
        """Extract detailed information of a game given its URL."""
        # Configure Selenium options to avoid opening a browser window
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(options=chrome_options)

        print(Fore.BLUE + f"Visiting game page: {url}")
        driver.get(url)
        time.sleep(2)  # Wait for the page to fully load

        # Extract the short description
        try:
            short_desc_elem = driver.find_element(By.CLASS_NAME, 'game_description_snippet')
            short_description = short_desc_elem.text.strip()
            print(Fore.BLUE + f"Short description extracted: {short_description}")
        except Exception:
            short_description = ""
            print(Fore.YELLOW + "Could not extract the short description.")

        # Extract the long description
        try:
            long_desc_elem = driver.find_element(By.ID, 'game_area_description')
            long_description = long_desc_elem.get_attribute('innerHTML').strip()
            print(Fore.BLUE + "Long description extracted.")
        except Exception:
            long_description = ""
            print(Fore.YELLOW + "Could not extract the long description.")

        # Extract the tags
        try:
            tags_elem = driver.find_elements(By.CLASS_NAME, 'app_tag')
            tags = [tag.text.strip() for tag in tags_elem if tag.text.strip() != '+']
            print(Fore.BLUE + f"Tags extracted: {tags}")
        except Exception:
            tags = []
            print(Fore.YELLOW + "Could not extract tags.")

        # Extract media links (images and videos)
        media_links = []
        try:
            media_items = driver.find_elements(By.CSS_SELECTOR, '#highlight_strip_scroll .highlight_strip_item')
            print(Fore.BLUE + f"Number of media found: {len(media_items)}")

            for item in media_items[:9]:  # Limit to the first 9 media items
                if 'highlight_strip_movie' in item.get_attribute('class'):
                    # Video
                    video_id = item.get_attribute('id').replace('thumb_movie_', '')
                    video_elem = driver.find_element(By.ID, f'highlight_movie_{video_id}')
                    video_url = video_elem.get_attribute('data-mp4-hd-source') or video_elem.get_attribute('data-mp4-source')
                    if video_url:
                        media_links.append(video_url)
                        print(Fore.BLUE + f"Video found: {video_url}")
                elif 'highlight_strip_screenshot' in item.get_attribute('class'):
                    # Image
                    img_elem = item.find_element(By.TAG_NAME, 'img')
                    img_url = img_elem.get_attribute('src').replace('116x65', '1920x1080')
                    media_links.append(img_url)
                    print(Fore.BLUE + f"Image found: {img_url}")
        except Exception:
            print(Fore.YELLOW + "Could not extract media.")

        # Extract reviews
        try:
            user_reviews_elem = driver.find_element(By.CLASS_NAME, 'user_reviews_summary_row')
            review_count_elem = user_reviews_elem.find_element(By.CSS_SELECTOR, 'meta[itemprop="reviewCount"]')
            review_value_elem = user_reviews_elem.find_element(By.CSS_SELECTOR, 'meta[itemprop="ratingValue"]')
            reviewcount = int(review_count_elem.get_attribute('content'))
            reviewvalue = review_value_elem.get_attribute('content')
            print(Fore.BLUE + f"Reviews count extracted: {reviewcount}")
            print(Fore.BLUE + f"Review value extracted: {reviewvalue}")
        except Exception:
            reviewcount = 0
            reviewvalue = ''
            print(Fore.YELLOW + "Could not extract reviews.")

        driver.quit()
        return short_description, long_description, tags, media_links, reviewcount, reviewvalue

    # Main logic
    # Connect to the database and get games within the date range that haven't been processed yet
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, release_date, url FROM games
        WHERE release_date BETWEEN ? AND ?
          AND (media1 IS NULL OR media1 = '')
    """, (start_date_str.upper(), end_date_str.upper()))
    games = cursor.fetchall()
    conn.close()

    # Aplicar límite si se solicita (para mantener coherencia con --max del scrapper principal)
    if max_games is not None:
        games = games[:max_games]

    print(Fore.GREEN + f"Found {len(games)} unprocessed games within the date range.")

    for game in games:
        game_id, name, release_date_str, url = game

        # Convert release_date_str to datetime.date
        try:
            release_date = datetime.datetime.strptime(release_date_str.upper(), '%d %b %Y').date()
        except ValueError:
            print(Fore.YELLOW + f"Unknown date format for the game {name}, skipping details.")
            continue

        print(Fore.BLUE + f"\nProcessing game: {name} (ID: {game_id})")

        # Extract the game details
        short_desc, long_desc, tags, media_links, reviewcount, reviewvalue = scrape_game_details(url)

        # If no media were found, assume there's no relevant information and skip
        if not media_links:
            print(Fore.YELLOW + f"No media found for the game {name}, skipping update.")
            continue

        # Update the database with the new data
        update_game_info(game_id, short_desc, long_desc, tags, media_links, reviewcount, reviewvalue)

    print(Fore.GREEN + "\nAll unprocessed game details have been successfully updated.")

# Example usage:
# scrape_all_game_details('01 Jan 2020', '31 Dec 2020', max_games=5)
