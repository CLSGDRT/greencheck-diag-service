from flask import request, jsonify, g
from functools import wraps
from app.utils.verify_jwt import JWTVerifier

verifier = JWTVerifier()

def require_jwt(f):
    """
    Décorateur Flask pour sécuriser les endpoints via JWT.
    - Vérifie la validité du token via JWKS
    - Stocke les claims dans g.user et le token brut dans g.jwt_token
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        claims = verifier.verify_token(auth_header)
        if not claims:
            return jsonify({"error": "Unauthorized"}), 401

        g.user = claims
        g.jwt_token = auth_header
        return f(*args, **kwargs)
    return decorated
