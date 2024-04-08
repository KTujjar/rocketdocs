from services.data_service import DataService, get_data_service
from services.clients.pinecone_client import PineconeClient, get_pinecone_client
from services.clients.anyscale_client import AnyscaleClient, get_anyscale_client
from schemas.documentation_generation import EmbeddingModelEnum
from fastapi import HTTPException, status


class SearchService:
    def __init__(
        self,
        embedding_client: AnyscaleClient,
        vector_database_client: PineconeClient,
        data_service: DataService,
    ):
        self.embedding_client = embedding_client
        self.vector_database_client = vector_database_client
        self.data_service = data_service

    async def search(self, repo_id: str, query: str, top_k=4):
        # 1. Generate embedding for the query
        query_embedding = await self.embedding_client.generate_embedding(
            model=EmbeddingModelEnum.BGE_LARGE, input=query
        )

        # 2. Query the vector database
        results = self.vector_database_client.query(
            namespace=repo_id, query_vector=query_embedding.data[0].embedding, top_k=top_k, include_metadata=True
        )

        # 3. Retrieve and format the results
        formatted_results = []
        for match in results.matches:
            formatted_results.append(
                {
                    "doc_id": match.metadata["doc_id"],
                    "score": match.score,
                    "chunk_content": match.metadata["chunk_content"],
                }
            )

        return formatted_results


def get_search_service():
    embedding_client = get_anyscale_client()
    vector_database_client = get_pinecone_client()
    data_service = get_data_service()
    return SearchService(embedding_client, vector_database_client, data_service)