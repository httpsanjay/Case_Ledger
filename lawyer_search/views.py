import os

import serpapi

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from dotenv import load_dotenv

load_dotenv()

client = serpapi.Client(
    api_key=os.environ.get("SERPAPI_API_KEY")
)


@login_required
def lawyer_search(request):

    user = request.user

    # Lawyer-only access
    if user.role != "LAWYER":
        return HttpResponseForbidden("Lawyer access required.")

    results = []
    search_query = ""
    error = ""

    if request.method == "POST":

        search_query = request.POST.get(
            "search_query",
            ""
        ).strip()

        if search_query:

            try:
                result = client.search({
                    "q": search_query,
                    "location": "India",
                    "hl": "en",
                    "gl": "in",
                    "google_domain": "google.co.in",
                })

                results = result.get(
                    "organic_results",
                    []
                )
            except Exception as e:

                error = (
                    "Search service is currently unavailable."
                )

    return render(
        request,
        "lawyer_search.html",
        {
            "query": search_query,
            "results": results,
            "error": error,
        }
    )