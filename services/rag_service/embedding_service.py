from services.data_service import DataService, get_data_service
from services.github_service import GithubService
from services.clients.anyscale_client import AnyscaleClient
from services.clients.pinecone_client import PineconeClient
from services.rag_service.text_chunker import TextChunker
from fastapi import HTTPException, status
from schemas.documentation_generation import FirestoreDoc, FirestoreRepo,EmbeddingModelEnum, StatusEnum
from collections import deque 
from routers import utils
from dotenv import load_dotenv
import firebase_admin
import os
import asyncio


class EmbeddingService:
    def __init__(
        self, 
        embedding_client: AnyscaleClient, 
        vector_database_client: PineconeClient, 
        github_service: GithubService, 
        data_service: DataService, 
        text_chunker: TextChunker
    ):
        self.embedding_client = embedding_client
        self.vector_database_client = vector_database_client
        self.github_service = github_service
        self.data_service = data_service
        self.text_chunker = text_chunker

    async def generate_markdown_embeddings_for_repo(self, repo_id: str, user_id: str):
        namespaces = vector_database_client.describe()["namespaces"]
        if (repo_id in namespaces):
            # vector_database_client.delete(repo_id)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Repo already exists in the database, we're not going to re-embed it.")
        repo_dict = self.data_service.get_user_repo(user_id, repo_id)
        repo = FirestoreRepo(**repo_dict)
        repo_formatted = utils.format_repo(repo)

        q = deque(repo_formatted.tree)
        while q:
            node = q.popleft()
            doc = self.data_service.get_user_documentation(user_id, node.id)
            await self.generate_markdown_embeddings_for_doc(doc, repo_id)

            for child in node.children:
                if child.completion_status == StatusEnum.COMPLETED:
                    q.append(child)
    
    async def generate_markdown_embeddings_for_doc(self, doc: FirestoreDoc, repo_id: str):
        markdown = doc.markdown_content
        markdown_regex = [
            # Note that this splitter doesn't handle horizontal lines defined
            # by *three or more* of ***, ---, or ___, but this is not handled
            "",
            " ",
            "\n",
            "\n\n",
            # Horizontal lines
            "\n___+\n",
            "\n---+\n",
            "\n\\*\\*\\*+\n",
            # Note the alternative syntax for headings (below) is not handled here
            # Heading level 2
            # ---------------
            # End of code block
            "```\n",
            # First, try to split along Markdown headings (starting with level 2)
            "\n#{1,6} "
        ]

        # There is a max of 2048 embeddings that can be generated at a time, so we need to "group" the chunks
        chunks = self.text_chunker.chunk(markdown, markdown_regex)
        grouped_chunks = [chunks[i:i+2048] for i in range(0, len(chunks), 2048)]

        chunk_index = 0
        for list_of_chunks in grouped_chunks:
            embeddings = await self.embedding_client.generate_embedding(
                model=EmbeddingModelEnum.BGE_LARGE,
                input=list_of_chunks
            )
            # The embeddings.data can have up to 2048 embeddings, upserting individually is slow
            # Pinecone has a limit of 100 upserts per request, so we will "group" the vectors into groups of 100
            vectors = []
            n = len(embeddings.data)
            for i, embedding in enumerate(embeddings.data):
                vectors.append({
                    "id": doc.id + f"-{chunk_index}",
                    "values": embedding.embedding,
                    "metadata": {
                        "chunk_content": list_of_chunks[embedding.index],
                        "doc_id": doc.id,
                    }
                })
                if len(vectors) == 100 or i == n - 1:
                    self.vector_database_client.upsert(vectors, repo_id)
                    vectors = []
                chunk_index += 1
                


if __name__ == "__main__":
    load_dotenv()
    firebase_app = firebase_admin.initialize_app(
        credential=None,
        options={"storageBucket": os.getenv("CLOUD_STORAGE_BUCKET")}
    )
    anyscale_client = AnyscaleClient(api_key=os.getenv("ANYSCALE_API_KEY"))
    vector_database_client = PineconeClient(api_key=os.getenv("PINECONE_API_KEY"), index="rocketdocs-repos-1")
    github_service = GithubService(token=os.getenv("GITHUB_API_KEY"))
    data_service = get_data_service()
    text_chunker = TextChunker(chunk_size=250, chunk_minimum=50)

    embedding_service = EmbeddingService(
        embedding_client=anyscale_client,
        vector_database_client=vector_database_client,
        github_service=github_service,
        data_service=data_service,
        text_chunker=text_chunker
    )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(embedding_service.generate_markdown_embeddings_for_repo("3153f0a7-09ef-4a12-be4f-3de3b8defda3", "qZ6GC61uBPha2bbMirUy3RgY6w92"))
