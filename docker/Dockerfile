FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    php-cli \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# API Key & Antigravity configuration
ENV GEMINI_API_KEY=""
ENV ANTIGRAVITY_API_KEY=""
ENV GOOGLE_API_KEY=""

# Language Linters & LSP tools
RUN pip install --no-cache-dir ruff pyright
RUN npm install -g @astrojs/check astro typescript biome

# Prepare Antigravity Plugin and Configuration directories
RUN mkdir -p /root/.gemini/config/plugins/lsp-enforcement-kit \
    /root/.gemini/antigravity-cli

WORKDIR /workspace
COPY . .

# Auto-link the plugin into global Antigravity config
RUN cp -r /workspace/plugin/lsp-enforcement-kit/* /root/.gemini/config/plugins/lsp-enforcement-kit/

CMD ["python3", "-m", "unittest", "discover", "tests", "-v"]
