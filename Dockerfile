FROM python:3.9-slim

# Install ffmpeg for video processing
RUN apt-get update && apt-get install -y ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app.py test_textclip.py /app/

EXPOSE 5000

CMD ["python", "app.py"]
