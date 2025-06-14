import re
from collections import defaultdict
from unittest import case
from os import getenv

import requests
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from os import getenv
from rdflib.plugins.sparql import prepareQuery, prepareUpdate
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import unquote

from . import queries
import json
from s4api.graphdb_api import GraphDBApi
from s4api.swagger import ApiClient
from urllib.parse import unquote

from rdflib import Graph, Namespace, URIRef, Literal, RDFS, RDF
from rdflib.plugins.stores.sparqlstore import SPARQLStore, SPARQLUpdateStore
import os

from .forms import CharacterForm
from .inferences import INFER_SIBLINGS, INFER_UNCLE, INFER_AUNT, INFER_NEPHEW, INFER_NIECE, INFER_GRANDFATHER, \
    INFER_GRANDMOTHER, INFER_FATHER_IN_LAW, INFER_MOTHER_IN_LAW, INFER_GRANDSON, INFER_GRANDDAUGHTER, IMPORT_ENTITY, \
    INFER_URBAN_CENTER_TRUE, INFER_URBAN_CENTER_FALSE, INFER_HABITABLE_FALSE, INFER_HABITABLE_TRUE, INFER_WEAPON
from .utils import rdflib_graph_to_html, is_valid_uri, to_human_readable, get_details, get_list, update_character, \
    remove_entity

endpoint = "http://localhost:7200/"
repo_name = "starwars"

client = ApiClient(endpoint=endpoint)

accessor = GraphDBApi(client)

store = SPARQLUpdateStore("http://localhost:7200/repositories/starwars",
                          "http://localhost:7200/repositories/starwars/statements", context_aware=False)
graph = Graph(store)

ont = Namespace("http://localhost:8000/ontology#")
res = Namespace(f"http://localhost:8000/resource/")
wd = Namespace(f"http://www.wikidata.org/entity/")


def home(request):
    return render(request, 'home.html', {'graph_html': rdflib_graph_to_html(graph)})


def handle_404_error(request, exception):
    return render(request, 'error404.html')

@csrf_exempt
def run_inferences(request, character_uri):
    if request.method == 'POST':
        wikidata_id = character_uri
        if not wikidata_id:
            return JsonResponse({'error': 'character_uri parameter is required'}, status=400)

        graphdb_url = "http://localhost:7200/repositories/starwars/statements"
        headers = {
            'Content-Type': 'application/sparql-update'
        }

        sparql_queries = [
            # Siblings
            INFER_SIBLINGS.format(wikidata_id=wikidata_id),

            # Uncle
            INFER_UNCLE.format(wikidata_id=wikidata_id),

            # Aunt
            INFER_AUNT.format(wikidata_id=wikidata_id),

            # Nephew
            INFER_NEPHEW.format(wikidata_id=wikidata_id),

            # Niece
            INFER_NIECE.format(wikidata_id=wikidata_id),

            # Grandfather
            INFER_GRANDFATHER.format(wikidata_id=wikidata_id),

            # Grandmother
            INFER_GRANDMOTHER.format(wikidata_id=wikidata_id),

            # Father in Law
            INFER_FATHER_IN_LAW.format(wikidata_id=wikidata_id),

            #Mother in Law
            INFER_MOTHER_IN_LAW.format(wikidata_id=wikidata_id),

            #Grandson
            INFER_GRANDSON.format(wikidata_id=wikidata_id),

            #Granddaughter
            INFER_GRANDDAUGHTER.format(wikidata_id=wikidata_id),

        ]

        try:
            import requests
            for query in sparql_queries:
                response = requests.post(graphdb_url, data=query, headers=headers)
                if response.status_code not in (200, 204):
                    return JsonResponse({'error': 'GraphDB error in one of the queries', 'details': response.text}, status=500)

            return JsonResponse({'message': 'All inferences triggered successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request'}, status=400)

def inferences_page(request):
    return render(request, 'inferences.html')

@csrf_exempt
def runall_inferences(request):
    if request.method == 'POST':
        graphdb_url = "http://localhost:7200/repositories/starwars/statements"
        headers = {
            'Content-Type': 'application/sparql-update'
        }

        sparql_queries = [
            #UrbanCenter true
            INFER_URBAN_CENTER_TRUE,
            #Urban Center false
            INFER_URBAN_CENTER_FALSE,
            #Planeta habitável false
            INFER_HABITABLE_FALSE,
            #Planeta Habitável true 
            INFER_HABITABLE_TRUE,
            INFER_WEAPON
        ]

        try:
            import requests
            for query in sparql_queries:
                response = requests.post(graphdb_url, data=query, headers=headers)
                if response.status_code not in (200, 204):
                    return JsonResponse({'error': 'GraphDB error in one of the queries', 'details': response.text}, status=500)

            return JsonResponse({'message': 'All inferences triggered successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request'}, status=400)

def import_entity(request):
    if request.method == "POST":
        uri = request.POST.get('uri')

        query = IMPORT_ENTITY.replace("{{{URI}}}",f"<{uri}>")

        response = requests.post(
            "http://localhost:7200/repositories/starwars/statements",
            headers={"Content-Type": "application/sparql-update"},
            data=query
        )

        response.raise_for_status()

        return redirect(request.META.get('HTTP_REFERER', '/'))
    else:
        redirect("/")


def search(request):
    q = request.GET.get('q', '')

    if is_valid_uri(q):
        # q is either a subject or is a type (the only relevant uri that is object only, at least for now)
        query = queries.SEARCH_SUBJECT
    else:
        # search for instances where it is an object (or part of it)
        query = queries.SEARCH_OBJECT

    results = graph.query(query, initBindings={'q': URIRef(q) if is_valid_uri(q) else Literal(q)})

    if len(results) == 1:
        result = next(iter(results))
        return redirect(result.s)  # if only one result we can just redirect
    else:
        results_list = []  # else just show all (if any results)
        for result in results:
            results_list.append({
                "uri": result.s,
                "name": result.sName,
                "relation": to_human_readable(result.p)
            })
        return render(request, 'search.html', {'results': results_list, 'query_string': re.split(r'[/#]', q)[-1]})


def resource_redirect(request, _id):
    uri = request.build_absolute_uri()
    query = """
        PREFIX ont: <http://localhost:8000/ontology#>
        SELECT DISTINCT ?t
        WHERE{
            ?uri rdf:type ?t .
            VALUES ?t { ont:Character ont:City ont:Droid ont:Film ont:Music ont:Organizations ont:Planet ont:Quote ont:Specie ont:Vehicle ont:Starship ont:Weapon } .
        }
    """

    types = list(graph.query(query, initBindings={'uri': URIRef(uri)}))

    if len(types) == 0:
        details = get_details(uri, graph)

        return render(request, "incomplete_entity.html", {"details": dict(details)})
    else:
        t = types[-1]["t"]  # -1 because some of our types are subtypes

        match t:
            case ont.Character:
                return redirect("http://localhost:8000/characters/" + _id)
            case ont.City:
                return redirect("http://localhost:8000/cities/" + _id)
            case ont.Droid:
                return redirect("http://localhost:8000/droids/" + _id)
            case ont.Film:
                return redirect("http://localhost:8000/films/" + _id)
            case ont.Music:
                return redirect("http://localhost:8000/music/" + _id)
            case ont.Organizations:
                return redirect("http://localhost:8000/organizations/" + _id)
            case ont.Planet:
                return redirect("http://localhost:8000/planets/" + _id)
            case ont.Quote:
                return redirect("http://localhost:8000/quotes/" + _id)
            case ont.Specie:
                return redirect("http://localhost:8000/species/" + _id)
            case ont.Vehicle:
                return redirect("http://localhost:8000/vehicles/" + _id)
            case ont.Starship:
                return redirect("http://localhost:8000/starships/" + _id)
            case ont.Weapon:
                return redirect("http://localhost:8000/weapons/" + _id)
            case _:
                return HttpResponseNotFound()


def character_details(request, _id):
    details = get_details(res[_id], graph)
    #print("details",details)
    return render(request, 'character_details.html', {'character': details})


def city_details(request, _id):
    details = get_details(res[_id], graph)
    return render(request, 'city_details.html', {'city': details})


def droid_details(request, _id):
    details = get_details(res[_id], graph)
    #print("droid_details",details)
    return render(request, 'droid_details.html', {'droid': details})


def film_details(request, _id):
    details = get_details(res[_id], graph)
    #print("details",details)
    return render(request, 'film_details.html', {'film': details})


def music_details(request, _id):
    details = get_details(res[_id], graph)
    return render(request, 'music_details.html', {'music': details})


def organization_details(request, _id):
    details = get_details(res[_id], graph)
    return render(request, 'organization_details.html', {'organization': details})


def planet_details(request, _id):
    details = get_details(res[_id], graph)
    return render(request, 'planet_details.html', {'planet': details})


def quote_details(request, _id):
    details = get_details(res[_id], graph)
    return render(request, 'quote_details.html', {'quote': details})


def specie_details(request, _id):
    details = get_details(res[_id], graph)
    return render(request, "species_details.html", {'specie': details})


def starship_details(request, _id):
    details = get_details(res[_id], graph)
    return render(request, "starship_details.html", {'starship': details})


def vehicle_details(request, _id):
    details = get_details(res[_id], graph)
    return render(request, "vehicle_details.html", {'vehicle': details})


def weapon_details(request, _id):
    details = get_details(res[_id], graph)
    return render(request, "weapon_details.html", {'weapon': details})


def characters(request):
    uri = "http://localhost:8000/ontology#Character"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    return render(request, 'characters.html',
                  {"characters": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def cities(request):
    uri = "http://localhost:8000/ontology#City"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    return render(request, 'cities.html',
                  {"cities": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def droids(request):
    uri = "http://localhost:8000/ontology#Droid"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    return render(request, 'droids.html',
                  {"droids": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def films(request):
    uri = "http://localhost:8000/ontology#Film"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    return render(request, 'films.html',
                  {"films": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def music(request):
    uri = "http://localhost:8000/ontology#Music"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    print("ahhh",get_list(uri, graph))
    return render(request, 'music.html',
                  {"music": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def organizations(request):
    uri = "http://localhost:8000/ontology#Organizations"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    return render(request, 'organizations.html',
                  {"organizations": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def planets(request):
    uri = "http://localhost:8000/ontology#Planet"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    return render(request, 'planets.html',
                  {"planets": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def quotes(request):
    uri = "http://localhost:8000/ontology#Quote"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    return render(request, 'quotes.html',
                  {"quotes": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def species(request):
    uri = "http://localhost:8000/ontology#Specie"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    return render(request, 'species.html',
                  {"species": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def starships(request):
    uri = "http://localhost:8000/ontology#Starship"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    return render(request, 'starships.html',
                  {"starships": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def vehicles(request):
    uri = "http://localhost:8000/ontology#Vehicle"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    return render(request, 'vehicles.html',
                  {"vehicles": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def weapons(request):
    uri = "http://localhost:8000/ontology#Weapon"
    query = queries.CONSTRUCT_LOCAL_GRAPH
    local_graph = graph.query(query, initBindings={'type': URIRef(uri)}).graph
    return render(request, 'weapons.html',
                  {"weapons": get_list(uri, graph), "graph_html": rdflib_graph_to_html(local_graph)})


def edit_character(request, _id=None):
    if request.method == "GET":
        if _id:  # the id itself is not important, it's just that I needed it for the path (and now use it to decide whether it's an updade or insert
            character_uri = request.build_absolute_uri().split("/")
            character_uri = "http://localhost:8000/resource/" + character_uri[4]
            initial_data = get_details(character_uri, graph, for_form=True)
            form = CharacterForm(initial=initial_data)
        else:
            form = CharacterForm()
        return render(request, 'edit_character.html', {'form': form})
    elif request.method == "POST":
        form = CharacterForm(request.POST)
        print("hello")
        if form.is_valid():
            print("x",_id)
            if _id:
                character_uri = request.build_absolute_uri().split("/")
                character_uri = "http://localhost:8000/resource/" + character_uri[4]
                print("uri",character_uri)
                update_character(form, character_uri=character_uri)
            else:
                print("hy")
                update_character(form)
            return HttpResponse(200)
        else:
            return JsonResponse({
                'status': 'error',
                'errors': form.errors
            }, status=400)
    else:
        return HttpResponseNotAllowed(['GET', 'POST'])


@csrf_exempt
def delete_entity(request, uri):
    print(request)
    if request.method == "POST":
        uri = unquote(unquote(uri))  # Decode the URI
        print(f"Deleting character: {uri}")

        print("URI", uri)
        delete_query = f"""
        PREFIX sw: <http://localhost:8000/resource/>
        DELETE WHERE {{
            sw:{uri} ?p ?o .
        }}
        """

        payload_query = {"update": delete_query}

        try:
            response = accessor.sparql_update(body=payload_query, repo_name=repo_name)
            print("Delete response:", response)
            return JsonResponse({"success": True, "message": "Character deleted successfully."})
        except Exception as e:
            print("Error deleting character:", e)
            return JsonResponse({"success": False, "message": "Error deleting character."}, status=500)

    return JsonResponse({"success": False, "message": "Invalid request method."}, status=400)
