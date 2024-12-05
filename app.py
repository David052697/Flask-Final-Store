from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import os
from flask_bcrypt import Bcrypt
import mysql.connector
import logging
from flask_restful import Api, Resource
from flask_mail import Mail, Message
from flask_babel import Babel, _

app = Flask(__name__)
api = Api(app)
app.secret_key = 'clave_secreta'
bcrypt = Bcrypt(app)

# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.mailgun.org'  # Servidor SMTP de Mailgun
app.config['MAIL_PORT'] = 587  # Puerto recomendado
app.config['MAIL_USE_TLS'] = True  # Usamos TLS para la conexión segura
app.config['MAIL_USE_SSL'] = False  # No usar SSL
app.config['MAIL_USERNAME'] = 'postmaster@sandboxf6cd6ed2bc5b4d8d8873b1e7487177fc.mailgun.org'  # Usuario SMTP
app.config['MAIL_PASSWORD'] = '00aae1bf35149057fde4a3edbe17ebbf-c02fd0ba-81da963e'  # Contraseña SMTP
app.config['MAIL_DEFAULT_SENDER'] = 'no-reply@tuapp.com'  # Cambia esto si deseas personalizar el remitente
   
mail = Mail(app)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="tienda"
)

#Flask RestFull API Build Los productos para una mejor manipulacion
class Producto(Resource):
    # Obtener todos los productos
    def get(self):
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM productos")
        productos = cursor.fetchall()
        return jsonify(productos)

    # Agregar un nuevo producto
    def post(self):
        data = request.get_json()  # Obtener los datos en formato JSON
        nombre = data.get('nombre')
        cantidad = data.get('cantidad')
        precio = data.get('precio')
        imagen = data.get('imagen')

        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO productos (nombre, cantidad, precio, imagen) VALUES (%s, %s, %s, %s)",
            (nombre, cantidad, precio, imagen)
        )
        db.commit()
        return jsonify({"message": "Producto agregado exitosamente"}), 201

    # Actualizar un producto existente
    def put(self, producto_id):
        data = request.get_json()
        nombre = data.get('nombre')
        cantidad = data.get('cantidad')
        precio = data.get('precio')
        imagen = data.get('imagen')

        cursor = db.cursor()
        cursor.execute(
            "UPDATE productos SET nombre = %s, cantidad = %s, precio = %s, imagen = %s WHERE id = %s",
            (nombre, cantidad, precio, imagen, producto_id)
        )
        db.commit()
        return jsonify({"message": "Producto actualizado exitosamente"})

    # Eliminar un producto
    def delete(self, producto_id):
        cursor = db.cursor()
        cursor.execute("DELETE FROM productos WHERE id = %s", (producto_id,))
        db.commit()
        return jsonify({"message": "Producto eliminado exitosamente"})

# Rutas para los productos
api.add_resource(Producto, '/api/productos', '/api/productos/<int:producto_id>')

UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

inventario = []
# Configuración para internacionalización
app.config['BABEL_DEFAULT_LOCALE'] = 'es'  # Idioma por defecto
app.config['BABEL_SUPPORTED_LOCALES'] = ['es', 'en']

babel = Babel(app)

# Función para determinar el idioma preferido
def get_locale():
    return request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LOCALES'])

# Inicializa la función de localización
babel.init_app(app, locale_selector=get_locale)


# Configurar el registro de logs en el archivo logs.txt
log_file = 'logs.txt'  # Archivo de logs en la raíz de la carpeta del proyecto
logging.basicConfig(
    filename=log_file,  # Especificar el archivo donde se guardarán los logs
    level=logging.DEBUG,  # Nivel de registro
    format='%(asctime)s - %(levelname)s - %(message)s',  # Formato de los logs
)

# Registrar un mensaje al iniciar la aplicación
app.logger.info('La aplicación Flask ha iniciado.')

# Ruta principal: redirige según el rol del usuario
@app.route('/home', methods=['GET', 'POST'] )
def main():
    if 'user_id' in session:
        if 'roles' in session:
            if 'vendedor' in session['roles']:
                return redirect(url_for('carrito'))
            elif 'comprador' in session['roles']:
                return redirect(url_for('comprador_dashboard'))
    return redirect(url_for('dashboard'))

# Dashboard general
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# Carrito de compras (solo para vendedores)
@app.route('/', methods=['GET', 'POST'])
def carrito():
    if 'user_id' not in session or 'roles' not in session or 'vendedor' not in session['roles']:
        flash("Acceso denegado. Solo vendedores pueden acceder.", "danger")
        return redirect(url_for('login'))

    # Establecer el número de productos por página
    products_per_page = 6

    # Obtener la página actual, por defecto será la 1
    page = request.args.get('page', 1, type=int)

    # Calcular el desplazamiento basado en la página
    offset = (page - 1) * products_per_page
    cursor = db.cursor(dictionary=True)

    # Verifica si el carrito está en la sesión
    if 'carrito' not in session:
        session['carrito'] = []

    if request.method == 'POST':
        # Validar si se ha subido una imagen
        if 'imagen' not in request.files or request.files['imagen'].filename == '':
            return redirect(url_for('carrito'))

        # Guardar la imagen
        imagen = request.files['imagen']
        filename = secure_filename(imagen.filename)
        imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # Crear el producto
        producto = {
            'nombre': request.form['nombre'],
            'cantidad': int(request.form['cantidad']),
            'precio': float(request.form['precio']),
            'imagen': filename
        }

        # Insertar el producto en la base de datos
        cursor.execute("INSERT INTO productos (nombre, cantidad, precio, imagen) VALUES (%s, %s, %s, %s)", 
                       (producto['nombre'], producto['cantidad'], producto['precio'], producto['imagen']))
        db.commit()
        flash("Producto agregado al inventario", "success")
        return redirect(url_for('carrito'))

    # Obtener productos con LIMIT y OFFSET para la paginación
    cursor.execute("SELECT * FROM productos LIMIT %s OFFSET %s", (products_per_page, offset))
    inventario = cursor.fetchall()

    # Obtener el número total de productos
    cursor.execute("SELECT COUNT(*) FROM productos")
    total_products = cursor.fetchone()['COUNT(*)']

    # Calcular el número total de páginas
    total_pages = (total_products + products_per_page - 1) // products_per_page

    # Recuperar la variable de pago exitoso de la sesión
    pago_exitoso = session.pop('pago_exitoso', False)

    # Pasar todos los datos necesarios a la plantilla
    return render_template('carrito.html', carrito=session['carrito'], pago_exitoso=pago_exitoso, inventario=inventario, total_pages=total_pages, current_page=page)

#ruta De vender se almacenan los productos en la base de datos con sus validaciones 
@app.route('/vende', methods=['GET', 'POST'])
def vende():
    if request.method == 'POST':
        try:
            # Obtener los datos del formulario
            nombre = request.form['nombre']
            cantidad = int(request.form['cantidad'])
            precio = float(request.form['precio'])

            # Procesar la imagen
            imagen = request.files['imagen']
            if imagen:
                imagen_filename = secure_filename(imagen.filename)
                imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename)
                imagen.save(imagen_path)
            else:
                flash("Debe proporcionar una imagen", "error")
                return redirect(url_for('vende'))

            # Usar la conexión global 'db'
            cursor = db.cursor()

            # Insertar el producto en la base de datos
            query = "INSERT INTO productos (nombre, cantidad, precio, imagen) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (nombre, cantidad, precio, imagen_filename))
            db.commit()

            # Cerrar el cursor
            cursor.close()

            flash("Producto agregado exitosamente", "success")

            # Redirigir a 'comprador_dashboard'
            return redirect(url_for('comprador_dashboard'))

        except Exception as e:
            flash(f"Error al agregar el producto: {e}", "error")
            return redirect(url_for('vende'))

    # Si es GET, simplemente mostrar el formulario
    return render_template('dashboard.html')


# Registro de usuario
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']  # Usamos la contraseña sin cifrar para enviarla en el correo
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')  # Ciframos la contraseña

        rol_id = request.form['rol']  # Recibe el ID del rol desde el formulario

        try:
            # Insertar usuario en la base de datos
            cursor = db.cursor()
            cursor.execute("INSERT INTO usuarios (username, email, password) VALUES (%s, %s, %s)", (username, email, hashed_password))
            db.commit()

            user_id = cursor.lastrowid  # Obtiene el ID del usuario recién creado
            cursor.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s, %s)", (user_id, rol_id))
            db.commit()

            # Obtener el nombre del rol
            cursor.execute("SELECT nombre FROM roles WHERE id = %s", (rol_id,))
            rol = cursor.fetchone()
            rol_nombre = rol[0] if rol else 'Sin definir'

            # Lógica para cambiar el rol a "Comprador" si es vendedor
            if rol_nombre == 'vendedor':
                rol_nombre = 'Comprador'  # Si el rol es vendedor, se cambia a comprador
            else:
                rol_nombre = 'Vendedor'  # Si el rol no es vendedor ni comprador, se asigna como vendedor por defecto

            # Enviar correo de confirmación
            msg = Message(
                'Confirmación de Registro',
                sender=app.config['MAIL_DEFAULT_SENDER'],  # Dirección de remitente configurada en Flask-Mail
                recipients=[email]  # Dirección de correo del usuario registrado
            )
            # Usamos un template HTML para el correo, incluyendo la contraseña sin cifrar
            msg.html = render_template('email.html', username=username, email=email, rol=rol_nombre, password=password)
            mail.send(msg)

            flash('Usuario registrado exitosamente. Por favor, revisa tu correo.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            db.rollback()  # Revertir cambios en caso de error
            flash(f'Ocurrió un error al registrar el usuario: {e}', 'danger')

    return render_template('register.html')

# Login de usuario
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        rol = request.form['rol']

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        user = cursor.fetchone()

        # Si el usuario no existe en la base de datos
        if not user:
            if rol == 'vendedor':
                flash("No estás registrado como vendedor. Por favor, regístrate primero.", "warning")
            elif rol == 'comprador':
                flash("No estás registrado como comprador. Por favor, regístrate primero.", "warning")
            flash("Correo o contraseña incorrectos.", "danger")
            return redirect(url_for('login'))

        # Verificar la contraseña
        if not bcrypt.check_password_hash(user['password'], password):
            flash("Correo o contraseña incorrectos.", "danger")
            return redirect(url_for('login'))

        # Verificar el rol del usuario
        cursor.execute("SELECT * FROM usuario_roles WHERE usuario_id = %s", (user['id'],))
        roles = cursor.fetchall()
        roles_asignados = [rol['rol_id'] for rol in roles]

        # Validar si el rol coincide con el ingresado
        if (rol == 'vendedor' and 1 not in roles_asignados) or (rol == 'comprador' and 2 not in roles_asignados):
            if rol == 'vendedor':
                flash("No tienes permisos como vendedor. Regístrate o selecciona el rol correcto.", "warning")
            elif rol == 'comprador':
                flash("No tienes permisos como comprador. Regístrate o selecciona el rol correcto.", "warning")
            return redirect(url_for('login'))

        # Inicio de sesión exitoso
        session['user_id'] = user['id']
        session['user_name'] = user['username']  # Asegúrate de que "username" exista en la base de datos
        session['roles'] = [rol]  # Almacena el rol en la sesión
        flash("Inicio de sesión exitoso.", "success")

        # Enviar notificación por correo electrónico cuando el usuario inicie sesión
        msg = Message(
            'Notificación de Inicio de Sesión',
            sender=app.config['MAIL_DEFAULT_SENDER'],  # Dirección configurada en Flask-Mail
            recipients=[email]  # Enviar al correo del usuario
        )
        # Usar un template HTML para el correo
        msg.html = render_template('email1.html', username=user['username'], rol=rol)
        mail.send(msg)

        # Redirige al dashboard según el rol
        if rol == 'vendedor':
            return redirect(url_for('carrito'))
        elif rol == 'comprador':
            return redirect(url_for('comprador_dashboard'))

    return render_template('login.html')




# Dashboard del comprador
@app.route('/comprador_dashboard', methods=['GET', 'POST'])
def comprador_dashboard():
    # Verificar autenticación y rol
    if 'user_id' not in session or 'roles' not in session or 'comprador' not in session['roles']:
        flash("Acceso denegado. Solo compradores pueden acceder.", "danger")
        return redirect(url_for('login'))

    # Configuración para la paginación
    products_per_page = 6
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * products_per_page
    cursor = db.cursor(dictionary=True)

    # Manejo del formulario para agregar productos
    if request.method == 'POST':
        if 'imagen' not in request.files or request.files['imagen'].filename == '':
            flash("Debes subir una imagen para el producto.", "danger")
            return redirect(url_for('comprador_dashboard'))

        imagen = request.files['imagen']
        filename = secure_filename(imagen.filename)
        imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        producto = {
            'nombre': request.form['nombre'],
            'cantidad': int(request.form['cantidad']),
            'precio': float(request.form['precio']),
            'imagen': filename
        }

        cursor.execute("INSERT INTO productos (nombre, cantidad, precio, imagen) VALUES (%s, %s, %s, %s)",
                       (producto['nombre'], producto['cantidad'], producto['precio'], producto['imagen']))
        db.commit()
        flash("Producto agregado exitosamente", "success")
        return redirect(url_for('comprador_dashboard'))

    # Consultar productos para mostrar
    cursor.execute("SELECT * FROM productos LIMIT %s OFFSET %s", (products_per_page, offset))
    productos = cursor.fetchall()

    # Contar el total de productos para calcular la paginación
    cursor.execute("SELECT COUNT(*) FROM productos")
    total_products = cursor.fetchone()['COUNT(*)']
    total_pages = (total_products + products_per_page - 1) // products_per_page

    # Renderizar el template con los datos
    return render_template('comprador_dashboard.html', productos=productos, total_pages=total_pages, current_page=page)



@app.route('/eliminar_producto/<int:id>', methods=['POST'])
def eliminar_producto(id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("DELETE FROM productos WHERE id = %s", (id,))
    db.commit()
    flash("Producto eliminado exitosamente", "success")
    return redirect(url_for('comprador_dashboard'))


@app.route('/modificar_producto/<int:id>/<accion>', methods=['POST'])
def modificar_producto(id, accion):
    cantidad_modificar = int(request.form['cantidad'])
    cursor = db.cursor(dictionary=True)
    
    # Consultar cantidad actual del producto
    cursor.execute("SELECT cantidad FROM productos WHERE id = %s", (id,))
    producto = cursor.fetchone()
    
    if producto:
        cantidad_actual = producto['cantidad']

        if accion == 'agregar':
            nueva_cantidad = cantidad_actual + cantidad_modificar
        elif accion == 'eliminar':
            if cantidad_modificar > cantidad_actual:
                flash(f"No puedes eliminar más de la cantidad existente ({cantidad_actual}).", "danger")
                return redirect(url_for('comprador_dashboard'))
            nueva_cantidad = cantidad_actual - cantidad_modificar
        else:
            flash(f"No puedes eliminar más de la cantidad existente ({cantidad_actual}).", "danger")
            return redirect(url_for('comprador_dashboard'))

        if nueva_cantidad <= 0:
            # Eliminar producto si la cantidad es 0 o negativa
            cursor.execute("DELETE FROM productos WHERE id = %s", (id,))
            db.commit()
            flash("Producto eliminado porque la cantidad llegó a 0", "success")
        else:
            # Actualizar la cantidad
            cursor.execute("UPDATE productos SET cantidad = %s WHERE id = %s", (nueva_cantidad, id))
            db.commit()
            flash("Cantidad del producto actualizada", "success")
    else:
        flash("Producto no encontrado", "danger")
    
    return redirect(url_for('comprador_dashboard'))

# Logout de usuario
@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada', 'success')
    return redirect(url_for('login'))

# Ruta para eliminar productos del carrito
@app.route('/eliminar/<string:nombre>', methods=['POST'])
def eliminar(nombre):
    carrito = session.get('carrito', [])
    cursor = db.cursor(dictionary=True)

    for item in carrito:
        if item['nombre'] == nombre:
            cursor.execute("SELECT * FROM productos WHERE nombre = %s", (nombre,))
            producto = cursor.fetchone()
            if producto:
                nueva_cantidad = producto['cantidad'] + item['cantidad']
                cursor.execute("UPDATE productos SET cantidad = %s WHERE nombre = %s", (nueva_cantidad, nombre))
                db.commit()
            break

    session['carrito'] = [item for item in carrito if item['nombre'] != nombre]
    return redirect(url_for('carrito'))

# Modificar cantidad de un producto en el carrito
@app.route('/modificar', methods=['POST'])
def modificar():
    nombre = request.form['nombre']  # Nombre del producto desde el formulario
    nueva_cantidad = int(request.form['cantidad'])  # Nueva cantidad desde el formulario

    cursor = db.cursor(dictionary=True)

    # Consultar el producto en la base de datos
    cursor.execute("SELECT * FROM productos WHERE nombre = %s", (nombre,))
    producto = cursor.fetchone()

    if producto:
        cantidad_disponible = producto['cantidad']

        # Obtener el carrito actual de la sesión
        carrito = session.get('carrito', [])

        # Buscar el producto en el carrito
        item_en_carrito = next((item for item in carrito if item['nombre'] == nombre), None)

        # Calcular la cantidad actual en el carrito
        cantidad_en_carrito = item_en_carrito['cantidad'] if item_en_carrito else 0

        if nueva_cantidad <= cantidad_disponible:
            # Sumar la nueva cantidad al carrito y restarla del inventario
            cantidad_total_carrito = cantidad_en_carrito + nueva_cantidad
            if item_en_carrito:
                item_en_carrito['cantidad'] = cantidad_total_carrito
            else:
                carrito.append({'nombre': nombre, 'cantidad': cantidad_total_carrito})

            # Restar la nueva cantidad del inventario
            nueva_cantidad_disponible = cantidad_disponible - nueva_cantidad
            cursor.execute("UPDATE productos SET cantidad = %s WHERE nombre = %s", 
                           (nueva_cantidad_disponible, nombre))
            db.commit()

            # Guardar el carrito actualizado en la sesión
            session['carrito'] = carrito
            flash("Cantidad modificada exitosamente.", "success")
        else:
            # Mostrar mensaje de error si la cantidad excede el inventario
            flash(f"Cantidad excedida. Solo hay {cantidad_disponible} unidades disponibles, intentalo nuevamente.", "error")
    else:
        flash("El producto no existe.", "error")

    return redirect(url_for('carrito'))


# Vaciar el carrito
@app.route('/vaciar', methods=['POST'])
def vaciar():
    carrito = session.get('carrito', [])
    cursor = db.cursor(dictionary=True)

    # Itera sobre los productos en el carrito
    for item in carrito:
        # Busca el producto en la base de datos
        cursor.execute("SELECT * FROM productos WHERE nombre = %s", (item['nombre'],))
        producto = cursor.fetchone()
        if producto:
            # Devuelve la cantidad al inventario
            nueva_cantidad = producto['cantidad'] + item['cantidad']
            cursor.execute("UPDATE productos SET cantidad = %s WHERE nombre = %s", (nueva_cantidad, item['nombre']))

    # Vacía el carrito
    session.pop('carrito', None)

    # Guarda los cambios en la base de datos
    db.commit()
    cursor.close()

    return redirect(url_for('carrito'))


# Procesar el pago
@app.route('/pagar', methods=['POST'])
def pagar():
    cursor = db.cursor(dictionary=True)

    # Obtén los detalles del carrito desde la sesión
    carrito = session.get('carrito', [])

    if not carrito:
        # Si no hay productos en el carrito, redirige con un mensaje
        flash("El carrito está vacío. No se puede realizar el pago.", "warning")
        return redirect(url_for('carrito'))

    # Calcula el total de la compra
    total = sum(item['precio'] * item['cantidad'] for item in carrito)

    # Guarda los detalles de la compra en la sesión para mostrarlos después
    session['total_pago'] = total
    session['detalle_compra'] = carrito
    session['pago_exitoso'] = True

    # Actualiza la base de datos para eliminar productos con cantidad 0
    cursor.execute("DELETE FROM productos WHERE cantidad = 0")
    db.commit()

    # Limpia el carrito después de procesar el pago
    session.pop('carrito', None)

    # Redirige al carrito (tu flujo original)
    return redirect(url_for('carrito'))


# Agregar producto al carrito
@app.route('/agregar_al_carrito/<string:nombre>', methods=['POST'])
def agregar_al_carrito(nombre):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos WHERE nombre = %s", (nombre,))
    producto = cursor.fetchone()

    if producto:
        cantidad_ingresada = int(request.form['cantidad'])
        if cantidad_ingresada > producto['cantidad']:
            flash('Stock insuficiente', 'error')
            return redirect(url_for('carrito'))  # Volver a la misma página del carrito con el mensaje de error

        carrito = session.get('carrito', [])
        encontrado = False

        for item in carrito:
            if item['nombre'] == producto['nombre']:
                if item['cantidad'] + cantidad_ingresada <= producto['cantidad']:
                    item['cantidad'] += cantidad_ingresada
                else:
                    flash('Stock insuficiente', 'error')
                    return redirect(url_for('carrito'))  # Volver a la misma página del carrito con el mensaje de error
                encontrado = True
                break

        if not encontrado:
            carrito.append({
                'nombre': producto['nombre'],
                'cantidad': cantidad_ingresada,
                'precio': producto['precio'],
                'imagen': producto['imagen']
            })

        session['carrito'] = carrito
        nueva_cantidad = producto['cantidad'] - cantidad_ingresada
        cursor.execute("UPDATE productos SET cantidad = %s WHERE nombre = %s", (nueva_cantidad, nombre))
        db.commit()
        
        flash('Producto agregado exitosamente', 'success')  # Mensaje de éxito

    # Al final, renderiza de nuevo la página del carrito para que los cambios sean visibles sin salir de la página
    return redirect(url_for('carrito'))  # Redirige a la misma página de carrito para actualizar los datos


# Manejo de errores 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)
