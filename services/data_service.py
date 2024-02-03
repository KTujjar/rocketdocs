import os
from typing import Generator, Any, Dict, List

import firebase_admin
from dotenv import load_dotenv
from fastapi import HTTPException, status
from firebase_admin import storage, firestore
from google.cloud.firestore_v1 import DocumentReference, WriteBatch
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.storage import Blob
from pydantic import BaseModel

from schemas.documentation_generation import DocStatusEnum, FirestoreDoc, FirestoreBatchOp, FirestoreBatchOpType, \
    FirestoreRepo, FirestoreQuery


class DataService:
    DOCUMENTATION_COLLECTION = "documentation"
    REPO_COLLECTION = "repos"

    def __init__(self):
        self.bucket = storage.bucket()
        self.db: Client = firestore.client()

    def get_documentation(self, doc_id) -> FirestoreDoc | None:
        document_snapshot = self._get(self.DOCUMENTATION_COLLECTION, doc_id)
        if not document_snapshot:
            return None
        document_dict = document_snapshot.to_dict()
        document_dict["id"] = document_snapshot.id
        firestore_doc = FirestoreDoc(**document_dict)
        return firestore_doc
    
    def get_user_documentation(self, user_id, doc_id) -> FirestoreDoc | None:
        doc = self._get(self.DOCUMENTATION_COLLECTION, doc_id)

        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"No documentation found with id {doc_id}.")
        
        if doc.get('owner') != user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail=f"{user_id} is not the owner of documentation with id {doc_id}.")

        documentation_dict = {**doc.to_dict(), 'id': doc.id}
        return FirestoreDoc(**documentation_dict)

    def add_documentation(self, data) -> str:
        document_ref = self._add(
            self.DOCUMENTATION_COLLECTION,
            data
        )

        document_ref.update({'id': document_ref.id})

        return document_ref.id

    def update_documentation(self, doc_id: str, data) -> None:
        self._update(
            self.DOCUMENTATION_COLLECTION,
            doc_id,
            data
        )

    def delete_documentation(self, doc_id: str) -> None:
        doc = self._get(self.DOCUMENTATION_COLLECTION, doc_id)
        if doc.get("status") == DocStatusEnum.IN_PROGRESS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Data is still being generated for this id, so it cannot be deleted yet.")
        self._delete(
            self.DOCUMENTATION_COLLECTION,
            doc_id
        )

    def delete_user_documentation(self, user_id, doc_id) -> None:
        doc = self._get(self.DOCUMENTATION_COLLECTION, doc_id)

        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"No documentation found with id {doc_id}.")
        
        if doc.get('owner') != user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail=f"{user_id} is not the owner of documentation with id {doc_id}.")

        if doc.get("status") == DocStatusEnum.IN_PROGRESS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Data is still being generated for this id, so it cannot be deleted yet.")
        self._delete(
            self.DOCUMENTATION_COLLECTION,
            doc_id
        )

    def add_repo(self, data) -> str:
        document_ref = self._add(
            self.REPO_COLLECTION,
            data
        )
        return document_ref.id

    def batch_create_repo(self, repo: FirestoreRepo) -> str:
        batch_ops = [
            FirestoreBatchOp(
                type=FirestoreBatchOpType.SET,
                reference=self.db.collection(self.REPO_COLLECTION).document(repo.id),
                data=repo.model_dump()
            )
        ]
        for doc in repo.docs:
            batch_ops.append(
                FirestoreBatchOp(
                    type=FirestoreBatchOpType.SET,
                    reference=self.db.collection(self.DOCUMENTATION_COLLECTION).document(doc.id),
                    data=doc.model_dump(exclude_unset=True)
                )
            )
        self._perform_batch(batch_ops)

        return repo.id

    def get_repo(self, repo_id) -> Dict[str, Any]:
        repo = self._get(self.REPO_COLLECTION, repo_id)
        return {**repo.to_dict(), 'id': repo.id}

    def get_repos(self) -> List[Dict[str, str]]:
        repos = self._list(self.REPO_COLLECTION)
        repos_dicts = [{**repo.to_dict(), 'id': repo.id} for repo in repos]
        return repos_dicts
    
    def get_user_repo(self, user_id, repo_id) -> Dict[str, Any]:
        repo = self._get(self.REPO_COLLECTION, repo_id)

        if not repo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"No repo found with id {repo_id}.")
        
        if repo.get('owner') != user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail=f"{user_id} is not the owner of repo with id {repo_id}.")

        return {**repo.to_dict(), 'id': repo.id}
    
    def get_user_repos(self, user_id) -> Dict[str, Any]:
        user_repo_query = self._query(self.REPO_COLLECTION, [
            FirestoreQuery(field_path="owner", op_string=FirestoreQuery.OP_STRING_EQUALS, value=user_id), # query for owner
        ])
        repos_dicts = [{**repo.to_dict(), 'id': repo.id} for repo in user_repo_query]

        return repos_dicts

    def _add(self, collection_path, data) -> DocumentReference:
        collection_ref = self.db.collection(collection_path)
        if isinstance(data, BaseModel):
            data = data.model_dump()
        update_time, document_ref = collection_ref.add(data)
        return document_ref

    def _perform_batch(self, batch_ops: List[FirestoreBatchOp]) -> None:
        batches = [batch_ops[item:item + 500] for item in range(0, len(batch_ops), 500)]
        for batch_data in batches:
            batch = self.db.batch()
            for batch_op in batch_data:
                if batch_op.type == FirestoreBatchOpType.SET:
                    batch.set(batch_op.reference, batch_op.data)
                elif batch_op.type == FirestoreBatchOpType.UPDATE:
                    batch.update(batch_op.reference, batch_op.data)
                elif batch_op.type == FirestoreBatchOpType.DELETE:
                    batch.delete(batch_op.reference)
            batch.commit()

    def _get(self, collection_path, document_id) -> DocumentSnapshot | None:
        document_ref = self.db.collection(collection_path).document(document_id)
        document_snapshot = document_ref.get()
        if not document_snapshot.exists:
            return None
        return document_snapshot

    def _update(self, collection_path, document_id, data) -> None:
        document_ref = self.db.collection(collection_path).document(document_id)
        if isinstance(data, BaseModel):
            data = data.model_dump()
        document_ref.update(data)

    def _delete(self, collection_path, document_id) -> None:
        document_ref = self.db.collection(collection_path).document(document_id)
        document_ref.delete()

    def _list(self, collection_path) -> Generator[DocumentSnapshot, Any, None]:
        docs = self.db.collection(collection_path)
        return docs.stream()
    
    def _query(self, collection_path, queries: list[FirestoreQuery]) -> list[DocumentSnapshot]:
        collection_ref = self.db.collection(collection_path)

        query = collection_ref
        for query_details in queries:
            query = query.where(filter=FieldFilter(**query_details.model_dump()))

        results = query.get()

        return results


    # Blob operations are unused for now
    def add_blob(self, blob_url, data: str):
        blob = self.bucket.blob(blob_url)
        blob.upload_from_string(data)

    def get_blob(self, blob_url) -> Blob:
        return self.bucket.get_blob(blob_url)

    def delete_blob(self, blob_url):
        self.bucket.blob(blob_url).delete()

    @staticmethod
    def get_blob_url(blob_name, folder="repo") -> str:
        return f"{folder}/{blob_name}"


def get_data_service() -> DataService:
    return DataService()


if __name__ == "__main__":
    load_dotenv()
    firebase_app = firebase_admin.initialize_app(
        credential=None,
        options={"storageBucket": os.getenv("CLOUD_STORAGE_BUCKET")}
    )

    data_service = get_data_service()

    # Firestore
    # result = firebase_client.add_document("documentation", {"status": "IN PROGRESS"})
    # print(result)

    # Cloud Storage
    data_service.add_blob("/repo/something.txt", "some docs")
    # result = firebase_client.get_blob("/repo/something.txt")
    # print(result.download_as_text())
