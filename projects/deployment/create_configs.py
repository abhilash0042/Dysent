"""
Phase 12: Production Deployment Configuration

Docker and Kubernetes deployment configurations for FL-DDoS system.
"""

# Dockerfile
DOCKERFILE = """FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose ports
EXPOSE 8000 5000

# Environment
ENV PYTHONUNBUFFERED=1

# Run FL server
CMD ["python", "projects/fl/aggregation_server.py"]
"""

# docker-compose.yml
DOCKER_COMPOSE = """version: '3.8'

services:
  fl-server:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FL_MODE=server
      - NUM_ROUNDS=20
    volumes:
      - ./data:/app/data
      - ./models:/app/models
    networks:
      - fl-network

  fl-node-1:
    build: .
    environment:
      - FL_MODE=node
      - NODE_ID=node1
      - SERVER_URL=fl-server:8000
    depends_on:
      - fl-server
    networks:
      - fl-network

  fl-node-2:
    build: .
    environment:
      - FL_MODE=node
      - NODE_ID=node2
      - SERVER_URL=fl-server:8000
    depends_on:
      - fl-server
    networks:
      - fl-network

  dashboard:
    build: .
    command: python projects/dashboard/app.py
    ports:
      - "5000:5000"
    networks:
      - fl-network

networks:
  fl-network:
    driver: bridge
"""

# Kubernetes deployment
K8S_DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: fl-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: fl-server
  template:
    metadata:
      labels:
        app: fl-server
    spec:
      containers:
      - name: fl-server
        image: fl-ddos:latest
        ports:
        - containerPort: 8000
        env:
        - name: FL_MODE
          value: "server"
---
apiVersion: v1
kind: Service
metadata:
  name: fl-server-service
spec:
  selector:
    app: fl-server
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: LoadBalancer
"""

def create_deployment_files():
    """Create deployment configuration files"""
    print("="*70)
    print("CREATING DEPLOYMENT CONFIGURATIONS")
    print("="*70)
    
    import os
    
    # Create directories
    os.makedirs('docker', exist_ok=True)
    os.makedirs('k8s', exist_ok=True)
    
    # Write Dockerfile
    with open('docker/Dockerfile', 'w') as f:
        f.write(DOCKERFILE)
    print("✓ Created docker/Dockerfile")
    
    # Write docker-compose
    with open('docker/docker-compose.yml', 'w') as f:
        f.write(DOCKER_COMPOSE)
    print("✓ Created docker/docker-compose.yml")
    
    # Write K8s deployment
    with open('k8s/deployment.yaml', 'w') as f:
        f.write(K8S_DEPLOYMENT)
    print("✓ Created k8s/deployment.yaml")
    
    print(f"\n✓ Deployment configurations created!")
    print(f"\n📝 To deploy:")
    print(f"  Docker: cd docker && docker-compose up")
    print(f"  K8s: kubectl apply -f k8s/deployment.yaml")


if __name__ == "__main__":
    create_deployment_files()
