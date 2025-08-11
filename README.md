# SafetyAmp Integration

## Container build

Use a single, parameterized build:

```bash
make build REGISTRY=iiusacr.azurecr.io IMAGE_NAME=safety-amp-agent TAG=latest
```

Multi-arch build and push:

```bash
make buildx REGISTRY=iiusacr.azurecr.io IMAGE_NAME=safety-amp-agent TAG=latest PLATFORM=linux/amd64,linux/arm64
```

## Kubernetes deploy with kustomize

Update the image once in `k8s/safety-amp/kustomization.yaml` and apply:

```bash
kubectl apply -k k8s/safety-amp
```