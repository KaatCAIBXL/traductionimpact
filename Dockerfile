# Gebruik een lichte Python-image
FROM python:3.11-slim

# Werkmap instellen
WORKDIR /app

# Vereisten installeren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-bestanden kopiëren
COPY . .

# Poort instellen
EXPOSE 8080

# Startcommando (pas aan als je FastAPI gebruikt)
CMD ["python", "app.py"]
