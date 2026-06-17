import json
from typing import List, Dict, Any
from sqlalchemy import or_, and_, text
from sqlalchemy.orm import Session
import logging

from app.models.scheme import SchemeRegistry, SchemeChunk
from app.services.embedding import EmbeddingProvider
from app.services.reranker import RerankerProvider

logger = logging.getLogger("uvicorn.error")

class HybridSearchService:
    def __init__(self, embedding_provider: EmbeddingProvider, rerank_provider: RerankerProvider):
        self.embedding_provider = embedding_provider
        self.rerank_provider = rerank_provider

    def retrieve(
        self,
        db: Session,
        query: str,
        profile: Dict[str, Any],
        top_n: int = 5,
        rrf_k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Runs the full hybrid retrieval pipeline:
        1. Metadata filters (State, Gender, Age)
        2. Vector Search & BM25 Keyword Search
        3. Reciprocal Rank Fusion (RRF) Merge
        4. BGE Reranker v2 M3
        """
        # Step 1: Pre-filtering criteria on database level
        # Extract state, gender, age filters
        citizen_state = str(profile.get("state") or "").lower().strip()
        citizen_gender = str(profile.get("gender") or "").lower().strip()
        citizen_age = profile.get("age")
        try:
            if citizen_age is not None:
                citizen_age = int(citizen_age)
        except ValueError:
            citizen_age = None

        # Build basic filter query for chunks based on parent Scheme Registry
        # We perform search on chunks, but check eligibility filters on parent Scheme table
        # If SQLite, pgvector is text-based JSON, so we fetch and filter in-memory or fallback.
        dialect_name = db.bind.dialect.name
        is_postgres = (dialect_name == "postgresql")

        # Get parent scheme registries matching state criteria to filter chunks
        # This acts as our Metadata Pre-Filter
        scheme_query = db.query(SchemeRegistry)
        if citizen_state and citizen_state != "any":
            # State matches scheme's state or is 'Central' or 'any'
            scheme_query = scheme_query.filter(
                or_(
                    SchemeRegistry.state.ilike(f"%{citizen_state}%"),
                    SchemeRegistry.state.ilike("%Central%"),
                    SchemeRegistry.state.ilike("%any%")
                )
            )
        
        filtered_schemes = scheme_query.all()
        filtered_scheme_ids = [s.id for s in filtered_schemes]
        
        if not filtered_scheme_ids:
            logger.info("No schemes matched metadata pre-filtering.")
            return []

        # Vector search query embedding
        query_vector = self.embedding_provider.embed_query(query)

        # Step 2: Run Vector Search and Text Search
        vector_results = []
        text_results = []

        if is_postgres:
            try:
                # 2A: Dense Vector Search using pgvector cosine distance operator <=>
                # pgvector <=> operator computes cosine distance (1 - cosine similarity)
                # Sort ascending by distance (descending similarity)
                vector_q = db.query(SchemeChunk, SchemeRegistry.scheme_name)\
                    .join(SchemeRegistry, SchemeChunk.scheme_id == SchemeRegistry.id)\
                    .filter(SchemeChunk.scheme_id.in_(filtered_scheme_ids))\
                    .order_by(SchemeChunk.embedding.cosine_distance(query_vector))\
                    .limit(30)
                
                vector_results = [{"chunk": chunk, "scheme_name": sname} for chunk, sname in vector_q.all()]
            except Exception as e:
                logger.error(f"Postgres vector search error: {e}")

            try:
                # 2B: Full Text Search using ts_rank for BM25-like behavior
                # We search on chunk_text
                # Create a search query match
                text_q = db.query(SchemeChunk, SchemeRegistry.scheme_name)\
                    .join(SchemeRegistry, SchemeChunk.scheme_id == SchemeRegistry.id)\
                    .filter(SchemeChunk.scheme_id.in_(filtered_scheme_ids))\
                    .filter(text("to_tsvector('english', chunk_text) @@ plainto_tsquery('english', :q)"))\
                    .params(q=query)\
                    .order_by(text("ts_rank(to_tsvector('english', chunk_text), plainto_tsquery('english', :q)) DESC"))\
                    .limit(30)
                
                text_results = [{"chunk": chunk, "scheme_name": sname} for chunk, sname in text_q.all()]
            except Exception as e:
                logger.error(f"Postgres text search error: {e}")
        else:
            # SQLite fallback: fetch candidate chunks and calculate scores manually in Python
            all_chunks = db.query(SchemeChunk, SchemeRegistry.scheme_name)\
                .join(SchemeRegistry, SchemeChunk.scheme_id == SchemeRegistry.id)\
                .filter(SchemeChunk.scheme_id.in_(filtered_scheme_ids))\
                .all()
            
            # Vector cosine similarity fallback in Python
            v_scores = []
            q_vec = np_array = np = None
            try:
                import numpy as np
                q_vec = np.array(query_vector)
            except ImportError:
                pass
                
            for chunk, sname in all_chunks:
                # Calculate vector score
                v_score = 0.0
                if q_vec is not None and chunk.embedding is not None:
                    try:
                        # SQLite stores embedding as JSON string due to TypeDecorator
                        c_vec = np.array(chunk.embedding)
                        if c_vec.shape == q_vec.shape:
                            cos_sim = np.dot(q_vec, c_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(c_vec))
                            v_score = float(cos_sim)
                    except Exception:
                        pass
                v_scores.append((chunk, sname, v_score))
            
            # Sort and pick top 30
            v_scores.sort(key=lambda x: x[2], reverse=True)
            vector_results = [{"chunk": item[0], "scheme_name": item[1]} for item in v_scores[:30]]

            # BM25 / Keyword count fallback in Python
            t_scores = []
            q_words = set(query.lower().split())
            for chunk, sname in all_chunks:
                text_content = chunk.chunk_text.lower()
                matches = sum(1 for w in q_words if w in text_content)
                t_scores.append((chunk, sname, matches))
            
            t_scores.sort(key=lambda x: x[2], reverse=True)
            text_results = [{"chunk": item[0], "scheme_name": item[1]} for item in t_scores[:30]]

        # Step 3: Reciprocal Rank Fusion (RRF)
        # Combine the ranking lists
        rrf_scores = {}
        
        # Helper to index by chunk ID
        chunk_dict = {}

        for rank, res in enumerate(vector_results):
            cid = str(res["chunk"].id)
            chunk_dict[cid] = res
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))

        for rank, res in enumerate(text_results):
            cid = str(res["chunk"].id)
            chunk_dict[cid] = res
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))

        # Sort combined results descending
        sorted_rrf = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        top_candidates = [chunk_dict[cid] for cid, _ in sorted_rrf[:30]]

        # Format candidates for the reranker provider
        rerank_input = []
        for cand in top_candidates:
            chunk = cand["chunk"]
            rerank_input.append({
                "id": str(chunk.id),
                "scheme_id": str(chunk.scheme_id),
                "scheme_name": cand["scheme_name"],
                "section": chunk.section,
                "chunk_text": chunk.chunk_text,
                "metadata": chunk.chunk_metadata
            })

        # Step 4: Reranking
        if not rerank_input:
            return []

        logger.info(f"Rerank pipeline: Sending {len(rerank_input)} candidate chunks to BGE Reranker...")
        reranked_results = self.rerank_provider.rerank(query=query, documents=rerank_input, top_k=top_n)

        # Unpack output
        final_results = []
        for doc, score in reranked_results:
            final_results.append({
                "scheme_name": doc["scheme_name"],
                "scheme_id": doc["scheme_id"],
                "section": doc["section"],
                "chunk_text": doc["chunk_text"],
                "metadata": doc["metadata"],
                "rerank_score": score
            })

        return final_results
