FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY bridge.py ./bridge.py

RUN useradd --create-home --uid 1000 bridge && chown -R bridge:bridge /app

USER bridge

CMD ["python", "bridge.py"]