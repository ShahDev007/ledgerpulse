FROM node:20-alpine
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
WORKDIR /app

# Workspace manifests + web/package sources for a full install (baked into the image;
# a named node_modules volume carries it forward, source is bind-mounted for hot reload).
COPY package.json pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages ./packages
RUN pnpm install

COPY apps/web ./apps/web

EXPOSE 3000
CMD ["pnpm", "--filter", "@ledgerpulse/web", "dev"]
