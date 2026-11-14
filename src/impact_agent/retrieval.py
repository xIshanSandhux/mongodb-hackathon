"""Default ATLAS-2 boundary adapter; replace through RetrievalStore if needed."""

from pymongo.errors import OperationFailure

from .atlas import VECTOR_INDEX
from .models import Document


class AtlasRetrievalStore:
    def __init__(self, knowledge, index_name: str = VECTOR_INDEX):
        self.knowledge = knowledge
        self.index_name = index_name
        self._ready = False

    def _search(self, text: str, filters: Document, limit: int) -> list[Document]:
        if not self._ready:
            indexes = list(self.knowledge.list_search_indexes(name=self.index_name))
            if not any(i.get("name") == self.index_name and i.get("queryable") is True
                       and i.get("status") == "READY" for i in indexes):
                raise OperationFailure("Vector index is missing or not ready")
            self._ready = True
        return list(self.knowledge.aggregate([
            {"$vectorSearch": {"index": self.index_name, "path": "search_text",
                               "query": {"text": text}, "filter": filters,
                               "numCandidates": max(100, 20 * limit), "limit": limit}},
            {"$set": {"score": {"$meta": "vectorSearchScore"}}},
        ]))

    def search_tests(self, repo_id: str, base_sha: str, text: str, limit: int = 3) -> list[Document]:
        return self._search(text, {"repo_id": repo_id, "base_sha": base_sha, "kind": "test"}, limit)

    def search_runs(self, repo_id: str, text: str, limit: int = 3) -> list[Document]:
        return self._search(text, {"repo_id": repo_id, "kind": "pr_run"}, limit)

    def save_run(self, document: Document) -> None:
        self.knowledge.replace_one({"_id": document["_id"]}, document, upsert=True)
