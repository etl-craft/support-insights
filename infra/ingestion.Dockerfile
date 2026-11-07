ARG PROJECT_IMAGE
FROM ghcr.io/astral-sh/uv:0.12.17@sha256:10787c682e4184e4f290de1171fd4703dc63de99221f10fe1c99002ce7fa9acc AS uv
FROM ${PROJECT_IMAGE}
USER root
COPY --from=uv /uv /tmp/uv
RUN /tmp/uv pip install --python /opt/etl-craft/bin/python --no-cache --compile-bytecode pymongo==4.18.3 confluent-kafka==2.12.2 && rm /tmp/uv
USER 10001
