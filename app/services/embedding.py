from abc import ABC, abstractmethod
from typing import List
import logging
import numpy as np

logger = logging.getLogger("uvicorn.error")

class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass


class LocalBGEM3EmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self.model = None
        self.dimension = 1024
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Initializing BGE-M3 SentenceTransformer...")
            self.model = SentenceTransformer("BAAI/bge-m3")
            logger.info("BGE-M3 SentenceTransformer loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load BGE-M3 SentenceTransformer: {e}. Falling back to mock embeddings.")

    def embed_query(self, text: str) -> List[float]:
        if self.model is not None:
            try:
                embedding = self.model.encode(text, normalize_embeddings=True)
                return embedding.tolist()
            except Exception as e:
                logger.error(f"BGE-M3 embedding error: {e}")
        
        # Mock embedding fallback (1024 dimensions)
        return self._generate_mock_embedding(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if self.model is not None:
            try:
                embeddings = self.model.encode(texts, normalize_embeddings=True)
                return embeddings.tolist()
            except Exception as e:
                logger.error(f"BGE-M3 batch embedding error: {e}")
        
        return [self._generate_mock_embedding(t) for t in texts]

    def _generate_mock_embedding(self, text: str) -> List[float]:
        # Generate a deterministic pseudo-random embedding based on text hash
        val = hash(text) % 1000
        np.random.seed(val)
        vec = np.random.randn(self.dimension)
        vec /= np.linalg.norm(vec)
        return vec.tolist()


class BedrockEmbeddingProvider(EmbeddingProvider):
    def __init__(self, region_name: str = "us-east-1"):
        self.region_name = region_name
        self.client = None
        try:
            import boto3
            self.client = boto3.client("bedrock-runtime", region_name=region_name)
        except Exception as e:
            logger.error(f"Failed to initialize AWS Bedrock client: {e}")

    def embed_query(self, text: str) -> List[float]:
        if not self.client:
            raise RuntimeError("Bedrock client not initialized")
        import json
        body = json.dumps({"inputText": text})
        response = self.client.invoke_model(
            modelId="amazon.titan-embed-text-v1",
            contentType="application/json",
            accept="application/json",
            body=body
        )
        response_body = json.loads(response.get("body").read())
        # Titan outputs 1536 dim; padding/truncation can be handled or we adapt to titan's dimensions
        return response_body.get("embedding")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(t) for t in texts]
