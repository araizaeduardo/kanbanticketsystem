from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os
import json
import telnyx
from sqlalchemy import or_, desc, asc
from werkzeug.utils import secure_filename
from calendar import monthrange

load_dotenv()  # Cargar variables de entorno

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['TELNYX_API_KEY'] = os.getenv('TELNYX_API_KEY')
telnyx.api_key = app.config['TELNYX_API_KEY']

db = SQLAlchemy(app)
mail = Mail(app)

# Configuración para archivos
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xls', 'xlsx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class Comentario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contenido = db.Column(db.Text, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    autor = db.Column(db.String(100), nullable=False)
    
    # Relación con archivos adjuntos
    archivos = db.relationship('Archivo', backref='comentario', lazy=True)

class Archivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    ruta = db.Column(db.String(255), nullable=False)
    fecha_subida = db.Column(db.DateTime, default=datetime.utcnow)
    comentario_id = db.Column(db.Integer, db.ForeignKey('comentario.id'), nullable=False)

class CambioTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    campo = db.Column(db.String(50), nullable=False)
    valor_anterior = db.Column(db.String(255))
    valor_nuevo = db.Column(db.String(255))
    fecha_cambio = db.Column(db.DateTime, default=datetime.utcnow)
    autor = db.Column(db.String(100), nullable=False)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(20), default='Nuevo')
    prioridad = db.Column(db.String(10), default='Media')  # Nueva columna
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    codigo_agencia = db.Column(db.String(10), nullable=False)
    agente = db.Column(db.String(100), nullable=False)
    fecha_ticket = db.Column(db.DateTime, nullable=False)
    correo_agencia = db.Column(db.String(100), nullable=False)
    historial_reenvios = db.Column(db.Text, default='')  # Almacenará el historial en formato JSON
    telefono = db.Column(db.String(20))  # Nuevo campo para teléfono
    fecha_limite = db.Column(db.DateTime)  # Nueva columna para deadline
    tiempo_estimado = db.Column(db.Integer)  # Tiempo estimado en horas
    comentarios = db.relationship('Comentario', backref='ticket', lazy=True, order_by=Comentario.fecha_creacion.desc())
    cambios = db.relationship('CambioTicket', backref='ticket', lazy=True, order_by=CambioTicket.fecha_cambio.desc())
    
    @property
    def estado_vencimiento(self):
        if not self.fecha_limite:
            return 'sin_fecha'
        
        ahora = datetime.now()
        tiempo_restante = self.fecha_limite - ahora
        
        if tiempo_restante.total_seconds() < 0:
            return 'vencido'
        elif tiempo_restante.total_seconds() < 24 * 3600:  # 24 horas
            return 'proximo'
        else:
            return 'en_tiempo'
            
    @property
    def tiempo_restante_formato(self):
        if not self.fecha_limite:
            return "Sin fecha límite"
            
        ahora = datetime.now()
        tiempo_restante = self.fecha_limite - ahora
        
        if tiempo_restante.total_seconds() < 0:
            return f"Vencido hace {abs(tiempo_restante).days} días"
        else:
            if tiempo_restante.days > 0:
                return f"Faltan {tiempo_restante.days} días"
            else:
                horas = tiempo_restante.seconds // 3600
                return f"Faltan {horas} horas"

    @staticmethod
    def buscar(
        termino_busqueda=None, 
        estado=None, 
        prioridad=None, 
        fecha_desde=None, 
        fecha_hasta=None,
        orden_por='fecha_creacion',
        orden='desc'
    ):
        query = Ticket.query

        # Búsqueda por texto
        if termino_busqueda:
            query = query.filter(
                or_(
                    Ticket.titulo.ilike(f'%{termino_busqueda}%'),
                    Ticket.descripcion.ilike(f'%{termino_busqueda}%'),
                    Ticket.codigo_agencia.ilike(f'%{termino_busqueda}%'),
                    Ticket.agente.ilike(f'%{termino_busqueda}%')
                )
            )

        # Filtros
        if estado:
            query = query.filter(Ticket.estado == estado)
        if prioridad:
            query = query.filter(Ticket.prioridad == prioridad)
        if fecha_desde:
            query = query.filter(Ticket.fecha_ticket >= fecha_desde)
        if fecha_hasta:
            query = query.filter(Ticket.fecha_ticket <= fecha_hasta)

        # Ordenamiento
        orden_func = desc if orden == 'desc' else asc
        query = query.order_by(orden_func(getattr(Ticket, orden_por)))

        return query.all()

@app.route('/')
def index():
    # Obtener parámetros de búsqueda y filtros
    busqueda = request.args.get('busqueda', '')
    estado = request.args.get('estado', '')
    prioridad = request.args.get('prioridad', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    orden_por = request.args.get('orden_por', 'fecha_creacion')
    orden = request.args.get('orden', 'desc')

    # Convertir fechas si están presentes
    if fecha_desde:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d')
    if fecha_hasta:
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d')

    # Realizar búsqueda
    tickets = Ticket.buscar(
        termino_busqueda=busqueda,
        estado=estado if estado != 'Todas' else None,
        prioridad=prioridad if prioridad != 'Todas' else None,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        orden_por=orden_por,
        orden=orden
    )

    return render_template('index.html', 
                         tickets=tickets, 
                         filtros_activos={
                             'busqueda': busqueda,
                             'estado': estado,
                             'prioridad': prioridad,
                             'fecha_desde': fecha_desde,
                             'fecha_hasta': fecha_hasta,
                             'orden_por': orden_por,
                             'orden': orden
                         })

@app.route('/ticket/nuevo', methods=['POST'])
def crear_ticket():
    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        codigo_agencia = request.form['codigo_agencia']
        agente = request.form['agente']
        fecha_ticket = datetime.strptime(request.form['fecha_ticket'], '%Y-%m-%d')
        correo_agencia = request.form['correo_agencia']
        telefono = request.form.get('telefono')  # Nuevo campo
        prioridad = request.form.get('prioridad', 'Media')  # Nuevo campo
        fecha_limite = request.form.get('fecha_limite')
        tiempo_estimado = request.form.get('tiempo_estimado')
        
        nuevo_ticket = Ticket(
            titulo=titulo, 
            descripcion=descripcion,
            codigo_agencia=codigo_agencia,
            agente=agente,
            fecha_ticket=fecha_ticket,
            correo_agencia=correo_agencia,
            telefono=telefono,
            prioridad=prioridad,  # Agregar prioridad
            fecha_limite=datetime.strptime(fecha_limite, '%Y-%m-%dT%H:%M') if fecha_limite else None,
            tiempo_estimado=int(tiempo_estimado) if tiempo_estimado else None
        )
        db.session.add(nuevo_ticket)
        db.session.commit()
        return redirect(url_for('index'))

@app.route('/ticket/mover/<int:id>', methods=['POST'])
def mover_ticket(id):
    ticket = Ticket.query.get_or_404(id)
    nuevo_estado = request.form['estado']
    ticket.estado = nuevo_estado
    db.session.commit()
    return jsonify({'success': True})

@app.route('/ticket/editar/<int:id>', methods=['GET', 'POST'])
def editar_ticket(id):
    ticket = Ticket.query.get_or_404(id)
    if request.method == 'POST':
        try:
            # Registrar cambios
            if ticket.titulo != request.form['titulo']:
                registrar_cambio(ticket, 'título', ticket.titulo, request.form['titulo'])
            if ticket.descripcion != request.form['descripcion']:
                registrar_cambio(ticket, 'descripción', ticket.descripcion, request.form['descripcion'])
            if ticket.estado != request.form.get('estado'):
                registrar_cambio(ticket, 'estado', ticket.estado, request.form.get('estado'))
            if ticket.prioridad != request.form.get('prioridad'):
                registrar_cambio(ticket, 'prioridad', ticket.prioridad, request.form.get('prioridad'))
            
            # Actualizar ticket
            ticket.titulo = request.form['titulo']
            ticket.descripcion = request.form['descripcion']
            ticket.estado = request.form.get('estado')
            ticket.prioridad = request.form.get('prioridad')
            # ... otros campos ...
            
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
            
    return jsonify({'success': False, 'message': 'Método no permitido'})

@app.route('/ticket/eliminar/<int:id>', methods=['POST'])
def eliminar_ticket(id):
    ticket = Ticket.query.get_or_404(id)
    db.session.delete(ticket)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/ticket/completar/<int:id>', methods=['POST'])
def completar_ticket(id):
    ticket = Ticket.query.get_or_404(id)
    ticket.estado = 'Resuelto'  # o 'Cerrado' según prefieras
    db.session.commit()
    return jsonify({'success': True})

@app.route('/ticket/enviar_correo/<int:id>', methods=['POST'])
def enviar_correo(id):
    ticket = Ticket.query.get_or_404(id)
    try:
        msg = Message(
            'Actualización de Ticket #{}'.format(ticket.id),
            sender=app.config['MAIL_USERNAME'],
            recipients=[ticket.correo_agencia]
        )
        msg.body = f"""
        Detalles del Ticket:
        
        Título: {ticket.titulo}
        Descripción: {ticket.descripcion}
        Estado: {ticket.estado}
        Agente: {ticket.agente}
        Fecha: {ticket.fecha_ticket.strftime('%Y-%m-%d')}
        
        Por favor, no responda a este correo automático.
        """
        mail.send(msg)

        # Guardar en el historial
        historial_actual = json.loads(ticket.historial_reenvios) if ticket.historial_reenvios else []
        nuevo_envio = {
            'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tipo': 'Email',
            'destinatario': ticket.correo_agencia,
            'mensaje': msg.body
        }
        historial_actual.append(nuevo_envio)
        ticket.historial_reenvios = json.dumps(historial_actual)
        db.session.commit()

        return jsonify({
            'success': True, 
            'message': 'Correo enviado exitosamente',
            'historial': nuevo_envio
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/ticket/reenviar/<int:id>', methods=['POST'])
def reenviar_correo(id):
    ticket = Ticket.query.get_or_404(id)
    correo_destino = request.form.get('correo_destino')
    nombre_destino = request.form.get('nombre_destino')
    mensaje_adicional = request.form.get('mensaje_adicional', '')
    
    try:
        msg = Message(
            'Información de Ticket #{}'.format(ticket.id),
            sender=app.config['MAIL_USERNAME'],
            recipients=[correo_destino]
        )
        msg.body = f"""
        Estimado/a {nombre_destino},

        {mensaje_adicional}

        Se le reenvía la información del siguiente ticket:
        
        Título: {ticket.titulo}
        Descripción: {ticket.descripcion}
        Estado: {ticket.estado}
        Agente: {ticket.agente}
        Fecha: {ticket.fecha_ticket.strftime('%Y-%m-%d')}
        Agencia: {ticket.codigo_agencia}
        
        Por favor, no responda a este correo automático.
        """
        mail.send(msg)

        # Guardar en el historial
        historial_actual = json.loads(ticket.historial_reenvios) if ticket.historial_reenvios else []
        nuevo_reenvio = {
            'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tipo': 'Reenvío',
            'destinatario': f"{nombre_destino} ({correo_destino})",
            'mensaje': msg.body
        }
        historial_actual.append(nuevo_reenvio)
        ticket.historial_reenvios = json.dumps(historial_actual)
        db.session.commit()

        return jsonify({
            'success': True, 
            'message': 'Correo reenviado exitosamente',
            'historial': nuevo_reenvio
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/ticket/obtener_correo/<int:id>', methods=['GET'])
def obtener_correo(id):
    ticket = Ticket.query.get_or_404(id)
    return jsonify({
        'correo': ticket.correo_agencia,
        'codigo_agencia': ticket.codigo_agencia,
        'telefono': ticket.telefono
    })

@app.template_filter('json_loads')
def json_loads_filter(value):
    try:
        return json.loads(value) if value else []
    except:
        return []

@app.template_filter('nl2br')
def nl2br_filter(text):
    if not text:
        return ""
    return text.replace('\n', '<br>')

@app.route('/ticket/duplicar/<int:id>', methods=['POST'])
def duplicar_ticket(id):
    ticket_original = Ticket.query.get_or_404(id)
    try:
        nuevo_ticket = Ticket(
            titulo=f"Copia de - {ticket_original.titulo}",
            descripcion=ticket_original.descripcion,
            estado='Nuevo',
            codigo_agencia=ticket_original.codigo_agencia,
            agente=ticket_original.agente,
            fecha_ticket=datetime.now(),
            correo_agencia=ticket_original.correo_agencia
        )
        db.session.add(nuevo_ticket)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Ticket duplicado exitosamente',
            'id': nuevo_ticket.id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/webhook/sms', methods=['POST'])
def webhook_sms():
    try:
        # Obtener datos del webhook de Telyx
        data = request.get_json()
        print("Webhook SMS recibido:", data)  # Debug log
        
        # Verificar que sea un mensaje SMS
        if not data or 'data' not in data or 'event_type' not in data['data']:
            print("Datos inválidos recibidos")  # Debug log
            return jsonify({'success': False, 'message': 'Datos inválidos'})
            
        if data['data']['event_type'] != 'message.received':
            print(f"Tipo de evento no esperado: {data['data']['event_type']}")  # Debug log
            return jsonify({'success': False, 'message': 'Evento no es un mensaje SMS'})
        
        # Extraer información del mensaje
        mensaje = data['data']['payload'].get('text', '')
        telefono_origen = data['data']['payload']['from'].get('phone_number', '')
        fecha_sms = datetime.now()  # Usamos la fecha actual en lugar de intentar parsear
        
        print(f"Mensaje: {mensaje}")  # Debug log
        print(f"Teléfono origen: {telefono_origen}")  # Debug log
        print(f"Fecha: {fecha_sms}")  # Debug log
        
        # Crear nuevo ticket
        nuevo_ticket = Ticket(
            titulo=f"SMS desde {telefono_origen}",
            descripcion=mensaje,
            codigo_agencia=telefono_origen,
            agente="Sistema SMS",
            fecha_ticket=fecha_sms,
            correo_agencia=f"{telefono_origen}@sms.sistema.com",
            telefono=telefono_origen
        )
        
        db.session.add(nuevo_ticket)
        db.session.commit()
        
        print(f"Ticket creado con ID: {nuevo_ticket.id}")  # Debug log
        return jsonify({'success': True, 'message': 'Ticket creado desde SMS'})
        
    except Exception as e:
        print(f"Error en webhook SMS: {str(e)}")  # Debug log
        return jsonify({'success': False, 'message': str(e)})

@app.route('/ticket/enviar_sms/<int:id>', methods=['POST'])
def enviar_sms(id):
    ticket = Ticket.query.get_or_404(id)
    numero_destino = ticket.telefono or request.form.get('numero_destino')
    mensaje = request.form.get('mensaje')
    
    try:
        if not numero_destino:
            return jsonify({
                'success': False,
                'message': 'No hay número de teléfono asociado al ticket ni proporcionado'
            })

        numero_origen = os.getenv('TELNYX_PHONE_NUMBER')
        
        if not numero_origen:
            return jsonify({
                'success': False,
                'message': 'Número de origen no configurado en variables de entorno'
            })

        # Formatear números...
        numero_origen = numero_origen.strip()
        if not numero_origen.startswith('+1'):
            numero_origen = '+1' + numero_origen.lstrip('+')

        numero_destino = numero_destino.strip()
        numero_destino = ''.join(c for c in numero_destino if c.isdigit() or c == '+')
        
        if not numero_destino.startswith('+1'):
            if numero_destino.startswith('+'):
                numero_destino = '+1' + numero_destino[1:]
            else:
                numero_destino = '+1' + numero_destino

        print(f"Enviando SMS desde: {numero_origen} a: {numero_destino}")

        # Enviar SMS usando Telnyx
        mensaje_enviado = telnyx.Message.create(
            from_=numero_origen,
            to=numero_destino,
            text=mensaje,
            messaging_profile_id=os.getenv('TELNYX_MESSAGING_PROFILE_ID')
        )

        # Guardar en el historial
        historial_actual = json.loads(ticket.historial_reenvios) if ticket.historial_reenvios else []
        nuevo_envio = {
            'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tipo': 'SMS',
            'destinatario': numero_destino,
            'mensaje': mensaje,
            'estado': 'enviado'
        }
        historial_actual.append(nuevo_envio)
        ticket.historial_reenvios = json.dumps(historial_actual)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'SMS enviado exitosamente',
            'historial': nuevo_envio
        })
    except Exception as e:
        error_detail = str(e)
        if hasattr(e, 'errors'):
            error_detail = f"Full details: {e.errors}"
        print(f"Error detallado: {error_detail}")
        return jsonify({
            'success': False,
            'message': f'Error al enviar SMS: {error_detail}'
        })

@app.route('/ticket/<int:ticket_id>/comentario', methods=['POST'])
def agregar_comentario(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    contenido = request.form.get('contenido')
    autor = request.form.get('autor', 'Usuario')  # En el futuro, esto vendrá del sistema de usuarios
    
    comentario = Comentario(
        contenido=contenido,
        ticket_id=ticket_id,
        autor=autor
    )
    db.session.add(comentario)
    
    # Manejar archivos adjuntos
    archivos = request.files.getlist('archivos')
    for archivo in archivos:
        if archivo and allowed_file(archivo.filename):
            filename = secure_filename(archivo.filename)
            # Crear subdirectorio para el ticket si no existe
            ticket_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(ticket_id))
            if not os.path.exists(ticket_folder):
                os.makedirs(ticket_folder)
            
            filepath = os.path.join(ticket_folder, filename)
            archivo.save(filepath)
            
            nuevo_archivo = Archivo(
                nombre=filename,
                ruta=filepath,
                comentario=comentario
            )
            db.session.add(nuevo_archivo)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'comentario': {
            'id': comentario.id,
            'contenido': comentario.contenido,
            'autor': comentario.autor,
            'fecha': comentario.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S'),
            'archivos': [{'nombre': a.nombre, 'id': a.id} for a in comentario.archivos]
        }
    })

@app.route('/archivo/<int:archivo_id>')
def descargar_archivo(archivo_id):
    archivo = Archivo.query.get_or_404(archivo_id)
    return send_file(archivo.ruta, as_attachment=True)

@app.route('/archivo/<int:archivo_id>/eliminar', methods=['POST'])
def eliminar_archivo(archivo_id):
    archivo = Archivo.query.get_or_404(archivo_id)
    try:
        # Eliminar el archivo físico
        if os.path.exists(archivo.ruta):
            os.remove(archivo.ruta)
        
        # Eliminar el registro de la base de datos
        db.session.delete(archivo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Archivo eliminado correctamente'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        })

def registrar_cambio(ticket, campo, valor_anterior, valor_nuevo, autor='Sistema'):
    if valor_anterior != valor_nuevo:
        cambio = CambioTicket(
            ticket_id=ticket.id,
            campo=campo,
            valor_anterior=str(valor_anterior),
            valor_nuevo=str(valor_nuevo),
            autor=autor
        )
        db.session.add(cambio)

@app.route('/vista/<string:tipo>')
def vista(tipo):
    # Obtener parámetros comunes
    busqueda = request.args.get('busqueda', '')
    estado = request.args.get('estado', '')
    prioridad = request.args.get('prioridad', '')
    agrupacion = request.args.get('agrupar_por', '')
    
    # Obtener tickets filtrados
    tickets = Ticket.buscar(
        termino_busqueda=busqueda,
        estado=estado if estado != 'Todas' else None,
        prioridad=prioridad if prioridad != 'Todas' else None
    )
    
    if tipo == 'kanban':
        return render_template('vistas/kanban.html', 
                             tickets=tickets, 
                             filtros_activos=request.args)
                             
    elif tipo == 'lista':
        # Ordenamiento para vista de lista
        orden_por = request.args.get('orden_por', 'fecha_creacion')
        orden = request.args.get('orden', 'desc')
        tickets = sorted(tickets, 
                        key=lambda x: getattr(x, orden_por),
                        reverse=(orden == 'desc'))
        
        return render_template('vistas/lista.html', 
                             tickets=tickets,
                             filtros_activos=request.args)
                             
    elif tipo == 'calendario':
        # Organizar tickets por fecha para vista de calendario
        año = int(request.args.get('año', datetime.now().year))
        mes = int(request.args.get('mes', datetime.now().month))
        
        # Crear calendario mensual
        _, dias_en_mes = monthrange(año, mes)
        calendario = {dia: [] for dia in range(1, dias_en_mes + 1)}
        
        for ticket in tickets:
            dia = ticket.fecha_ticket.day
            if ticket.fecha_ticket.year == año and ticket.fecha_ticket.month == mes:
                calendario[dia].append(ticket)
        
        return render_template('vistas/calendario.html',
                             calendario=calendario,
                             año=año,
                             mes=mes,
                             filtros_activos=request.args)
                             
    elif tipo == 'agrupada':
        # Agrupar tickets según el criterio seleccionado
        tickets_agrupados = {}
        if agrupacion == 'estado':
            for ticket in tickets:
                tickets_agrupados.setdefault(ticket.estado, []).append(ticket)
        elif agrupacion == 'prioridad':
            for ticket in tickets:
                tickets_agrupados.setdefault(ticket.prioridad, []).append(ticket)
        elif agrupacion == 'agencia':
            for ticket in tickets:
                tickets_agrupados.setdefault(ticket.codigo_agencia, []).append(ticket)
        
        return render_template('vistas/agrupada.html',
                             tickets_agrupados=tickets_agrupados,
                             agrupacion=agrupacion,
                             filtros_activos=request.args)
    
    # Por defecto, redirigir a vista Kanban
    return redirect(url_for('vista', tipo='kanban'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5003)
