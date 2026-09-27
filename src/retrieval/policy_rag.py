"""RAG over policy documents (docs/architecture.md § 7, prompt.md § 18).

Uses TF-IDF cosine similarity (scikit-learn, already a dependency) rather
than dense embeddings + pgvector: the project's stated stack
(docs/architecture.md § 5) proposes pgvector for this, but adding a real
embedding model here means either a paid API call (forbidden — mock mode is
mandatory, prompt.md § 52) or a local sentence-transformers model, which is a
large new dependency and download on a machine that has repeatedly hit
out-of-memory conditions in this session (docs/project-status.md §§ Phase
3-5 detail). TF-IDF is a documented, honest simplification — swapping in
pgvector + a real embedding model is a clear future step, not a fabricated
capability.

Documents live in policy_docs/*.md, all explicitly labeled SYNTHETIC in
their own header — never a real bank's policy. If no chunk clears the
similarity threshold, `retrieve` returns `None` — the caller must not invent
a policy citation (`prompt.md` § 18: "If no reliable policy source is found:
Escalate or state that the policy could not be verified").
"""

import dataclasses
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

POLICY_DOCS_DIR = Path(__file__).parent / "policy_docs"

# scikit-learn's TfidfVectorizer ships only an English stopword list —
# without filtering Spanish function words, a query sharing only words like
# "de"/"la"/"en"/"que" with a chunk can score deceptively high (verified:
# an unrelated nonsense query matched purely on function-word overlap before
# this list was added). Not exhaustive, but covers the common offenders.
_SPANISH_STOPWORDS = [
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como", "con", "contra",
    "cual", "cuando", "de", "del", "desde", "donde", "durante", "e", "el", "ella", "ellas",
    "ellos", "en", "entre", "era", "es", "esa", "esas", "ese", "eso", "esos", "esta",
    "estas", "este", "esto", "estos", "ha", "hasta", "la", "las", "le", "les", "lo", "los",
    "mas", "más", "me", "mi", "mientras", "muy", "ni", "no", "nos", "nosotros", "o", "os",
    "otra", "otras", "otro", "otros", "para", "pero", "poco", "por", "porque", "que", "quien",
    "se", "sea", "ser", "si", "sin", "sobre", "su", "sus", "tambien", "también", "te", "ti",
    "toda", "todas", "todo", "todos", "tu", "tus", "un", "una", "unas", "uno", "unos", "y",
    "ya", "yo",
]

# Below this cosine-similarity score, no chunk is considered a reliable
# match — an arbitrary but documented threshold (illustrative, not tuned
# against a labeled retrieval-quality dataset; see docs/model-evaluation.md
# § 8 for the LLM-evaluation methodology this would need before being
# trusted in a real decision path).
SIMILARITY_THRESHOLD = 0.08


@dataclasses.dataclass
class PolicyChunk:
    source_file: str
    text: str


@dataclasses.dataclass
class RetrievalResult:
    chunk: PolicyChunk
    score: float


class PolicyRAG:
    def __init__(self, docs_dir: Path = POLICY_DOCS_DIR) -> None:
        self.chunks = _load_chunks(docs_dir)
        self._vectorizer = TfidfVectorizer(stop_words=_SPANISH_STOPWORDS)
        self._matrix = self._vectorizer.fit_transform([c.text for c in self.chunks])

    def retrieve(self, query: str) -> RetrievalResult | None:
        if not self.chunks:
            return None
        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._matrix)[0]
        best_idx = int(scores.argmax())
        best_score = float(scores[best_idx])
        if best_score < SIMILARITY_THRESHOLD:
            return None
        return RetrievalResult(chunk=self.chunks[best_idx], score=best_score)


def _load_chunks(docs_dir: Path) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        # Paragraph-level chunking — simple and adequate for these short,
        # single-topic synthetic documents.
        for para in text.split("\n\n"):
            para = para.strip()
            if para and not para.startswith("<!--") and not para.startswith("#"):
                chunks.append(PolicyChunk(source_file=path.name, text=para))
    return chunks
