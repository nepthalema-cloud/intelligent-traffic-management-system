FROM python:3.11-slim

WORKDIR /app

# Install base requirements
COPY requirements/base.txt requirements/production.txt ./
RUN pip install --no-cache-dir -r production.txt

COPY pyproject.toml ./
COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
