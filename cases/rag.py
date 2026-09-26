import os

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_classic.chains import RetrievalQA


from .models import Case
from .permissions import can_access_case, can_access_document_version



VECTOR_DB = "./vector_db"

embeddings = HuggingFaceEmbeddings( model_name="sentence-transformers/all-MiniLM-L6-v2")

vectorstore = Chroma(
    collection_name="nyayavault",
    persist_directory=VECTOR_DB,
    embedding_function=embeddings,
)



def index_case(case):

    documents = []

    for document in case.documents.all():

        for version in document.versions.all():

            text = version.extracted_text

            if not text:
                continue

            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "case_id": case.id,
                        "document_id": document.id,
                        "document_name": document.name,
                        "version_id": version.id,
                    },
                )
            )

    if not documents:
        return 0

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    chunks = splitter.split_documents(documents)

    vectorstore.add_documents(chunks)

    return len(chunks)


# ---------------------------------------------------------
# ASK CASE
# ---------------------------------------------------------

def ask_case(user, case_id, question):

    case = Case.objects.get(id=case_id)

    # Django handles authorization
    if not can_access_case(user, case):
        return {
            "success": False,
            "error": "Not authorized."
        }

    retriever = vectorstore.as_retriever(
    search_kwargs={
        "k": 5,
        "filter": {
            "case_id": case.id
        }
    }
)

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
    )

    qa = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
    )

    answer = qa.invoke(question)

    return {
        "success": True,
        "answer": answer["result"],
    }