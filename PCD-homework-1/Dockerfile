FROM python:3.9

WORKDIR /app

COPY . /app

RUN pip install aioquic  # Install QUIC support

CMD ["python", "server.py"]