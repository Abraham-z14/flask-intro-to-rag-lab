from __future__ import annotations

import re
from typing import Any


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "can",
    "do",
    "does",
    "for",
    "from",
    "get",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "need",
    "of",
    "on",
    "or",
    "our",
    "should",
    "so",
    "the",
    "their",
    "to",
    "use",
    "what",
    "when",
    "where",
    "who",
    "why",
    "with",
    "you",
    "your",
}


def tokenize(text: str) -> set[str]:
    """
    Convert text into a set of useful lowercase search terms.

    Common stopwords and very short tokens are removed so that
    retrieval focuses on meaningful words from the user's query.
    """
    raw_tokens = re.findall(r"[a-zA-Z0-9']+", text.lower())

    tokens = set()

    for token in raw_tokens:
        token = token.strip("'")

        if len(token) <= 1:
            continue

        if token in STOPWORDS:
            continue

        tokens.add(token)

    return tokens


def document_search_text(document: dict[str, Any]) -> str:
    """
    Combine all searchable document fields into one text value.

    This allows retrieval to consider document metadata as well as
    the main document body.
    """
    title = document.get("title", "")
    category = document.get("category", "")
    tags = " ".join(document.get("tags", []))
    text = document.get("text", "")

    return f"{title} {category} {tags} {text}"


def score_document(query: str, document: dict[str, Any]) -> dict[str, Any]:
    """
    Score a document according to keyword overlap with the query.

    Each matching term contributes one point. Matches appearing in
    the title receive an additional 0.5-point boost.
    """
    query_tokens = tokenize(query)
    document_tokens = tokenize(document_search_text(document))
    title_tokens = tokenize(document.get("title", ""))

    matched_terms = query_tokens.intersection(document_tokens)
    title_matches = query_tokens.intersection(title_tokens)

    score = len(matched_terms) + (0.5 * len(title_matches))

    return {
        "document": document,
        "score": score,
        "matched_terms": sorted(matched_terms),
    }


def retrieve_context(
    query: str,
    documents: list[dict[str, Any]],
    limit: int = 2,
    minimum_score: float = 1.0,
) -> list[dict[str, Any]]:
    """
    Return the highest-scoring relevant documents for the query.

    Documents below the minimum score are discarded so unrelated
    questions do not receive arbitrary company documentation.
    """
    scored_documents = [
        score_document(query, document)
        for document in documents
    ]

    relevant_matches = [
        match
        for match in scored_documents
        if match["score"] >= minimum_score
    ]

    relevant_matches.sort(
        key=lambda match: match["score"],
        reverse=True,
    )

    return relevant_matches[:limit]


def format_context(context_matches: list[dict[str, Any]]) -> str:
    """
    Format selected documents into a structured block for the model.
    """
    if not context_matches:
        return "No relevant context was found in the approved company documents."

    blocks = []

    for match in context_matches:
        document = match["document"]

        block = (
            f"Source ID: {document['id']}\n"
            f"Title: {document['title']}\n"
            f"Category: {document['category']}\n"
            f"Content: {document['text']}"
        )

        blocks.append(block)

    return "\n\n---\n\n".join(blocks)


def build_prompt(query: str, context_matches: list[dict[str, Any]]) -> str:
    """
    Build a grounded prompt containing instructions, retrieved context,
    the user's question, and response requirements.
    """
    context = format_context(context_matches)

    return (
        "Instructions:\n"
        "Use only the approved company documentation provided in the Context section.\n"
        "Do not invent facts, policies, procedures, or requirements that are not supported "
        "by the provided context.\n"
        "If the context does not support a claim, do not include that claim.\n\n"
        "Context:\n"
        f"{context}\n\n"
        "Question:\n"
        f"{query}\n\n"
        "Response requirements:\n"
        "Answer the user's question clearly and concisely using the provided context.\n"
        "Keep the answer grounded in the approved documentation."
    )


def source_metadata(match: dict[str, Any]) -> dict[str, str]:
    """
    Return only source metadata that is safe to expose to API clients.
    """
    document = match["document"]

    return {
        "id": document["id"],
        "title": document["title"],
    }