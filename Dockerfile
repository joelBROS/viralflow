FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg espeak ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-render.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN mkdir -p output work/media
ENV PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "10000"]
