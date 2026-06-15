import sqlite3


def connect_db():
    """Conectar a la base de datos SQLite"""
    conn = sqlite3.connect('SR_BBDD.db')
    return conn


def execute_query(query):
    """Ejecutar una consulta SQL y mostrar los resultados"""
    conn = connect_db()
    cursor = conn.cursor()

    try:
        # Ejecutar la consulta
        cursor.execute(query)

        # Si es un SELECT, fetchall() devuelve los resultados
        if query.strip().upper().startswith('SELECT'):
            results = cursor.fetchall()
            if results:
                for row in results:
                    print(row)
            else:
                print("Consulta ejecutada, pero no hay resultados.")

        # Si no es un SELECT, commit a la base de datos
        else:
            conn.commit()
            print(f"Consulta '{query}' ejecutada con éxito.")

    except sqlite3.Error as e:
        print(f"Error al ejecutar la consulta: {e}")

    finally:
        # Cerrar la conexión
        conn.close()


def main():
    print("Bienvenido a la consola SQL para SR_BBDD")
    print("Escribe tus consultas SQL. Escribe 'salir' para terminar.")

    while True:
        # Leer la consulta del usuario
        query = input("SQL> ")

        # Verificar si el usuario quiere salir
        if query.lower() == 'salir':
            print("Saliendo de la consola SQL.")
            break

        # Ejecutar la consulta
        execute_query(query)


if __name__ == "__main__":
    main()
