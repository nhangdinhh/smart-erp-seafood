FROM python:3.10-slim
WORKDIR /app
COPY . .
EXPOSE 8069
CMD ["python3", "-m", "http.server", "8069"]