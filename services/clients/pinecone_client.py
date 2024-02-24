from pinecone import Pinecone
from typing import List, Dict, Any, Optional, Union

class PineconeClient:
    def __init__(self, api_key: str, index: str):
        pc = Pinecone(api_key=api_key)
        self.index = pc.Index(index)

    def upsert(self, vectors: Union[List[tuple], List[dict]], namespace: str):
        self.index.upsert(vectors=vectors, namespace=namespace)
    
    def query(self, namespace: str, query_vector: List[float], top_k: int, **kwargs):
        return self.index.query(namespace=namespace, vector=query_vector, top_k=top_k, **kwargs)
    
    def delete(self, namespace: str):
        self.index.delete(delete_all=True, namespace=namespace)
    
    def describe(self, filter: Optional[Dict[str, Union[str, float, int, bool, List, dict]]] = None):
        return self.index.describe_index_stats(filter)