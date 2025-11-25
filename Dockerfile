FROM python:3.11-slim

# Instalar ffmpeg (requerido por spotdl)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Crear directorio home para el usuario
RUN mkdir -p /home/spotdl/.cache /home/spotdl/.config && \
    chown -R 1000:1000 /home/spotdl

# Instalar spotdl, flask y requests
RUN pip install --no-cache-dir spotdl flask requests

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de la aplicación
COPY app.py .
COPY templates templates/

# Exponer puerto
EXPOSE 5000

# Comando para ejecutar la aplicación
CMD ["python", "app.py"]
