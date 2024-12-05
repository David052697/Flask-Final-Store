# Importamos la aplicación Flask desde el archivo app ubicado en la carpeta /a
from app import app  

def application(environ, start_response):
    """
    Función WSGI que actúa como punto de entrada para todas las peticiones.
    """
    return app(environ, start_response)  # Pasamos el control a la aplicación Flask

if __name__ == '__main__':
    # Usamos wsgiref para crear un servidor simple WSGI
    from wsgiref.simple_server import make_server

    # Configuración del servidor: dirección localhost y puerto 8080
    srv = make_server('localhost', 8080, application)  
    print("Servidor corriendo en http://localhost:8080")
    
    # Mantenemos el servidor ejecutándose
    srv.serve_forever()
