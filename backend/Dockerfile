FROM python:3.12-slim

WORKDIR /app

# Solo el manifiesto primero para aprovechar la cache de capas de Docker: si el codigo
# cambia pero las dependencias no, no se reinstalan.
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
