FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-hin poppler-utils libgl1 libtesseract-dev libleptonica-dev g++ pkg-config && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY parse.py ./
COPY app ./app
ENV PORT=8080
CMD ["sh","-c","cd app && gunicorn -w 1 --threads 8 --timeout 120 -b 0.0.0.0:$PORT app:app"]
