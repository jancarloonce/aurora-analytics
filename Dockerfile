FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY base.py config.py ingester.py dashboard.py ./
COPY sources/ sources/
COPY publishers/ publishers/

RUN useradd --system --no-create-home appuser
USER appuser

CMD ["python", "ingester.py"]
