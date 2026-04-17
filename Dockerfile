FROM python:3.15.0a8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY bridge.py ./bridge.py

RUN useradd --create-home --uid 1000 bridge && chown -R bridge:bridge /app

USER bridge

CMD ["python", "bridge.py"]
