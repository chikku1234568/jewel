"""Local embeddings with BAAI/bge-base-en-v1.5 via fastembed (ONNX, no torch)."""

import math

_MODEL_NAME = "BAAI/bge-base-en-v1.5"


class BgeEmbedder:
    """Normalized 768-d vectors. The model downloads on first use."""

    def __init__(self) -> None:
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=_MODEL_NAME)
        vectors = []
        for raw in self._model.embed(texts):
            values = [float(item) for item in raw]
            norm = math.sqrt(sum(value * value for value in values)) or 1.0
            vectors.append([value / norm for value in values])
        return vectors
