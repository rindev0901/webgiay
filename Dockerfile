FROM python:3.10.11-alpine AS builder

WORKDIR /app

COPY . .

RUN python -m venv venv

RUN source venv/bin/activate

RUN pip install -r requirements.txt

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
