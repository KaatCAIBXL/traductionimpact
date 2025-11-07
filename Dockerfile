# Gebruik stabiele Python-versie
FROM python:3.12-slim

WORKDIR /app

# Installeer systeemvereisten
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Installeer Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopieer projectbestanden
COPY . .

EXPOSE 8080

ENTRYPOINT ["python", "App.py"]





