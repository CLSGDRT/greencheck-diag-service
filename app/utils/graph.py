from langchain_ollama import ChatOllama
from pydantic import BaseModel
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
from PIL import Image
from io import BytesIO
from app.models.db import db
from app.models.models import DiagResult
import uuid
import torch
from transformers import Blip2Processor, Blip2ForConditionalGeneration

from app.utils.safe_call import SafeCall
import requests

# ---------------------------
# 1. LLM Ollama
# ---------------------------
llm = ChatOllama(model="llama3.1")
safe = SafeCall(http_timeout=15, http_retries=2, http_backoff=1.0)

# ---------------------------
# 2. Modèles Pydantic
# ---------------------------
class DiagState(BaseModel):
    image_id: str
    user_text: str
    jwt_token: str = None
    image: Image.Image = None
    image_description: str = None
    is_plant: bool = None
    score: float = None
    disease: str = None
    advice: str = None

class IsPlant(BaseModel):
    is_plant: bool

# ---------------------------
# 3. Téléchargement sécurisé
# ---------------------------
def download_image(state: DiagState) -> DiagState:
    url = f"http://image-service:8000/images/{state.image_id}/download"
    headers = {"Authorization": state.jwt_token}
    resp = safe.http_get(url, headers=headers)
    if resp is None:
        raise RuntimeError("Impossible de télécharger l'image après plusieurs tentatives")
    state.image = Image.open(BytesIO(resp.content)).convert("RGB")
    return state

# ---------------------------
# 4. Description image (BLIP-2) sécurisée
# ---------------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BLIP_MODEL_NAME = "Salesforce/blip2-opt-2.7b"

processor = Blip2Processor.from_pretrained(BLIP_MODEL_NAME)
blip_model = Blip2ForConditionalGeneration.from_pretrained(BLIP_MODEL_NAME, device_map="auto")
blip_model.to(DEVICE)

def describe_image_local(image: Image.Image) -> str:
    inputs = processor(images=image, return_tensors="pt").to(DEVICE)
    out = blip_model.generate(**inputs)
    caption = processor.decode(out[0], skip_special_tokens=True)
    return caption

def describe_image(state: DiagState) -> DiagState:
    caption = safe.run_local(describe_image_local, args=(state.image,), timeout=300, fallback="Description temporairement indisponible")
    state.image_description = caption
    return state

# ---------------------------
# 5. Vérification plante
# ---------------------------
plant_check_prompt = PromptTemplate.from_template("""
Tu es un expert en botanique. Vérifie si l'image représente bien une plante.
Répond strictement en JSON avec le champ:
- is_plant: True si c'est une plante, False sinon

Description de l'image : {image_description}
""")

def verify_is_plant(state: DiagState) -> DiagState:
    structured_llm = llm.with_structured_output(IsPlant)
    chain = plant_check_prompt | structured_llm
    result = chain.invoke({"image_description": state.image_description})
    state.is_plant = result.is_plant
    return state

# ---------------------------
# 6. Diagnostic santé + conseils
# ---------------------------
diagnosis_prompt = PromptTemplate.from_template("""
Tu es un expert botaniste. Analyse l'état de santé de la plante en te basant sur la description de l'image et le texte fourni.
Répond strictement en JSON:
- score: note de santé de la plante (0-5)
- disease: maladie identifiée si existante, sinon vide
- advice: conseils de traitement ou prévention

Description de l'image: {image_description}
Texte utilisateur: {user_text}
""")

def run_diagnosis(state: DiagState) -> DiagState:
    structured_llm = llm.with_structured_output(DiagState)
    chain = diagnosis_prompt | structured_llm
    result = chain.invoke({
        "image_description": state.image_description,
        "user_text": state.user_text
    })
    state.score = result.score
    state.disease = result.disease
    state.advice = result.advice
    return state

# ---------------------------
# 7. Persistance en DB
# ---------------------------
def persist_diagnosis(state: DiagState) -> DiagState:
    diag = DiagResult(
        id=str(uuid.uuid4()),
        image_id=state.image_id,
        user_text=state.user_text,
        score=state.score,
        disease=state.disease,
        advice=state.advice
    )
    db.session.add(diag)
    db.session.commit()
    return state

# ---------------------------
# 8. Graphe LangGraph
# ---------------------------
graph = StateGraph(DiagState)

graph.add_node("download_image", download_image)
graph.add_node("describe_image", describe_image)
graph.add_node("verify_is_plant", verify_is_plant)
graph.add_node("run_diagnosis", run_diagnosis)
graph.add_node("persist_diagnosis", persist_diagnosis)

graph.set_entry_point("download_image")
graph.add_edge("download_image", "describe_image")
graph.add_edge("describe_image", "verify_is_plant")
graph.add_edge("verify_is_plant", "run_diagnosis", lambda s: "run_diagnosis" if s.is_plant else END)
graph.add_edge("run_diagnosis", "persist_diagnosis")
graph.add_edge("persist_diagnosis", END)

assistant_graph = graph.compile()
