from flask import Flask, request, jsonify
from app.utils.verify_jwt import JWTVerifier
from app.utils.graph import assistant_graph, DiagState
from werkzeug.exceptions import BadRequest, Unauthorized

app = Flask(__name__)
jwt_verifier = JWTVerifier()

# ---------------------------
# Route principale de diagnostic
# ---------------------------
@app.route("/diag", methods=["POST"])
def diagnose_plant():
    """
    JSON attendu:
    {
        "image_id": "<uuid de l'image>",
        "user_text": "<texte de l'utilisateur>"
    }

    Header:
        Authorization: Bearer <jwt_token>
    """
    auth_header = request.headers.get("Authorization")
    jwt_claims = jwt_verifier.verify_token(auth_header)
    if jwt_claims is None:
        raise Unauthorized("JWT invalide ou manquant")

    data = request.get_json()
    if not data or "image_id" not in data or "user_text" not in data:
        raise BadRequest("Champs 'image_id' et 'user_text' requis")

    # Initialisation de l'état du graphe
    state = DiagState(
        image_id=data["image_id"],
        user_text=data["user_text"],
        jwt_token=auth_header
    )

    # Exécution du graphe LangGraph
    try:
        final_state = assistant_graph.run(state)
    except Exception as e:
        return jsonify({"error": f"Erreur interne du service: {e}"}), 500

    # Si la vérification plante échoue
    if final_state.is_plant is False:
        return jsonify({
            "image_id": final_state.image_id,
            "user_text": final_state.user_text,
            "error": "L'image ne représente pas une plante"
        }), 400

    # Réponse finale
    response = {
        "image_id": final_state.image_id,
        "user_text": final_state.user_text,
        "score": final_state.score,
        "disease": final_state.disease,
        "advice": final_state.advice
    }

    return jsonify(response), 200


# ---------------------------
# Lancement de l'app
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
