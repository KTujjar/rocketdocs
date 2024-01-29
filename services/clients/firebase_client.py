import os
from typing import Generator, Any, Dict

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import storage, firestore
from google.cloud.firestore_v1 import DocumentReference
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.cloud.firestore_v1.client import Client
from google.cloud.storage import Blob
from typing import Iterator


class FirebaseClient:
    DOCUMENTATION_COLLECTION = "documentation"
    REPO_COLLECTION = "repos"

    def __init__(self):
        self.bucket = storage.bucket()
        self.db: Client = firestore.client()

    def add_blob(self, blob_url, data: str):
        blob = self.bucket.blob(blob_url)
        blob.upload_from_string(data)

    def get_blob(self, blob_url) -> Blob:
        return self.bucket.get_blob(blob_url)
    
    def delete_blob(self, blob_url):
        self.bucket.blob(blob_url).delete()

    def get_documentation(self, doc_id) -> Dict[str, Any] | None:
        document_snapshot = self._get(self.DOCUMENTATION_COLLECTION, doc_id)

        if not document_snapshot:
            return None

        document_dict = document_snapshot.to_dict()
        document_dict["id"] = document_snapshot.id

        return document_dict

    def add_documentation(self, data) -> str:
        document_ref = self._add(
            FirebaseClient.DOCUMENTATION_COLLECTION,
            data
        )

        return document_ref.id

    def update_documentation(self, doc_id: str, data) -> None:
        self._update(
            self.DOCUMENTATION_COLLECTION,
            doc_id,
            data
        )

    def delete_documentation(self, doc_id: str) -> None:
        self._delete(
            self.DOCUMENTATION_COLLECTION, 
            doc_id
        )

    def get_repo(self, repo_id) -> Dict[str, Any]:
        repo = self._get(self.REPO_COLLECTION, repo_id)
        
        return {**repo.to_dict(), 'id': repo.id}

    def get_repos(self) -> Iterator[Dict[str, Any]]:
        repos = self._list(self.REPO_COLLECTION)
        repos_dicts = [{**repo.to_dict(), 'id': repo.id} for repo in repos]
        return repos_dicts
    
    @staticmethod
    def get_blob_url(blob_name, folder="repo") -> str:
        return f"{folder}/{blob_name}"

    def _add(self, collection_path, data) -> DocumentReference:
        collection_ref = self.db.collection(collection_path)
        update_time, document_ref = collection_ref.add(data)
        return document_ref

    def _get(self, collection_path, document_id) -> DocumentSnapshot | None:
        document_ref = self.db.collection(collection_path).document(document_id)
        document_snapshot = document_ref.get()
        if not document_snapshot.exists:
            return None
        return document_snapshot

    def _update(self, collection_path, document_id, data) -> None:
        document_ref = self.db.collection(collection_path).document(document_id)
        document_ref.update(data)

    def _delete(self, collection_path, document_id) -> None:
        document_ref = self.db.collection(collection_path).document(document_id)
        document_ref.delete()

    def _list(self, collection_path) -> Generator[DocumentSnapshot, Any, None]:
        docs = self.db.collection(collection_path)
        return docs.stream()


def get_firebase_client() -> FirebaseClient:
    return FirebaseClient()


if __name__ == "__main__":
    load_dotenv()
    firebase_app = firebase_admin.initialize_app(
        credential=None,
        options={"storageBucket": os.getenv("CLOUD_STORAGE_BUCKET")}
    )

    firebase_client = get_firebase_client()

    # Firestore
    # result = firebase_client.add_document("documentation", {"status": "IN PROGRESS"})
    # print(result)

    # Cloud Storage
    firebase_client.add_blob("/repo/something.txt", "some docs")
    # result = firebase_client.get_blob("/repo/something.txt")
    # print(result.download_as_text())
