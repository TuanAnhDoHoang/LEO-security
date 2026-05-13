# LEO Security Dashboard

A repository for the LEO security dashboard and simulation tools.

## Clone the repository

Use the repository clone command with submodules:

```bash
git clone --recurse-submodules https://github.com/TuanAnhDoHoang/LEO-security
cd LEO-security
```

## Build and run with Docker Compose

The project includes a `docker-compose.yml` and `Dockerfile` that build the dashboard container and run both the frontend and backend.

```bash
sudo docker compose up --build
```

This will:
- build the Docker image from `Dockerfile`
- install dependencies in `dashboard/`
- start the Vite frontend server on port `5173`
- start the Express/WS backend server on port `3001`

After startup, open the dashboard in your browser at:

```text
http://localhost:5173
```

## Run the dashboard locally without Docker

If you prefer local development, use the dashboard package directly.

```bash
cd dashboard
npm install
npm run dev
```

Then visit:

```text
http://localhost:5173
```

If you want frontend and backend together in development mode:

```bash
cd dashboard
npm install
npm run dev:all
```

## Build the dashboard for production

```bash
cd dashboard
npm install
npm run build
```

For a local preview after build:

```bash
npm run preview
```

## Ports

- `5173` — Vite frontend development server
- `3001` — dashboard backend / WebSocket server

## Notes

- The Docker setup uses `node:20-bullseye` and installs Python tools required by the repository.
- The dashboard service is configured to mount the repository into the container for live development.
- If you use Docker on Linux, make sure you have `docker` and `docker compose` installed and running.

## Project structure

- `dashboard/` — React + TypeScript frontend and Express/WebSocket backend
- `ddos/`, `eavesdropper/`, `jamming/`, `mitm/` — attack simulation modules and demos
- `Dockerfile` — container image for the dashboard and required Python tools
- `docker-compose.yml` — Docker Compose service definition for the dashboard
