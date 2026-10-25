"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
STOPWORDS = ["the", "is", "where", "a", "an", "of", "to", "how", "do", "i", "what", "which", "in", "does", "are", "there", "any", "these", "docs", "for", "and", "this", "that", "it", "be", "can", "if", "my", "our"]
MIN_SCORE = 1
class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)
        self.chunks = self.build_chunks(self.documents)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def build_index(self, documents):
        index = {}
        for filename, text in documents:
            words = text.lower().split()
            for word in words:
                if word not in index:
                    index[word] = []
                if filename not in index[word]:
                    index[word].append(filename)
        # print("token ->", index.get("token"))
        # print("secret ->", index.get("secret"))
        # print("database ->", index.get("database"))
        # print("total words:", len(index))
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------
    def build_chunks(self, documents):
        chunks = []
        for filename, text in documents:
            for piece in text.split("\n#"):
                if piece.strip():
                    chunks.append((filename, piece.strip()))
        return chunks
    def score_document(self, query, text):
        score = 0
        for word in query.lower().split():
            word = word.strip("?.,!")
            if word in STOPWORDS:
                continue
            if word[:6] in text.lower():
                score += 1
        return score

    def retrieve(self, query, top_k=3):
        results = []
        for filename, text in self.chunks:
            score = self.score_document(query, text)
            if score >= MIN_SCORE:
                results.append((filename, text, score))

        results.sort(key=lambda item: (-item[2], len(item[1])))

        top = []
        for filename, text, score in results[:top_k]:
            top.append((filename, text))
        return top

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
