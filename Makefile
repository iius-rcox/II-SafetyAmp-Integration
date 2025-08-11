REGISTRY ?= iiusacr.azurecr.io
IMAGE_NAME ?= safety-amp-agent
IMAGE ?= $(REGISTRY)/$(IMAGE_NAME)
TAG ?= latest
PLATFORM ?= linux/amd64

.PHONY: build push buildx

build:
	docker build --platform=$(PLATFORM) -t $(IMAGE):$(TAG) -f Dockerfile .

push:
	docker push $(IMAGE):$(TAG)

buildx:
	docker buildx build --platform=$(PLATFORM) -t $(IMAGE):$(TAG) -f Dockerfile --push .