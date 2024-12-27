# Sistema de Gestión de Tickets

Un sistema simple para gestionar tickets de soporte, construido con Flask.

## 🚀 ¿Qué puedes hacer con esta aplicación?

- Crear y gestionar tickets de soporte
- Ver el estado de tus tickets (Nuevo ➡️ En Progreso ➡️ Resuelto ➡️ Cerrado)
- Recibir notificaciones por correo cuando hay actualizaciones
- Duplicar tickets existentes
- Acceder desde cualquier dispositivo (diseño responsivo)

## 📋 Antes de empezar necesitas:

1. Python 3.9 o más reciente
2. Una cuenta de Gmail
3. (Opcional) Docker y Docker Compose si quieres usar contenedores

## 🔧 Guía de Instalación

### Opción 1: Instalación Simple (Sin Docker)

1. **Descarga el proyecto**
   ```bash
   git clone <url-del-repositorio>
   cd <nombre-del-proyecto>
   ```

2. **Prepara tu entorno**
   ```bash
   # En Windows:
   python -m venv venv
   venv\Scripts\activate

   # En Mac/Linux:
   python -m venv venv
   source venv/bin/activate
   ```

3. **Instala lo necesario**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configura tu correo**
   - Crea un archivo llamado `.env` con:
   ```env
   FLASK_DEBUG=True
   
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   MAIL_USERNAME=tu.correo@gmail.com
   MAIL_PASSWORD=tu_contraseña_de_aplicacion
  
   SQLALCHEMY_DATABASE_URI=sqlite:///tickets.db
   ```

5. **¡Inicia la aplicación!**
   ```bash
   python app.py
   ```

### Opción 2: Usando Docker (Más avanzado)

1. **Descarga el proyecto** (igual que arriba)

2. **Configura tu correo** (igual que arriba)

3. **Construye y ejecuta con Docker**
   ```bash
   docker-compose build
   docker-compose up
   ```

## 📱 Usar la Aplicación

1. Abre tu navegador
2. Ve a: `http://localhost:5003`
3. ¡Listo! Ya puedes crear tu primer ticket

## 🔒 Configurar Gmail

1. Ve a tu cuenta de Gmail
2. Activa la verificación en dos pasos
3. Genera una "Contraseña de aplicación"
4. Usa esa contraseña en tu archivo `.env`

## 📁 Estructura de Archivos

```
tu_proyecto/
├── app.py              # Código principal
├── requirements.txt    # Dependencias
├── templates/         
│   └── index.html     # Página principal
├── Dockerfile         # Para Docker
└── docker-compose.yml # Para Docker
```

## Pruebas con CURL
--Windows 
Invoke-WebRequest -Method POST -Uri "http://localhost:5004/webhook/sms" -ContentType "application/json" -Body '{"data":{"event_type":"message.received","occurred_at":1710817200,"payload":{"text":"Este es un mensaje de prueba","from":{"phone_number":"+34600000000"}}}}'

--Linux/Mac
curl -X POST -H "Content-Type: application/json" -d '{"data":{"event_type":"message.received","occurred_at":1710817200,"payload":{"text":"Este es un mensaje de prueba","from":{"phone_number":"+34600000000"}}}}' http://localhost:5004/webhook/sms



## ❗ Solución de Problemas Comunes

1. **Error de correo**: Verifica que usaste la contraseña de aplicación de Gmail
2. **Error al iniciar**: Asegúrate de que el puerto 5003 está libre
3. **Dependencias**: Si hay errores, ejecuta `pip install -r requirements.txt` nuevamente

## 🤝 ��Quieres Contribuir?

1. Haz un fork del proyecto
2. Crea tu rama (`git checkout -b mejora/NuevaFuncion`)
3. Sube tus cambios (`git commit -m 'Agregué una nueva función'`)
4. Envía un Pull Request

## 📄 Licencia

Este proyecto usa la licencia MIT - mira el archivo [LICENSE](LICENSE) para detalles