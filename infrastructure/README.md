# Infrastructure Usage Guide

This document explains how to run the **CloudNativePG + pgvector** stack and the sample Python application in two environments:

1. **Local development with Minikube** – fast feedback loop, no cloud bill.
2. **Azure Kubernetes Service (AKS)** – production-like cluster, deployed via Azure CLI and GitHub Actions.

---

## 0. Prerequisites

| Tool                                                                    | Version (tested) | Purpose                         |
| ----------------------------------------------------------------------- | ---------------- | ------------------------------- |
| [Docker](https://docs.docker.com/get-docker/)                           | 24.x             | Build & run container images    |
| [Minikube](https://minikube.sigs.k8s.io/)                               | ≥ v1.32          | Local single-node Kubernetes    |
| [kubectl](https://kubernetes.io/docs/tasks/tools/)                      | ≥ v1.27          | Talk to any Kubernetes cluster  |
| [Helm](https://helm.sh/)                                                | ≥ v3.12          | Install CloudNativePG operator  |
| [Kustomize](https://kubectl.docs.kubernetes.io/installation/kustomize/) | ≥ v5.4           | Patch manifests per environment |
| [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)    | ≥ 2.55           | Interact with Azure / AKS       |
| Bash / zsh                                                              | —                | Run helper scripts              |

> ℹ️ The repo already contains a GitHub Actions workflow (`.github/workflows/deploy.yml`) that automates all AKS steps. The commands below are useful for **manual / first-time** deployment and troubleshooting.

---

## 1. Local Development with Minikube

### 1.1 Prerequisites Installation

**What is Minikube?**
Minikube is a tool that runs a single-node Kubernetes cluster locally on your machine. It's perfect for development, testing, and learning Kubernetes without needing a cloud provider.

**What is Kubernetes?**
Kubernetes (k8s) is a container orchestration platform that automates deployment, scaling, and management of containerized applications.

First, ensure you have all required tools installed:

\*\*Quick-start (Ubuntu/Debian)

If you're on Linux, run the commands below to install all prerequisites in one go:

```bash
sudo apt-get update && sudo apt-get install -y docker.io
sudo usermod -aG docker $USER && newgrp docker

curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64

curl -LO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl

curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

curl -s https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh | bash
sudo mv kustomize /usr/local/bin/

# Verify
docker --version && minikube version && kubectl version --client && helm version && kustomize version
```

For macOS and Windows users, see the official installation guides for
[Docker](https://docs.docker.com/get-docker/),
[Minikube](https://minikube.sigs.k8s.io/),
[Kubectl](https://kubernetes.io/docs/tasks/tools/),
[Helm](https://helm.sh/), and
[Kustomize](https://kubectl.docs.kubernetes.io/installation/kustomize/).

### 1.2 Start Your Local Kubernetes Cluster

Now we'll start minikube with enough resources for PostgreSQL and our application:

```bash
# Start minikube with adequate resources
# --cpus 4: Use 4 CPU cores (PostgreSQL needs good CPU)
# --memory 8g: Use 8GB RAM (PostgreSQL and containers need memory)
# --disk-size 30g: 30GB disk space for container images and data
# --driver=docker: Use Docker as the container runtime
minikube start --cpus 4 --memory 8g --disk-size 30g --driver=docker

# This might take a few minutes on first run as it downloads the Kubernetes image
```

**What just happened?**
Minikube created a virtual machine (or container) running Kubernetes on your local machine. This is your own personal Kubernetes cluster!

```bash
# Check if minikube is running
minikube status
# You should see something like:
# minikube
# type: Control Plane
# host: Running
# kubelet: Running
# apiserver: Running

# Enable storage for persistent volumes (database storage)
minikube addons enable storage-provisioner

# Enable metrics server (needed for auto-scaling)
minikube addons enable metrics-server

# Make sure kubectl talks to your minikube cluster
kubectl config use-context minikube

# Test the connection - you should see cluster info
kubectl cluster-info

# See what's running in your cluster (should be mostly empty for now)
kubectl get pods --all-namespaces
```

**Understanding what you see:**

- `kubectl` is your main tool for talking to Kubernetes
- `pods` are the smallest deployable units (think of them as containers)
- `--all-namespaces` shows you everything in the cluster

**Troubleshooting Common Issues:**

```bash
# If minikube fails to start, try:
minikube delete && minikube start --cpus 4 --memory 8g --disk-size 30g --driver=docker

# Check available drivers
minikube start --help | grep driver

# For Apple Silicon Macs, you might need:
minikube start --cpus 4 --memory 8g --disk-size 30g --driver=qemu

# Check minikube logs if issues persist
minikube logs
```

### 1.3 Install the PostgreSQL Operator

**What is an Operator?**
A Kubernetes operator is like a smart robot that knows how to manage complex applications. The CloudNativePG operator knows how to install, configure, backup, and maintain PostgreSQL databases in Kubernetes.

```bash
# Navigate to your project directory (where you cloned this repo)
cd /path/to/your/oai-coding-agent

# Run the bootstrap script to install the PostgreSQL operator
./infrastructure/scripts/bootstrap-operator.sh
```

**What this script does:**

1. Adds the CloudNativePG Helm repository (where the operator package lives)
2. Installs the operator into the `cnpg-system` namespace
3. Waits for the operator to be ready

```bash
# Verify the operator is running
kubectl get pods -n cnpg-system

# You should see something like:
# NAME                                    READY   STATUS    RESTARTS   AGE
# cloudnativepg-operator-xxxx-xxxx        1/1     Running   0          2m
```

**Understanding Namespaces:**
Namespaces are like folders in Kubernetes - they help organize resources. We're using `cnpg-system` for our PostgreSQL-related components.

### 1.4 Build and Deploy Everything

Now we'll build our Python application and deploy both PostgreSQL and the app to Kubernetes:

```bash
# First, build the Python application into a Docker image
# This creates a container image that minikube can use
docker build -t python-app:dev -f python-app/Dockerfile python-app/

# Load the image into minikube's Docker registry
# (This step is important - minikube needs access to your locally built image)
minikube image load python-app:dev

# Now deploy everything using Kustomize
# This will create: PostgreSQL cluster, Python app, pgAdmin, and all supporting resources
kubectl kustomize infrastructure/kustomize/overlays/minikube | kubectl apply -f -
```

**What just happened?**

1. **Docker build**: Created a container image with your Python app
2. **minikube image load**: Made the image available inside your minikube cluster
3. **kubectl apply**: Told Kubernetes to create all the resources defined in our configuration files

**Understanding Kustomize:**
Kustomize lets us have different configurations for different environments. The `overlays/minikube` folder contains settings specific to local development (like using hostpath storage and creating NodePort services for external access).

### 1.5 Watch Everything Come Online

Let's monitor the deployment and make sure everything starts correctly:

```bash
# Watch all pods in the cnpg-system namespace come online
# This will show you real-time status updates
kubectl get pods -n cnpg-system -w

# You should eventually see something like:
# NAME                         READY   STATUS    RESTARTS   AGE
# cloudnativepg-operator-xxx   1/1     Running   0          5m
# pg-vector-1                  1/1     Running   0          2m
# pg-vector-2                  1/1     Running   0          2m
# pg-vector-3                  1/1     Running   0          2m
# python-app-xxx-xxx           1/1     Running   0          1m
# pgadmin-xxx-xxx              1/1     Running   0          1m

# Press Ctrl+C to stop watching when everything is Running
```

**Understanding Pod Status:**

- **Pending**: Kubernetes is finding a place to run the pod
- **ContainerCreating**: Downloading and starting the container
- **Running**: Everything is working!
- **1/1 Ready**: 1 container is ready out of 1 total

### 1.6 Access Your Applications

Now let's access the applications we just deployed:

**Option 1: Using Port Forwarding (Recommended for beginners)**

```bash
# Access your Python application (in a new terminal window)
kubectl port-forward -n cnpg-system deploy/python-app 8000:8000

# Now open http://localhost:8000 in your browser
# You should see your Python application running!

# Access pgAdmin (database management UI) - in another terminal
kubectl port-forward -n cnpg-system deploy/pgadmin 8080:80

# Open http://localhost:8080 in your browser
# Login with: dev@localhost / devpass
```

**Option 2: Using NodePort Services (Direct access)**

```bash
# Get direct URLs to your services (no port-forwarding needed)
minikube service pg-vector-external -n cnpg-system --url    # PostgreSQL direct access
minikube service pgadmin-external -n cnpg-system --url      # pgAdmin web interface
minikube service python-app -n cnpg-system --url           # Python app (if you added a NodePort)

# These commands will give you URLs like http://192.168.49.2:30080
```

**Understanding the difference:**

- **Port-forwarding**: Creates a tunnel from your local machine to the pod
- **NodePort**: Exposes the service on a port on the minikube VM itself

### 1.7 Connect to Your Database

Once you have pgAdmin open (http://localhost:8080 with dev@localhost / devpass), you can connect to your PostgreSQL database:

**Setting up the database connection in pgAdmin:**

1. Click "Add New Server" or "Create" → "Server"
2. Fill in the connection details:
   - **Name**: `Local PostgreSQL` (any name you want)
   - **Host**: `pg-vector-rw` (this is the Kubernetes service name)
   - **Port**: `5432` (standard PostgreSQL port)
   - **Database**: `app_db`
   - **Username**: `app`
   - **Password**: You need to get this from Kubernetes

**Getting the database password:**

```bash
# Get the auto-generated PostgreSQL password
kubectl get secret -n cnpg-system db-user-pass -o jsonpath='{.data.password}' | base64 -d
echo  # adds a newline for readability

# Copy this password and use it in pgAdmin
```

**Useful Kubernetes Commands for Development:**

```bash
# View all resources in your namespace
kubectl get all -n cnpg-system

# Check logs if something isn't working
kubectl logs -n cnpg-system deployment/python-app
kubectl logs -n cnpg-system deployment/pgadmin

# Get detailed info about a pod
kubectl describe pod -n cnpg-system <pod-name>

# Connect directly to a running container (for debugging)
kubectl exec -it -n cnpg-system deployment/python-app -- /bin/bash
```

### 1.8 Making Changes During Development

When you modify your Python application:

```bash
# Rebuild the Docker image
docker build -t python-app:dev -f python-app/Dockerfile python-app/

# Load the new image into minikube
minikube image load python-app:dev

# Restart the deployment to use the new image
kubectl rollout restart deployment/python-app -n cnpg-system

# Watch the rollout complete
kubectl rollout status deployment/python-app -n cnpg-system
```

### 1.9 Cleaning Up

When you're done developing:

```bash
# Delete all the resources we created
kubectl delete namespace cnpg-system

# Stop minikube
minikube stop

# (Optional) Delete the minikube cluster entirely
minikube delete
```

---

## 2. Deploy to AKS (manual via Azure CLI)

> **Skip this section** if you are using the provided GitHub Actions pipeline – it performs the same steps on every push to `main`.

### 2.1 Login and set context

```bash
# Login with a user or service principal
az login            # or: az login --service-principal -u APP_ID -p PASSWORD --tenant TENANT_ID

# Set variables (replace placeholders)
export AKS_RG=<AKS_RESOURCE_GROUP>
export AKS_CLUSTER=<AKS_CLUSTER_NAME>

# Fetch kubeconfig for the current shell
az aks get-credentials --resource-group "$AKS_RG" --name "$AKS_CLUSTER" --overwrite-existing
```

### 2.2 Install CloudNativePG operator (one-time per cluster)

```bash
./infrastructure/scripts/bootstrap-operator.sh
```

### 2.3 Create a zone-redundant Premium SSD v2 StorageClass

Azure's recommended approach for stateful workloads in Production is to use Premium SSD v2 with Zone-Redundant Storage (ZRS). The overlay already contains a manifest that defines such a class (`premium-zrs`). Apply it **once per cluster**:

```bash
kubectl apply -f infrastructure/kustomize/overlays/aks/sc-azure-disk-premium-zrs.yaml
```

This will become the default StorageClass referenced by the CloudNativePG cluster and WAL volumes.

### 2.4 Provision database secrets via Azure Key Vault (mandatory)

The deployment now _always_ pulls the database password from Azure Key Vault via the CSI driver. Plain-text Kubernetes `Secret` objects are no longer created.

1. Create (or use) a Key Vault and add the secret `pg-password`:
   ```bash
   az keyvault create --name <KEYVAULT_NAME> --resource-group <RESOURCE_GROUP>
   az keyvault secret set --vault-name <KEYVAULT_NAME> --name pg-password --value <YOUR_PASSWORD>
   ```
2. Grant the AKS user-assigned managed identity `GET` access to secrets in that vault.
3. Enable the Secrets Store CSI driver addon:
   ```bash
   az aks enable-addons --addons azure-keyvault-secrets-provider --resource-group $AKS_RG --name $AKS_CLUSTER
   ```
4. Patch `infrastructure/kustomize/overlays/aks/keyvault-secretstore.yaml` with your `keyvaultName`, `tenantId`, and the `userAssignedIdentityID`

> **Note**: The Kustomize overlay now mounts the Key Vault secret into a Kubernetes secret named `db-user-pass-kv`, which is referenced by the CloudNativePG cluster spec. No manual `kubectl create secret` commands are required.

### 2.5 Build & push the Python image (GHCR)

```bash
IMAGE=ghcr.io/$(git config user.name | tr '[:upper:]' '[:lower:]')/python-app:manual

docker build -t "$IMAGE" -f python-app/Dockerfile python-app/
# Requires a GHCR PAT in $GITHUB_TOKEN
 echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USER --password-stdin

docker push "$IMAGE"
```

### 2.6 Patch image & apply manifests

```bash
OVERLAY=infrastructure/kustomize/overlays/aks

# (Optional) update the Python image tag built in the previous step
pushd "$OVERLAY"
kustomize edit set image python-app=$IMAGE
popd

# Apply everything – this will automatically pick up the Key Vault secret and ZRS storage class
kustomize build "$OVERLAY" | kubectl apply -f -
```

### 2.7 Smoke test

```bash
kubectl get pods -n cnpg-system -l app=python-app
kubectl port-forward -n cnpg-system deploy/python-app 8000:8000
curl http://localhost:8000
```

---

## 3. Deploy to AKS via GitHub Actions (CI/CD)

1. **Secrets** → _Settings → Secrets and variables → Actions_
   - `AZURE_CREDENTIALS` – output of `az ad sp create-for-rbac --sdk-auth` (JSON)
   - `PG_PASSWORD` – the Postgres password you want in prod
2. Edit `.github/workflows/deploy.yml` and set
   - `AKS_RG` – resource group
   - `AKS_CLUSTER` – cluster name
3. Push to `main`. The workflow will:
   - log in to Azure and set the AKS context
   - build & push `python-app` image to GHCR with the commit SHA tag
   - patch the Kustomize overlay with the new image + secret
   - install/upgrade the CloudNativePG operator
   - apply all manifests

Progress will appear under the **Actions** tab.

---

## 4. New Features Added

### 4.1 Enhanced Local Development

- **pgAdmin**: Web-based PostgreSQL administration tool
- **External Access**: NodePort services for direct database connections
- **Init Containers**: Automatic database migration/schema setup
- **Connection Pooling**: Environment variables for optimal database connections

### 4.2 Production Enhancements

- **Azure Key Vault**: Secure secret management for AKS deployments
- **Horizontal Pod Autoscaler**: Automatic scaling based on CPU/memory metrics
- **Improved Storage**: Fixed storage class consistency across environments

### 4.3 Monitoring & Observability

- **HPA Metrics**: CPU and memory-based scaling policies
- **Database Connection Health**: Enhanced readiness probes

## 5. Folder Reference

```
infrastructure/
├── charts/                 # Helm values override (operator)
├── kustomize/
│   ├── base/               # Core resources: Namespace, Postgres, App, pgAdmin, HPA
│   └── overlays/
│       ├── aks/            # Azure-specific: storage, topology, Key Vault integration
│       └── minikube/       # Local: hostpath storage, NodePort services
├── scripts/
│   └── bootstrap-operator.sh
└── README.md               # ← you are here
```

Enjoy hacking! If you run into issues, the operator logs are your friend:

```bash
kubectl logs -n cnpg-system deploy/cloudnativepg-operator -f
```
