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
    result = ["${DOCKERHUB_REPO_NAME}:${tag}-torch${TORCH_VERSION}-${cuda}${EXTRA_TAG}"]
}

target "_common" {
    dockerfile = "Dockerfile"
    context = "."
    args = {
        PYTHON_VERSION     = PYTHON_VERSION
        TORCH_VERSION      = TORCH_VERSION
    }
}

target "_cu124" {
    inherits = ["_common"]
    args = {
        BASE_IMAGE         = "nvidia/cuda:12.4.1-devel-ubuntu22.04"
        CUDA_VERSION       = "cu124"
    }
}

target "_cu125" {
    inherits = ["_common"]
    args = {
        BASE_IMAGE         = "nvidia/cuda:12.5.1-devel-ubuntu24.04"
        CUDA_VERSION       = "cu125"
    }
}

target "_cu126" {
    inherits = ["_common"]
    args = {
        BASE_IMAGE         = "nvidia/cuda:12.6.3-devel-ubuntu24.04"
        CUDA_VERSION       = "cu126"
    }
}

target "_cu128" {
    inherits = ["_common"]
    args = {
        BASE_IMAGE         = "nvidia/cuda:12.8.1-devel-ubuntu24.04"
        CUDA_VERSION       = "cu128"
    }
}

target "_cu129" {
    inherits = ["_common"]
    args = {
        BASE_IMAGE         = "nvidia/cuda:12.9.1-devel-ubuntu24.04"
        CUDA_VERSION       = "cu129"
    }
}

target "_cu130" {
    inherits = ["_common"]
    args = {
        BASE_IMAGE         = "nvidia/cuda:13.0.0-devel-ubuntu24.04"
        CUDA_VERSION       = "cu130"
        TORCH_VERSION      = "2.9.0"
    }
}

target "_no_custom_nodes" {
    args = {
        SKIP_CUSTOM_NODES = "1"
    }
}

target "_base_nodes" {
    args = {
        CUSTOM_NODES_FILE = "custom_nodes_base.txt"
    }
}

# Full targets (all custom nodes)
target "full-12-4" {
    inherits = ["_cu124"]
    tags = tag("full", "cu124")
}

target "full-12-5" {
    inherits = ["_cu125"]
    tags = tag("full", "cu125")
}

target "full-12-6" {
    inherits = ["_cu126"]
    tags = tag("full", "cu126")
}

target "full-12-8" {
    inherits = ["_cu128"]
    tags = tag("full", "cu128")
}

target "full-12-9" {
    inherits = ["_cu129"]
    tags = tag("full", "cu129")
}

target "full-13-0" {
    inherits = ["_cu130"]
    tags = tag("full", "cu130")
}

# Base targets (stable custom nodes)
target "base-12-4" {
    inherits = ["_cu124", "_base_nodes"]
    tags = tag("base", "cu124")
}

target "base-12-5" {
    inherits = ["_cu125", "_base_nodes"]
    tags = tag("base", "cu125")
}

target "base-12-6" {
    inherits = ["_cu126", "_base_nodes"]
    tags = tag("base", "cu126")
}

target "base-12-8" {
    inherits = ["_cu128", "_base_nodes"]
    tags = tag("base", "cu128")
}

target "base-12-9" {
    inherits = ["_cu129", "_base_nodes"]
    tags = tag("base", "cu129")
}

target "base-13-0" {
    inherits = ["_cu130", "_base_nodes"]
    tags = tag("base", "cu130")
}

# Minimal targets without custom nodes
target "minimal-12-4" {
    inherits = ["_cu124", "_no_custom_nodes"]
    tags = tag("minimal", "cu124")
}

target "minimal-12-5" {
    inherits = ["_cu125", "_no_custom_nodes"]
    tags = tag("minimal", "cu125")
}

target "minimal-12-6" {
    inherits = ["_cu126", "_no_custom_nodes"]
    tags = tag("minimal", "cu126")
}

target "minimal-12-8" {
    inherits = ["_cu128", "_no_custom_nodes"]
    tags = tag("minimal", "cu128")
}

target "minimal-12-9" {
    inherits = ["_cu129", "_no_custom_nodes"]
    tags = tag("minimal", "cu129")
}

target "minimal-13-0" {
    inherits = ["_cu130", "_no_custom_nodes"]
    tags = tag("minimal", "cu130")
}

# slim targets removed - only full/base/minimal
