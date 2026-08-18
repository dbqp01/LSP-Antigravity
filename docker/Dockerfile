FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    git \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --no-cache-dir ruff pyright
RUN npm install -g @astrojs/check astro typescript biome

WORKDIR /workspace
COPY . .

CMD ["python3", "-m", "unittest", "discover", "tests", "-v"]
