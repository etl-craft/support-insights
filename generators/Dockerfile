FROM python:3.11-slim-bookworm@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd
WORKDIR /app
COPY generators/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY generators/ generators/
COPY infra/entrypoint/ infra/entrypoint/
COPY project/seeds/ project/seeds/
ENV PYTHONPATH=/app/generators PYTHONUNBUFFERED=1
RUN mkdir -p /app/storage /app/logs && useradd -u 10001 generator && chown -R generator /app
USER 10001
CMD ["sh", "-c", "python generators/initialize.py && exec python infra/entrypoint/data_generator_orchestrator.py"]
