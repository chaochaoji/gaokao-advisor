"""Unified embedding with auto GPU detection and CPU fallback."""

import os


class EmbeddingService:
    def __init__(self, mode="auto", api_key="", model="BAAI/bge-m3",
                 local_path=""):
        if mode == "auto":
            mode = self._detect_best_mode(api_key)
        self.mode = mode
        self.device_info = self._get_device_info()

        if mode == "api":
            self.backend = APIEmbeddingBackend(api_key, model)
        elif mode == "cpu":
            self.backend = LocalEmbeddingBackend(
                local_path or model, device="cpu"
            )
        else:
            self.backend = LocalEmbeddingBackend(
                local_path or model, device="cuda"
            )

    @staticmethod
    def _detect_best_mode(api_key):
        try:
            import torch
            if torch.cuda.is_available():
                return "local"
        except ImportError:
            pass
        if api_key or os.getenv("ZXF_EMBEDDING_API_KEY"):
            return "api"
        return "cpu"

    @staticmethod
    def _get_device_info():
        try:
            import torch
            if torch.cuda.is_available():
                return f"GPU: {torch.cuda.get_device_name(0)}"
            return "CPU (no GPU detected)"
        except ImportError:
            return "CPU (torch not installed)"

    def embed(self, texts):
        return self.backend.encode(texts)

    def embed_query(self, text):
        if hasattr(self.backend, "encode_query"):
            return self.backend.encode_query(text)
        return self.embed([text])[0]

# -- API Backend --
class APIEmbeddingBackend:
    def __init__(self, api_key="", model="BAAI/bge-m3"):
        self.api_key = api_key or os.getenv("ZXF_EMBEDDING_API_KEY", "")
        self.model = model
        self.base_url = "https://api.siliconflow.cn/v1"

    def encode(self, texts):
        import requests
        resp = requests.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return [d["embedding"] for d in
                sorted(data["data"], key=lambda x: x["index"])]

    def encode_query(self, text):
        return self.encode([text])[0]


# -- Local Backend (GPU or CPU) --
class LocalEmbeddingBackend:
    def __init__(self, model_name="BAAI/bge-m3", device=None):
        import torch
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model_name = model_name
        self._model = None

    def _ensure_model(self):
        if self._model is not None:
            return
        from FlagEmbedding import BGEM3FlagModel
        use_fp16 = (self.device == "cuda")
        print(f"Loading {self.model_name} on {self.device} "
              f"(fp16={use_fp16})...")
        self._model = BGEM3FlagModel(
            self.model_name,
            use_fp16=use_fp16,
            device=self.device,
        )
        print("Model loaded.")

    def encode(self, texts):
        self._ensure_model()
        result = self._model.encode(
            texts, batch_size=8 if self.device == "cpu" else 32
        )
        return result["dense_vecs"].tolist()

    def encode_query(self, text):
        return self.encode([text])[0]
