FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY lirix ./lirix
COPY examples ./examples
COPY tests ./tests
COPY mantle_TT ./mantle_TT

RUN python -m pip install --upgrade pip \
    && python -m pip install -e ".[dev]" streamlit

EXPOSE 7860

CMD ["streamlit", "run", "mantle_TT/app.py", "--server.address=0.0.0.0", "--server.port=7860"]
