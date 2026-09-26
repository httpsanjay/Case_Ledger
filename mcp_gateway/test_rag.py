import asyncio

from rag import answer_case_question


async def main():

    result = await answer_case_question(
        case_id=1,
        question="What documents are available in this case?",
        top_k=5,
    )

    print("\n================ RESULT ================\n")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())