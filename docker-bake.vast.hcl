variable "DOCKERHUB_REPO_NAME" {
    default = "smyshnikof/comfyui"
}

variable "PYTHON_VERSION" {
    default = "3.13"
}
variable "TORCH_VERSION" {
    default = "2.8.0"
}

variable "EXTRA_TAG" {
    default = ""
}

function "tag" {
    params = [tag, cuda]
    result = ["${DOCKERHUB_REPO_NAME}:vast-${tag}-torch${TORCH_VERSION}-${cuda}${EXTRA_TAG}"]
}

target "_common" {
    dockerfile = "Dockerfile.vast"
    context = "."
    args = {
        PYTHON_VERSION     = PYTHON_VERSION
        TORCH_VERSION      = TORCH_VERSION
    }
}

# Vast.ai base images - using pytorch base images
# For CUDA 12.4, 12.6, 12.8
target "_cu124" {
    inherits = ["_common"]
    args = {
        BASE_IMAGE         = "vastai/pytorch:2.6.0-cuda-12.4.0-py312"
        CUDA_VERSION       = "cu124"
    }
}

target "_cu126" {
    inherits = ["_common"]
    args = {
        BASE_IMAGE         = "vastai/pytorch:2.6.0-cuda-12.6.3-py312"
        CUDA_VERSION       = "cu126"
    }
}

target "_cu128" {
    inherits = ["_common"]
    args = {
        BASE_IMAGE         = "vastai/pytorch:2.6.0-cuda-12.8.0-py312"
        CUDA_VERSION       = "cu128"
    }
}

target "_no_custom_nodes" {
    args = {
        SKIP_CUSTOM_NODES = "1"
    }
}

target "vast-12-4" {
    inherits = ["_cu124"]
    tags = tag("base", "cu124")
}

target "vast-12-6" {
    inherits = ["_cu126"]
    tags = tag("base", "cu126")
}

target "vast-12-8" {
    inherits = ["_cu128"]
    tags = tag("base", "cu128")
}

