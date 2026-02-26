from fastapi import FastAPI
from pydantic import BaseModel
from graph import ejecutable
from fastapi.middleware.cors import CORSMiddleware # IMPORTANTE

app = FastAPI(title="RAG API", version="1.0")

# --- MAGIA ANTI-CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite que cualquier HTML se conecte (ideal para desarrollo)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -----------------------

class QueryRequest(BaseModel):
    query: str
    

@app.get("/")
def home():
    return {"status": "ok", "message": "Welcome to the RAG API"}

@app.post("/query")
def handle_query(request: QueryRequest):
    query = request.query

    estado_inicial = {
        "pregunta": query
    }

    resultado_final = ejecutable.invoke(estado_inicial)
    response = resultado_final.get("respuesta", "No se pudo generar una respuesta")

    return {"response": response}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
