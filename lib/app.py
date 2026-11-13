from __future__ import annotations

from flask import Flask, jsonify, request

from lib.ai_client import generate_response
from lib.company_documents import COMPANY_DOCUMENTS
from lib.rag_service import build_prompt, retrieve_context, source_metadata


def create_app():
    app = Flask(__name__)

    @app.get("/api/health")
    def health_check():
        return jsonify({"status": "ok"})

    @app.post("/api/ask")
    def ask_question():
        """
        Accept a question, retrieve approved company context,
        generate a grounded response, and return source metadata.
        """

        # Read JSON safely. Invalid or missing JSON becomes None
        # instead of causing Flask to raise an exception.
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify(
                {"error": "A valid JSON body containing a query is required."}
            ), 400

        query = data.get("query")

        # The query must exist, be a string, and contain non-whitespace text.
        if not isinstance(query, str) or not query.strip():
            return jsonify(
                {"error": "Query must be a non-empty string."}
            ), 400

        query = query.strip()

        # Retrieve approved documentation that is relevant to this query.
        context_matches = retrieve_context(
            query,
            COMPANY_DOCUMENTS,
        )

        # Do not call the model when approved documentation cannot
        # support an answer.
        if not context_matches:
            return jsonify(
                {
                    "query": query,
                    "answer": (
                        "The approved company documents do not contain enough "
                        "information to answer that question."
                    ),
                    "sources": [],
                }
            ), 200

        prompt = build_prompt(query, context_matches)

        try:
            answer = generate_response(prompt)
        except RuntimeError as error:
            return jsonify(
                {
                    "error": (
                        f"Model service is currently unavailable: {error}"
                    )
                }
            ), 503

        sources = [
            source_metadata(match)
            for match in context_matches
        ]

        return jsonify(
            {
                "query": query,
                "answer": answer,
                "sources": sources,
            }
        ), 200

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)