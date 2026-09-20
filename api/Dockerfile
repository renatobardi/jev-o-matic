FROM python:3.12-slim

# Pinado, só wheels — mesmo padrão do studio/api.
RUN pip install --no-cache-dir --only-binary :all: uv==0.12.12

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-build --no-dev

COPY src ./src
RUN uv sync --locked --no-dev \
 && useradd --create-home --uid 10001 jevomatic \
 && chown -R jevomatic:jevomatic /app
USER jevomatic

ENV PATH="/app/.venv/bin:${PATH}"
EXPOSE 8000
CMD ["uvicorn", "jevomatic_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
