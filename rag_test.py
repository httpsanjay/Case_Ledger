import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nyaya_vault.settings")
django.setup()

from cases.models import Case
from cases.rag import index_case, ask_case


# Change this to an existing case ID
CASE_ID = 1


# --------------------------------------------------
# 1. Get case
# --------------------------------------------------

case = Case.objects.get(id=CASE_ID)

print("\nCASE:")
print(case)


# --------------------------------------------------
# 2. Index documents
# --------------------------------------------------

print("\nIndexing documents...")

chunks = index_case(case)

print(f"Indexed chunks: {chunks}")


# --------------------------------------------------
# 3. Test RAG
# --------------------------------------------------

question = "What information is available in this case?"

print("\nQuestion:")
print(question)

# Replace this with a real Django user
user = case.created_by

result = ask_case(
    user=user,
    case_id=CASE_ID,
    question=question,
)

print("\nRESULT:")
print(result)