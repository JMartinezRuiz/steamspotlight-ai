import sqlite3

# Conectar o crear la base de datos
conn = sqlite3.connect('SR_BBDD.db')
cursor = conn.cursor()

# Crear la tabla 'games' si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        release_date TEXT,
        url TEXT NOT NULL,
        price TEXT
    )
''')

# Confirmar los cambios y cerrar la conexión
conn.commit()
conn.close()
