FROM python:3.13-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV DEBUG=FALSE

EXPOSE 8000

WORKDIR /app

COPY pyproject.toml uv.lock /app/

RUN uv sync --frozen --no-dev

COPY . /app

RUN uv run python manage.py makemigrations --merge
RUN uv run python manage.py migrate --noinput
RUN uv run python manage.py collectstatic --noinput
RUN rm -rf /var/tmp/django_cache

ENTRYPOINT ["uv", "run", "python3"]

CMD ["manage.py", "runserver", "0.0.0.0:8000"]
