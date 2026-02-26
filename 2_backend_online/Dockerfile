# 1. Usamos una imagen oficial de Python ligera
FROM python:3.11-slim

# 2. Definimos el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Instalamos dependencias del sistema (Graphviz necesita esto a nivel sistema operativo para dibujar grafos)
RUN apt-get update && apt-get install -y \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# 4. Copiamos PRIMERO el requirements (esto optimiza la caché de Docker)
COPY requirements.txt .

# 5. Instalamos las librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiamos el resto del código de tu proyecto al contenedor
COPY . .

# 7. Exponemos el puerto que va a usar FastAPI
EXPOSE 8000

# 8. El comando para arrancar la API cuando el contenedor se levante
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]