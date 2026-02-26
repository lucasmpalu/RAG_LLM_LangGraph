# ==========================================
# PARCHE ANTI-FIREWALL (A PRUEBA DE REINICIOS)
# Este codigo es para evitar errores de SLL al hacer llamadas a OpenAI 
# ya que estoy usando la computadora de la empresa que tiene firewall. 
# Si estás corriendo este código en tu computadora personal, no deberías necesitar este parche.
# ==========================================
import urllib3
from urllib3.connectionpool import HTTPSConnectionPool
import os
import httpx

os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
urllib3.disable_warnings()

# El candado: Si ya está parchado, no lo vuelve a parchar
if not hasattr(HTTPSConnectionPool, "_ya_parchado"):
    orig_init = HTTPSConnectionPool.__init__
    def patched_init(self, *args, **kwargs):
        kwargs['cert_reqs'] = 'CERT_NONE'
        kwargs['assert_hostname'] = False
        orig_init(self, *args, **kwargs)
    HTTPSConnectionPool.__init__ = patched_init
    HTTPSConnectionPool._ya_parchado = True # Cerramos el candado
cliente_sin_ssl = httpx.Client(verify=False)


from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from ddgs import DDGS
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import StrOutputParser
import graphviz # Para visualizar el grafo (opcional)
import yaml

# ==============================================================================================================

# Inyección de las API Keys
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)
os.environ["OPENAI_API_KEY"] = config["OPENAI_API_KEY"]
os.environ["PINECONE_API_KEY"] = config["PINECONE_API_KEY"]

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, http_client=cliente_sin_ssl)
contenido_RAG = "casos clínicos, sintomas, diagnosticos y que forma confirmación por imágenes se recomienda para cada caso clínico"


# ==============================================================================================================

class State(TypedDict):
    """Definimos la estructura de nuestro estado (memoria) usando TypedDict para tipado fuerte."""
    pregunta: str
    contenidoInternet: str
    contenidoRAG: str
    historial: list 
    respuesta: str
    next_step: str

# ==============================================================================================================

def recibe_pregunta(state: State) -> State:

    if not state.get("historial"):
        state["historial"] = []
    
    state["historial"].append(f"Pregunta: {state['pregunta']}")
    print(f"Pregunta recibida: {state['pregunta']}, historial actualizado: {state['historial']}")
    return state

def decision(state: State) -> str:
    

    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", '''Eres un asistente inteligente que decide la mejor estrategia para responder a una pregunta.
        Tienes tres opciones: buscar en internet, buscar en una base de datos RAG o generar una respuesta directa utilizando un modelo de IA. 
        Basas tu decisión en la pregunta recibida.
        En nuestro RAG tenemos información sobre {explicacion_contenido_RAG}, pero no sobre cultura pop o eventos actuales.
        Responde ÚNICAMENTE con una de estas tres opciones: 
         "buscar_en_internet" si es una pregunta que no está en el RAG, 
         "buscar_en_rag" si el contenido puede estar en el RAG el cual contiene las siguientes informaciones {explicacion_contenido_RAG}, o 
         "consultar_llm" si no es una pregunta que tiene que ver con el contenido del RAG ni es algo que se precise buscar en internet.
          No agregues puntos, ni texto extra.'''),
        ("assistant", "Historial de la conversación hasta ahora: {historial}"),
        ("user", "Última pregunta: {pregunta}")
    ])

    # También podria definir de forma específica si la pregunta tiene ciertas palabras clave relacionadas con el RAG
    # podría hacer un if "sintoma" in pregunta_usuario or "diagnostico" in pregunta_usuario or "caso clinico" in pregunta_usuario: 
    # y el "next_step" lo seteo directamente sin necesidad de llamar al LLM

    # También podría realizar un RAG "ElasticSearch" adicional para mas contexto a la hora de tomar la decisión,
    # o dependiendo palabras claves en la pregunta, podría recuperar datos del RAG "ElasticSearch" y no de "Pinecone".

    chain = chat_prompt | llm | StrOutputParser() 

    pregunta_usuario = state["pregunta"]

    respuesta = chain.invoke({
        "pregunta": pregunta_usuario, 
        "explicacion_contenido_RAG": contenido_RAG,
        "historial": "\n".join(state.get("historial", "No hay historial previo hasta ahora"))
    })

    print(f"Respuesta de la decisión: {respuesta}")
    print("    ")

    return {"next_step": respuesta.strip('"')}

def buscar_en_rag(state: State) -> State:
    from pinecone import Pinecone
    from langchain_pinecone import PineconeVectorStore
    from langchain_openai import OpenAIEmbeddings

    pinecone_client = Pinecone()
    indice = pinecone_client.Index("my-first-rag")
    cliente_sin_ssl = httpx.Client(verify=False)

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small", 
        http_client=cliente_sin_ssl
    )

    query_vector = embeddings.embed_query(state["pregunta"])
    
    # pasar pregunta del usuario a vector embedding
    respuesta_pinecone = indice.query(
    vector=query_vector, 
    top_k=1,              
    include_metadata=True
    )

    documentos_recuperados = respuesta_pinecone.get("matches", [])
    state["contenidoRAG"] = "\n".join([doc["metadata"]["text"] for doc in documentos_recuperados if "metadata" in doc])    
    print(f"Documentos recuperados del RAG: {state['contenidoRAG']}")
    print("    ")
    return state

def buscar_en_internet(state: State) -> State:
    query = state["pregunta"]
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=3))
    contenido_internet = "\n".join([result["title"] + ": " + result["href"] for result in results]) 
    state["contenidoInternet"] = contenido_internet
    print(f"Resultados de la búsqueda en internet: {state['contenidoInternet']}")
    print("    ") 
    return state



def consultar_llm(state: State) -> State:
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "Eres un asistente inteligente que responde preguntas utilizando tu conocimiento previo."),
        ("user", "Pregunta: {pregunta}"),
        ("assistant", "Historial de la conversación hasta ahora: {historial}")

    ])
    
    chain = prompt_template | llm | StrOutputParser()

    respuesta = chain.invoke({"pregunta": state["pregunta"], "historial": "\n".join(state["historial"])})

    state["respuesta"] = respuesta
    
    return state

def sintetizar_respuesta(state: State) -> State:
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "Eres un asistente inteligente que sintetiza respuestas finales a partir de toda la información disponible."),
        ("user", "Pregunta: {pregunta}\nContexto RAG: {contenidoRAG}\nContexto Internet: {contenidoInternet}\nHistorial: {historial}")
    ])
    
    chain = prompt_template | llm | StrOutputParser()
    
    respuesta = chain.invoke({
        "pregunta": state["pregunta"],
        "contenidoRAG": state.get("contenidoRAG", ""),
        "contenidoInternet": state.get("contenidoInternet", ""),
        "historial": "\n".join(state["historial"])
    })

    
    state["respuesta"] = respuesta

    return state

def responder(state: State) -> State:

    respuesta_final = state.get("respuesta", "Sin respuesta")
    state["historial"].append(f"Respuesta: {respuesta_final}")
    return state

# ==============================================================================================================

graph = StateGraph(State)

# ==============================================================================================================

graph.add_node("recibe_pregunta", RunnableLambda(recibe_pregunta))
graph.add_node("decision", RunnableLambda(decision))
graph.add_node("buscar_en_internet", RunnableLambda(buscar_en_internet))
graph.add_node("buscar_en_rag", RunnableLambda(buscar_en_rag))
graph.add_node("consultar_llm", RunnableLambda(consultar_llm))
graph.add_node("sintetizar_respuesta", RunnableLambda(sintetizar_respuesta))
graph.add_node("responder", RunnableLambda(responder))

# ==============================================================================================================

graph.set_entry_point("recibe_pregunta")
graph.add_edge("recibe_pregunta", "decision")
graph.add_conditional_edges(
    "decision",
lambda state: state["next_step"], # variable temporal que contiene la respuesta del LLM indicando la siguiente acción a tomar
    {   "consultar_llm": "consultar_llm",
        "buscar_en_internet": "buscar_en_internet",
        "buscar_en_rag": "buscar_en_rag",
    }
)
graph.add_edge("consultar_llm", "responder")
graph.add_edge("buscar_en_internet", "sintetizar_respuesta")
graph.add_edge("buscar_en_rag", "sintetizar_respuesta")
graph.add_edge("sintetizar_respuesta", "responder")
graph.add_edge("responder", END)

# ==============================================================================================================

ejecutable = graph.compile()

# ==============================================================================================================

