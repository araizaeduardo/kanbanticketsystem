from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os
import json
import telnyx

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

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(20), default='Nuevo')
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    codigo_agencia = db.Column(db.String(10), nullable=False)
    agente = db.Column(db.String(100), nullable=False)
    fecha_ticket = db.Column(db.DateTime, nullable=False)
    correo_agencia = db.Column(db.String(100), nullable=False)
    historial_reenvios = db.Column(db.Text, default='')  # Almacenará el historial en formato JSON
    telefono = db.Column(db.String(20))  # Nuevo campo para teléfono

@app.route('/')
def index():
    tickets = Ticket.query.all()
    return render_template('index.html', tickets=tickets)

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
        
        nuevo_ticket = Ticket(
            titulo=titulo, 
            descripcion=descripcion,
            codigo_agencia=codigo_agencia,
            agente=agente,
            fecha_ticket=fecha_ticket,
            correo_agencia=correo_agencia,
            telefono=telefono  # Agregar el nuevo campo
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
            ticket.titulo = request.form['titulo']
            ticket.descripcion = request.form['descripcion']
            ticket.codigo_agencia = request.form['codigo_agencia']
            ticket.agente = request.form['agente']
            ticket.fecha_ticket = datetime.strptime(request.form['fecha_ticket'], '%Y-%m-%d')
            ticket.correo_agencia = request.form['correo_agencia']
            ticket.telefono = request.form.get('telefono')  # Nuevo campo
            
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
        return jsonify({'success': True, 'message': 'Correo enviado exitosamente'})
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
            'destinatario': nombre_destino,
            'correo': correo_destino,
            'mensaje': mensaje_adicional
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
    # Usar el teléfono del ticket si existe, si no, usar el número proporcionado en el formulario
    numero_destino = ticket.telefono or request.form.get('numero_destino')
    mensaje = request.form.get('mensaje')
    
    try:
        # Verificar si hay un número de destino
        if not numero_destino:
            return jsonify({
                'success': False,
                'message': 'No hay número de teléfono asociado al ticket ni proporcionado'
            })

        # Obtener y formatear el número de origen
        numero_origen = os.getenv('TELNYX_PHONE_NUMBER')
        
        # Asegurarse de que el número existe
        if not numero_origen:
            return jsonify({
                'success': False,
                'message': 'Número de origen no configurado en variables de entorno'
            })

        # Limpiar y formatear el número de origen
        numero_origen = numero_origen.strip()
        if not numero_origen.startswith('+1'):
            numero_origen = '+1' + numero_origen.lstrip('+')

        # Limpiar y formatear el número de destino
        numero_destino = numero_destino.strip()
        # Eliminar cualquier carácter no numérico excepto el '+'
        numero_destino = ''.join(c for c in numero_destino if c.isdigit() or c == '+')
        
        # Si no empieza con +1, agregarlo
        if not numero_destino.startswith('+1'):
            # Si empieza con +, quitar el + y agregar +1
            if numero_destino.startswith('+'):
                numero_destino = '+1' + numero_destino[1:]
            # Si no empieza con +, simplemente agregar +1
            else:
                numero_destino = '+1' + numero_destino

        print(f"Enviando SMS desde: {numero_origen} a: {numero_destino}")  # Debug

        # Enviar SMS usando Telnyx
        mensaje = telnyx.Message.create(
            from_=numero_origen,
            to=numero_destino,
            text=mensaje,
            messaging_profile_id=os.getenv('TELNYX_MESSAGING_PROFILE_ID')
        )

        return jsonify({
            'success': True,
            'message': 'SMS enviado exitosamente'
        })
    except Exception as e:
        error_detail = str(e)
        if hasattr(e, 'errors'):
            error_detail = f"Full details: {e.errors}"
        print(f"Error detallado: {error_detail}")  # Debug
        return jsonify({
            'success': False,
            'message': f'Error al enviar SMS: {error_detail}'
        })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5003)
