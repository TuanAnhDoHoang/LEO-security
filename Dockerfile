# Use Node.js as the base image (Bullseye has better Python support)
FROM node:20-bullseye

# Install Python and necessary build tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    hping3 \
    iptables \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install cryptography

# Set the working directory
WORKDIR /app

# Copy the entire project
COPY . .

# Set up the dashboard
WORKDIR /app/dashboard
RUN npm install

# Build the frontend (optional, but good for production-ready containers)
# For this simulation, we'll stay in dev mode to support the WebSocket proxying easily
# RUN npm run build

# Expose the ports
# 5173: Vite Dev Server (Frontend)
# 3001: Express Server (Backend / WebSockets)
EXPOSE 5173 3001

# Command to run both the backend and frontend
CMD ["npm", "run", "dev:all"]
