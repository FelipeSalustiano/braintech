FROM python:3.12-slim

WORKDIR /voltlens

COPY . .

RUN pip install --no-cache-dir --upgrade pip

CMD ["python"]