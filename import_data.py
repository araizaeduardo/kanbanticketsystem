import sqlite3

def import_database_data():
    try:
        # Conectar a ambas bases de datos
        source_conn = sqlite3.connect('tickets.db')
        dest_conn = sqlite3.connect('instance/tickets.db')
        
        source_cursor = source_conn.cursor()
        dest_cursor = dest_conn.cursor()
        
        # Obtener todas las tablas de la base de datos origen
        source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = source_cursor.fetchall()
        
        # Para cada tabla
        for table in tables:
            table_name = table[0]
            
            # Obtener la estructura de la tabla
            source_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';")
            create_table_sql = source_cursor.fetchone()[0]
            
            # Crear la tabla en la base de datos destino
            dest_cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
            dest_cursor.execute(create_table_sql)
            
            # Copiar los datos
            source_cursor.execute(f"SELECT * FROM {table_name};")
            rows = source_cursor.fetchall()
            
            if rows:
                # Obtener los nombres de las columnas
                columns = [description[0] for description in source_cursor.description]
                placeholders = ','.join(['?' for _ in columns])
                
                # Insertar los datos
                dest_cursor.executemany(
                    f"INSERT INTO {table_name} VALUES ({placeholders});",
                    rows
                )
            
            print(f"Tabla {table_name} importada exitosamente")
        
        # Guardar cambios
        dest_conn.commit()
        
        # Cerrar conexiones
        source_conn.close()
        dest_conn.close()
        
        print("Importación completada exitosamente")
        
    except sqlite3.Error as e:
        print(f"Error de SQLite: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import_database_data() 