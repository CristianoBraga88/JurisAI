import os
import time
import sqlite3
import bcrypt
import streamlit as st
from pypdf import PdfReader

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
import ollama

PASTA_USUARIOS = "usuarios"
BANCO = "sistema.db"

os.makedirs(PASTA_USUARIOS, exist_ok=True)


def conectar():
    return sqlite3.connect(BANCO, check_same_thread=False)


def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            senha TEXT
        )
    """)

    conn.commit()
    conn.close()


def gerar_hash(senha):
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def cadastrar_usuario(email, senha):

    conn = conectar()
    cursor = conn.cursor()

    senha_hash = gerar_hash(senha)

    try:

        cursor.execute(
            "INSERT INTO usuarios(email, senha) VALUES(?,?)",
            (email, senha_hash)
        )

        conn.commit()
        conn.close()

        return True

    except:

        conn.close()
        return False


def autenticar_usuario(email, senha):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT senha FROM usuarios WHERE email=?", (email,))
    resultado = cursor.fetchone()

    conn.close()

    if not resultado:
        return False

    senha_hash = resultado[0].encode()

    return bcrypt.checkpw(senha.encode(), senha_hash)


def pasta_usuario(email):

    nome = email.replace("@", "_").replace(".", "_")

    base = os.path.join(PASTA_USUARIOS, nome)

    casos = os.path.join(base, "casos")

    os.makedirs(casos, exist_ok=True)

    return casos


def pasta_caso(usuario, caso):

    base_usuario = pasta_usuario(usuario)

    pasta_caso = os.path.join(base_usuario, caso)

    docs = os.path.join(pasta_caso, "documentos")

    base_vetorial = os.path.join(pasta_caso, "base")

    os.makedirs(docs, exist_ok=True)
    os.makedirs(base_vetorial, exist_ok=True)

    return docs, base_vetorial


def salvar_pdf(upload, pasta):

    caminho = os.path.join(pasta, upload.name)

    with open(caminho, "wb") as f:
        f.write(upload.getbuffer())


def ler_pdfs(pasta):

    documentos = []

    for arquivo in os.listdir(pasta):

        if arquivo.endswith(".pdf"):

            caminho = os.path.join(pasta, arquivo)

            reader = PdfReader(caminho)

            texto = ""

            for pagina in reader.pages:

                conteudo = pagina.extract_text()

                if conteudo:
                    texto += conteudo + "\n"

            documentos.append(
                Document(
                    page_content=texto,
                    metadata={"source": arquivo}
                )
            )

    return documentos


def criar_base(pasta_docs, pasta_base):

    documentos = ler_pdfs(pasta_docs)

    if not documentos:
        return None

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    chunks = splitter.split_documents(documentos)

    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=pasta_base
    )

    return db


def abrir_base(pasta):

    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    return Chroma(
        persist_directory=pasta,
        embedding_function=embeddings
    )


def gerar_prompt(contexto, pergunta):

    return f"""
Você é um assistente jurídico especializado.

Analise o documento e responda com:

1. Resumo
2. Pontos importantes
3. Riscos jurídicos
4. Sugestões de melhoria
5. Conclusão

DOCUMENTO:
{contexto}

PERGUNTA:
{pergunta}
"""


def analisar(pergunta):

    if not st.session_state.base_atual:

        st.error("Indexe o caso primeiro")

        return

    db = abrir_base(st.session_state.base_atual)

    resultados = db.similarity_search(pergunta, k=4)

    contexto = "\n\n".join(
        [doc.page_content for doc in resultados]
    )

    prompt = gerar_prompt(contexto, pergunta)

    resposta = ollama.chat(
        model="llama3",
        messages=[{"role": "user", "content": prompt}]
    )

    texto = resposta["message"]["content"]

    st.markdown(texto)


criar_tabela()

st.set_page_config(page_title="JurisAI", page_icon="⚖️")

st.title("⚖️ JurisAI")

if "logado" not in st.session_state:
    st.session_state.logado = False

if "base_atual" not in st.session_state:
    st.session_state.base_atual = None

menu = st.sidebar.radio("Acesso", ["Entrar", "Cadastrar"])

if not st.session_state.logado:

    if menu == "Cadastrar":

        email = st.text_input("Email")

        senha = st.text_input("Senha", type="password")

        if st.button("Cadastrar"):

            if cadastrar_usuario(email, senha):
                st.success("Conta criada")

            else:
                st.error("Email já existe")

    else:

        email = st.text_input("Email")

        senha = st.text_input("Senha", type="password")

        if st.button("Entrar"):

            if autenticar_usuario(email, senha):

                st.session_state.logado = True

                st.session_state.usuario = email

                st.rerun()

            else:

                st.error("Login inválido")

else:

    st.sidebar.success(st.session_state.usuario)

    pasta_casos = pasta_usuario(st.session_state.usuario)

    st.sidebar.subheader("Casos")

    casos = os.listdir(pasta_casos)

    caso_atual = st.sidebar.selectbox("Selecionar caso", [""] + casos)

    novo_caso = st.sidebar.text_input("Novo caso")

    if st.sidebar.button("Criar caso"):

        os.makedirs(os.path.join(pasta_casos, novo_caso), exist_ok=True)

        st.rerun()

    if caso_atual:

        docs, base = pasta_caso(st.session_state.usuario, caso_atual)

        st.header(f"Caso: {caso_atual}")

        arquivos = st.file_uploader(
            "Enviar documentos",
            type=["pdf"],
            accept_multiple_files=True
        )

        if arquivos:

            for a in arquivos:
                salvar_pdf(a, docs)

            st.success("Documento enviado")

        if st.button("Indexar caso"):

            criar_base(docs, base)

            st.session_state.base_atual = base

            st.success("Caso indexado")

        pergunta = st.chat_input("Pergunta sobre o caso")

        if pergunta:

            with st.chat_message("user"):
                st.write(pergunta)

            with st.chat_message("assistant"):

                analisar(pergunta)