# 🚀 Deploying Satellite Crawlers for Link Profiler

This guide provides instructions on how to deploy and manage satellite crawlers for your Link Profiler system. Satellite crawlers are essential components of the distributed architecture, allowing you to scale your crawling and data aggregation capabilities horizontally.

## 🎯 What are Satellite Crawlers?

In the Link Profiler architecture, satellite crawlers are independent worker processes responsible for executing individual crawl tasks. They connect to a central Redis instance to:

*   **Fetch Jobs**: Retrieve crawl tasks from the shared job queue.
*   **Execute Crawls**: Perform web crawling, data extraction, and initial processing.
*   **Report Results**: Send processed results back to the central system via a result queue.
*   **Send Heartbeats**: Periodically report their status and health to the Job Coordinator.

By deploying multiple satellite crawlers, you can significantly increase your system's throughput, distribute the workload, and enhance resilience.

## 📋 Prerequisites

Before deploying satellite crawlers, ensure you have:

1.  **Running Link Profiler API**: Your main FastAPI application (the "Job Coordinator") must be up and running, accessible to the satellite crawlers.
2.  **Central Redis Instance**: A Redis server accessible from all satellite crawlers. This is used for job queues, results, and heartbeats.
3.  **PostgreSQL Database**: The PostgreSQL database must be accessible from the main API (Job Coordinator) for job status updates and result storage. Satellite crawlers typically do not directly access the main database for job status, but they might need it for certain data persistence (e.g., if they directly save intermediate results).
4.  **Python Environment**: Python 3.9+ installed on the deployment target.
5.  **Docker (Optional)**: For containerised deployments.
6.  **Kubernetes Cluster (Optional)**: For orchestrated deployments.

## ⚙️ Satellite Crawler Configuration

Satellite crawlers are configured primarily through **environment variables**, which are loaded by the `ConfigLoader` in your application. This allows for flexible deployment without modifying code.

The `satellite_crawler.py` script uses `Link_Profiler.config.config_loader.ConfigLoader` to read its configuration. This `ConfigLoader` automatically picks up environment variables that are prefixed with `LP_` (e.g., `LP_REDIS_URL` maps to `redis.url` in the configuration).

Here are the key environment variables you should set for each satellite crawler instance:

*   **`LP_REDIS_URL`**: The full URL to your central Redis instance (e.g., `redis://your-redis-host:6379/0`). This is critical for queue communication.
*   **`LP_SATELLITE_ID`**: A **unique identifier** for each satellite crawler instance (e.g., `satellite-us-east-1-001`). If not provided, the crawler will generate a UUID, but explicit IDs are better for monitoring.
*   **`LP_SATELLITE_HEARTBEAT_INTERVAL`**: How often (in seconds) the satellite sends a heartbeat to the Job Coordinator (default: `5`).
*   **`LP_QUEUE_JOB_QUEUE_NAME`**: The name of the Redis queue from which the satellite fetches jobs (default: `crawl_jobs`).
*   **`LP_QUEUE_RESULT_QUEUE_NAME`**: The name of the Redis queue where the satellite sends completed job results (default: `crawl_results`).
*   **`LP_QUEUE_DEAD_LETTER_QUEUE_NAME`**: The name of the Redis queue for failed or unprocessable jobs (default: `dead_letter_queue`).
*   **`LP_BROWSER_CRAWLER_ENABLED`**: Set to `true` if this satellite should perform browser-based crawling (e.g., using Playwright for JavaScript rendering). Requires Playwright browsers to be installed in the environment.
*   **`LP_BROWSER_CRAWLER_HEADLESS`**: Set to `true` for headless browser operation (recommended for servers).
*   **`LP_BROWSER_CRAWLER_BROWSER_TYPE`**: Specify the browser type (`chromium`, `firefox`, `webkit`).
*   **`LP_LOGGING_LEVEL`**: Set the logging verbosity (e.g., `INFO`, `DEBUG`, `WARNING`).
*   **`LP_REGION`**: (Optional) A region identifier for the satellite, if your application logic uses it (e.g., `us-east-1`).

## 🚀 Deployment Methods

### 1. Local/Manual Deployment (for Testing or Small Scale)

This method is suitable for quickly testing a satellite crawler or running a few instances on dedicated machines.

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/your-org/link-profiler.git
    cd link-profiler
    ```
2.  **Create Virtual Environment & Install Dependencies**:
    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    # If LP_BROWSER_CRAWLER_ENABLED is true, install Playwright browsers:
    playwright install chromium firefox webkit
    ```
3.  **Configure Environment Variables**:
    Create a `.env` file in your project root or set them directly in your shell.
    ```dotenv
    # .env example for a satellite crawler
    LP_REDIS_URL=redis://your-redis-host:6379/0
    LP_SATELLITE_ID=my-local-satellite-01
    LP_SATELLITE_HEARTBEAT_INTERVAL=5
    LP_BROWSER_CRAWLER_ENABLED=true
    LP_BROWSER_CRAWLER_HEADLESS=true
    LP_BROWSER_CRAWLER_BROWSER_TYPE=chromium
    LP_LOGGING_LEVEL=INFO
    LP_REGION=local
    ```
4.  **Set Python Path**:
    ```bash
    export PYTHONPATH=$(pwd) # macOS/Linux
    # $env:PYTHONPATH=(Get-Location).Path # PowerShell
    ```
5.  **Run the Satellite Crawler**:
    ```bash
    python Link_Profiler/queue_system/satellite_crawler.py
    ```
    You should see logs indicating the crawler connecting to Redis and waiting for jobs.

### 2. Docker Deployment (Recommended for Production)

Containerising your satellite crawlers with Docker provides consistency, isolation, and easier management.

1.  **Build the Docker Image**:
    Navigate to the `link-profiler` project root and use the provided `Dockerfile.satellite`.
    ```bash
    cd Link_Profiler/deployment/docker
    docker build -f Dockerfile.satellite -t your-docker-registry/link-profiler-satellite:latest ../../
    # Replace 'your-docker-registry' with your actual registry (e.g., ghcr.io/your-org)
    # The 'latest' tag can be replaced with a version number (e.g., v1.0.0)
    ```
2.  **Push to a Container Registry (Optional but Recommended)**:
    ```bash
    docker push your-docker-registry/link-profiler-satellite:latest
    ```
3.  **Run a Docker Container**:
    You can run individual containers or use `docker-compose` for multiple instances.
    ```bash
    docker run -d \
      --name link-profiler-satellite-01 \
      -e LP_REDIS_URL="redis://your-redis-host:6379/0" \
      -e LP_SATELLITE_ID="docker-satellite-01" \
      -e LP_BROWSER_CRAWLER_ENABLED="true" \
      -e LP_BROWSER_CRAWLER_HEADLESS="true" \
      -e LP_BROWSER_CRAWLER_BROWSER_TYPE="chromium" \
      -e LP_LOGGING_LEVEL="INFO" \
      -e LP_REGION="us-east-1" \
      your-docker-registry/link-profiler-satellite:latest
    ```
    Adjust environment variables as needed.

### 3. Kubernetes Deployment (for Scalability and Orchestration)

Kubernetes is ideal for managing a fleet of satellite crawlers, providing auto-scaling, self-healing, and load balancing.

1.  **Ensure Image is in Registry**:
    Make sure your `link-profiler-satellite` Docker image is pushed to a registry accessible by your Kubernetes cluster. Update the `image` field in `satellite-deployment.yaml`.

2.  **Create Kubernetes Secret (for sensitive environment variables)**:
    It's best practice to store sensitive information like database and Redis URLs in Kubernetes Secrets.
    ```bash
    kubectl create namespace link-profiler # If you don't have one
    kubectl create secret generic link-profiler-secrets --namespace link-profiler \
      --from-literal=redis-url="redis://your-redis-host:6379/0" \
      --from-literal=database-url="postgresql://user:password@your-db-host:5432/link_profiler_db" \
      --from-literal=auth-secret-key="your_jwt_secret_key" \
      --from-literal=monitor-password="your_monitor_user_password"
    ```
    Ensure the keys (`redis-url`, `database-url`, `auth-secret-key`, `monitor-password`) match those referenced in `satellite-deployment.yaml`.

3.  **Deploy the Satellite Crawlers**:
    Use the provided `satellite-deployment.yaml` to create a Kubernetes Deployment.
    ```bash
    kubectl apply -f Link_Profiler/deployment/kubernetes/satellite-deployment.yaml --namespace link-profiler
    ```
    This will create a Deployment named `satellite-crawlers` and the specified number of pods (default `2`).

4.  **Configure Horizontal Pod Autoscaler (HPA)**:
    The `k8s-hpa.yaml` (provided in your repository) allows Kubernetes to automatically scale the number of satellite crawler pods up or down based on CPU and memory utilization.
    ```bash
    kubectl apply -f Link_Profiler/deployment/kubernetes/k8s-hpa.yaml --namespace link-profiler
    ```
    This HPA targets the `satellite-crawlers` Deployment and will scale it between 2 and 20 replicas to maintain average CPU utilization at 70% and memory at 80%. You can adjust these thresholds and replica counts as needed.

## ✅ Verification

After deploying your satellite crawlers, you can verify their operation using several methods:

1.  **Check Satellite Crawler Logs**:
    For Docker: `docker logs <container-name>`
    For Kubernetes: `kubectl logs <pod-name> -n link-profiler`
    Look for messages indicating connection to Redis, fetching jobs, and processing tasks.

2.  **Monitor Job Coordinator Stats**:
    Access your main Link Profiler API's monitoring endpoint (requires admin authentication):
    `GET http://localhost:8000/api/queue/stats`
    Look for `active_crawlers` and `satellite_crawlers` in the response. You should see your deployed satellites listed with their unique IDs and status.

3.  **Check Mission Control Dashboard**:
    If your Mission Control Dashboard is deployed, navigate to the "Crawler Fleet" or "Mission Status" section. You should see the active satellite crawlers and their performance metrics.

4.  **Submit a Test Job**:
    Submit a simple crawl job via your API (e.g., using the `scripts/data_aggregation_examples.py` script). Observe if the job status changes from `QUEUED` to `IN_PROGRESS` and eventually `COMPLETED`, indicating that a satellite crawler picked it up.

By following these steps, you can effectively deploy and manage your satellite crawler fleet, enabling your Link Profiler system to handle large-scale data aggregation tasks.
