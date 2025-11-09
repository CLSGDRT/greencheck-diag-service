from flask import Flask, request, jsonify
from app.utils.verify_jwt import JWTVerifier
from app.utils.graph import assistant_graph, DiagState
from app.models.db import db
from app.models.models import DiagResult
from werkzeug.exceptions import BadRequest, Unauthorized, NotFound

app = Flask(__name__)
jwt_verifier = JWTVerifier()


# ---------------------------
# Route principale de diagnostic
# ---------------------------
@app.route("/diag", methods=["POST"])
def diagnose_plant():
    """
    Lance un diagnostic sur une plante à partir d'une image et d'une description utilisateur.

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

    try:
        final_state = assistant_graph.run(state)
    except Exception as e:
        return jsonify({"error": f"Erreur interne du service: {str(e)}"}), 500

    if final_state.is_plant is False:
        return jsonify({
            "image_id": final_state.image_id,
            "user_text": final_state.user_text,
            "error": "L'image ne représente pas une plante"
        }), 400

    # Création du diagnostic en base
    diag = DiagResult(
        image_id=final_state.image_id,
        user_text=final_state.user_text,
        score=final_state.score,
        disease=final_state.disease,
        advice=final_state.advice,
        user_id=jwt_claims.get("sub")  # identifiant utilisateur depuis le JWT
    )
    db.session.add(diag)
    db.session.commit()

    response = {
        "id": diag.id,
        "image_id": diag.image_id,
        "user_text": diag.user_text,
        "score": diag.score,
        "disease": diag.disease,
        "advice": diag.advice,
        "created_at": diag.created_at.isoformat()
    }

    return jsonify(response), 200


# ---------------------------
# GET /diag/<diag_id>
# ---------------------------
@app.route("/diag/<diag_id>", methods=["GET"])
def get_diag(diag_id):
    """
    Récupère un diagnostic spécifique appartenant à l'utilisateur connecté.
    """
    auth_header = request.headers.get("Authorization")
    jwt_claims = jwt_verifier.verify_token(auth_header)
    if jwt_claims is None:
        raise Unauthorized("JWT invalide ou manquant")

    user_id = jwt_claims.get("sub")

    diag = DiagResult.query.filter_by(id=diag_id, user_id=user_id).first()
    if not diag:
        raise NotFound("Diagnostic introuvable ou non autorisé")

    response = {
        "id": diag.id,
        "image_id": diag.image_id,
        "user_text": diag.user_text,
        "score": diag.score,
        "disease": diag.disease,
        "advice": diag.advice,
        "created_at": diag.created_at.isoformat()
    }
    return jsonify(response), 200


# ---------------------------
# GET /diag
# ---------------------------
@app.route("/diag", methods=["GET"])
def list_user_diags():
    """
    Liste tous les diagnostics appartenant à l'utilisateur connecté.
    """
    auth_header = request.headers.get("Authorization")
    jwt_claims = jwt_verifier.verify_token(auth_header)
    if jwt_claims is None:
        raise Unauthorized("JWT invalide ou manquant")

    user_id = jwt_claims.get("sub")

    diags = DiagResult.query.filter_by(user_id=user_id).order_by(DiagResult.created_at.desc()).all()
    results = [
        {
            "id": d.id,
            "image_id": d.image_id,
            "user_text": d.user_text,
            "score": d.score,
            "disease": d.disease,
            "advice": d.advice,
            "created_at": d.created_at.isoformat()
        }
        for d in diags
    ]

    return jsonify(results), 200


# ---------------------------
# Lancement de l'app
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
