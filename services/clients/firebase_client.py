import os
from typing import Generator, Any

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import storage, firestore
from google.cloud.firestore_v1 import DocumentReference
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.cloud.firestore_v1.client import Client
from google.cloud.storage import Blob



class FirebaseClient:
    TEST_COLLECTION = "documentation"

    def __init__(self):
        self.bucket = storage.bucket()
        self.db: Client = firestore.client()

    def add_document(self, collection_name, data) -> DocumentReference:
        collection_ref = self.db.collection(collection_name)

        print(data)
        update_time, document_ref = collection_ref.add(data)
        return document_ref

    def get_document(self, collection_name, document_id) -> DocumentSnapshot | None:
        document_ref = self.db.collection(collection_name).document(document_id)
        document_snapshot = document_ref.get()
        if not document_snapshot.exists:
            return None
        return document_snapshot

    def update_document(self, collection_name, document_id, data) -> None:
        document_ref = self.db.collection(collection_name).document(document_id)
        document_ref.update(data)

    def delete_document(self, collection_name, document_id) -> None:
        document_ref = self.db.collection(collection_name).document(document_id)
        document_ref.delete()

    def get_collection(self, collection_name) -> Generator[DocumentSnapshot, Any, None]:
        docs = self.db.collection(collection_name)
        return docs.stream()

    def add_blob(self, blob_url, data):
        blob = self.bucket.blob(blob_url)
        blob.upload_from_string(data)

    def get_blob(self, blob_url) -> Blob:
        return self.bucket.get_blob(blob_url)
    
    def get_blob_url(self, blob_name, folder="repo") -> str:
        return f"/{folder}/{blob_name}"



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
