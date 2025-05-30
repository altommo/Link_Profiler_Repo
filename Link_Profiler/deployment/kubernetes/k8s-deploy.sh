# k8s-namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: link-profiler

---
# k8s-redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: link-profiler
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        command: ["redis-server", "--appendonly", "yes"]
        volumeMounts:
        - name: redis-storage
          mountPath: /data
      volumes:
      - name: redis-storage
        persistentVolumeClaim:
          claimName: redis-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: link-profiler
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
  type: ClusterIP

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
  namespace: link-profiler
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi

---
# k8s-coordinator.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: coordinator
  namespace: link-profiler
spec:
  replicas: 1
  selector:
    matchLabels:
      app: coordinator
  template:
    metadata:
      labels:
        app: coordinator
    spec:
      containers:
      - name: coordinator
        image: linkprofiler/coordinator:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        - name: DATABASE_URL
          value: "postgresql://postgres:postgres@postgres-service:5432/link_profiler_db"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /queue/stats
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /queue/stats
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: coordinator-service
  namespace: link-profiler
spec:
  selector:
    app: coordinator
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer

---
# k8s-satellites.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: satellite-crawlers
  namespace: link-profiler
spec:
  replicas: 3  # Start with 3 satellites, can be scaled
  selector:
    matchLabels:
      app: satellite-crawler
  template:
    metadata:
      labels:
        app: satellite-crawler
    spec:
      containers:
      - name: satellite
        image: linkprofiler/satellite:latest
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        - name: REGION
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName  # Use node name as region
        - name: CRAWLER_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name  # Use pod name as crawler ID
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "300m"
        livenessProbe:
          exec:
            command:
            - python
            - -c
            - "import redis; r=redis.Redis.from_url('redis://redis-service:6379'); r.ping()"
          initialDelaySeconds: 30
          periodSeconds: 30

---
# k8s-hpa.yaml - Horizontal Pod Autoscaler for satellites
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: satellite-hpa
  namespace: link-profiler
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: satellite-crawlers
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80

---
# k8s-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: crawler-config
  namespace: link-profiler
data:
  default-config.json: |
    {
      "max_depth": 3,
      "max_pages": 1000,
      "delay_seconds": 1.0,
      "timeout_seconds": 30,
      "respect_robots_txt": true,
      "follow_redirects": true,
      "extract_images": true,
      "extract_pdfs": false,
      "max_file_size_mb": 10
    }

---
# k8s-deploy.sh - Deployment script for Kubernetes
#!/bin/bash

echo "🚀 Deploying Link Profiler to Kubernetes..."

# Apply namespace
kubectl apply -f k8s-namespace.yaml

# Apply ConfigMap
kubectl apply -f k8s-configmap.yaml

# Deploy Redis
kubectl apply -f k8s-redis.yaml

# Wait for Redis to be ready
echo "⏳ Waiting for Redis to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/redis -n link-profiler

# Deploy coordinator
kubectl apply -f k8s-coordinator.yaml

# Wait for coordinator to be ready
echo "⏳ Waiting for coordinator to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/coordinator -n link-profiler

# Deploy satellites
kubectl apply -f k8s-satellites.yaml

# Deploy autoscaler
kubectl apply -f k8s-hpa.yaml

echo "✅ Deployment complete!"

# Get service information
echo "🌐 Getting service information..."
kubectl get services -n link-profiler

# Get pod status
echo "📊 Getting pod status..."
kubectl get pods -n link-profiler

echo "🔍 To check logs:"
echo "kubectl logs -f deployment/coordinator -n link-profiler"
echo "kubectl logs -f deployment/satellite-crawlers -n link-profiler"

echo "📈 To scale satellites:"
echo "kubectl scale deployment satellite-crawlers --replicas=10 -n link-profiler"