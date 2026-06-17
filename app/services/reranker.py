from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger("uvicorn.error")

class RerankerProvider(ABC):
    @abstractmethod
    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        pass


class LocalBGERerankerProvider(RerankerProvider):
    def __init__(self):
        self.model = None
        try:
            from sentence_transformers import CrossEncoder
            logger.info("Initializing BGE-Reranker cross-encoder...")
            # Use the v2-m3 reranker
            self.model = CrossEncoder("BAAI/bge-reranker-v2-m3")
            logger.info("BGE-Reranker loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load BGE-Reranker: {e}. Falling back to simple keyword overlap reranker.")

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        if not documents:
            return []
            
        if self.model is not None:
            try:
                pairs = [[query, doc.get("chunk_text", "")] for doc in documents]
                scores = self.model.predict(pairs).tolist()
                
                # Pair documents with scores
                scored_docs = list(zip(documents, scores))
                # Sort descending by score
                scored_docs.sort(key=lambda x: x[1], reverse=True)
                return scored_docs[:top_k]
            except Exception as e:
                logger.error(f"BGE-Reranker prediction error: {e}")

        # Fallback keyword overlap ranking
        return self._fallback_rerank(query, documents, top_k)

    def _fallback_rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        query_words = set(query.lower().split())
        scored_docs = []
        for doc in documents:
            text = doc.get("chunk_text", "").lower()
            # Simple word overlap count
            overlap = sum(1 for w in query_words if w in text)
            # Normalize by query length
            score = float(overlap) / max(len(query_words), 1)
            scored_docs.append((doc, score))
            
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return scored_docs[:top_k]
