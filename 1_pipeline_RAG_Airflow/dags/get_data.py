from langchain_community.document_loaders import PyMuPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore # <--- ESTA ES LA LÍNEA QUE CAMBIA
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import time
import numpy as np
from pinecone import Pinecone
import yaml

# Apunta a la carpeta donde está get_data.py (dags)
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
# Apunta a la carpeta superior (1_pipeline_offline)
PROJECT_DIR = os.path.dirname(BASE_DIR)

pdf_directory = os.path.join(BASE_DIR, 'pdfs')
processed_pdfs_file = os.path.join(BASE_DIR, 'processed_pdfs.txt')
new_pdfs_file = os.path.join(BASE_DIR, 'new_pdfs.txt')

def check_new_pdfs():
    if not os.path.exists(pdf_directory):
        print(f"El directorio '{pdf_directory}' no existe. Creándolo...")
        os.makedirs(pdf_directory)

    if os.path.exists(processed_pdfs_file):
        with open(processed_pdfs_file, 'r') as f:
            processed_pdfs = set(line.strip() for line in f)
    else:
        processed_pdfs = set()

    pdf_files = [f for f in os.listdir(pdf_directory) if f.endswith('.pdf')]
    new_pdfs = [pdf for pdf in pdf_files if pdf not in processed_pdfs]

    if new_pdfs:
        print(f"Nuevos PDFs encontrados: {new_pdfs}")
    else:
        print("No se encontraron nuevos PDFs")


def extract_new_pdfs(index, **kwargs):
    
    # ------------------------------------------------------------------
    # BLOQUE DE CODIGO PARA HACER FUNCIONAL LA APP POR FALTA DE PERMISOS
    import urllib3
    from urllib3.connectionpool import HTTPSConnectionPool
    urllib3.disable_warnings()
    orig_init = HTTPSConnectionPool.__init__
    def patched_init(self, *args, **kwargs):
        kwargs['cert_reqs'] = 'CERT_NONE'
        kwargs['assert_hostname'] = False
        orig_init(self, *args, **kwargs)
    HTTPSConnectionPool.__init__ = patched_init
    import httpx
    cliente_sin_ssl = httpx.Client(verify=False)
    # ------------------------------------------------------------------
    
    import os
    api_key = os.getenv("PINECONE_API_KEY")
    pinecone = Pinecone(api_key=api_key)
    index_pinecone = pinecone.Index(index)
    
    documents  = []

    procesados = ""
    if os.path.exists(processed_pdfs_file):
        with open(processed_pdfs_file, 'r') as f:
            procesados = f.read()

    for pdf in os.listdir(pdf_directory):
        if pdf.endswith('.pdf') and pdf not in procesados:
            
            loader = PyMuPDFLoader(os.path.join(pdf_directory, pdf))
            docs = loader.load()
            documents.extend(docs)
            
            with open(processed_pdfs_file, 'a') as f:
                f.write(pdf + '\n')
            

    if not documents:
        print("No hay documentos nuevos para procesar")
        return

    text_splitter = RecursiveCharacterTextSplitter( chunk_size=650,
                                                    chunk_overlap=150,
                                                    length_function=len)

    chunks = text_splitter.create_documents([doc.page_content for doc in documents])
    
    # --- APLICAMOS EL PARCHE AL CONECTAR CON OPENAI ---
    embeddings = OpenAIEmbeddings(model='text-embedding-ada-002', http_client=cliente_sin_ssl)

    vector_store = PineconeVectorStore.from_documents(chunks,  
                                                      embeddings,
                                                      index_name=index)