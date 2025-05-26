from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL
import re
import time

class WikidataToRDF:
    def __init__(self):
        self.endpoint = SPARQLWrapper("https://query.wikidata.org/sparql")
        self.endpoint.setReturnFormat(JSON)

        self.WD = Namespace("http://www.wikidata.org/entity/")
        self.WDT = Namespace("http://www.wikidata.org/prop/direct/")
        self.EX = Namespace("http://localhost:8000/external#")

        self.graph = Graph()
        self.graph.bind("wd", self.WD)
        self.graph.bind("wdt", self.WDT)
        self.graph.bind("ex", self.EX)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("owl", OWL)

    def safe_uri_fragment(self, text):
        if not text:
            return "unknown"
        safe_text = re.sub(r'[^\w\s-]', '', text)
        safe_text = re.sub(r'\s+', '_', safe_text.strip())
        return safe_text[:50]

    def get_all_star_wars_droids(self, limit=500):
        # Query: all droids that are part of the Star Wars franchise
        query = f"""
        SELECT ?droid ?droidLabel WHERE {{
            ?droid wdt:P31/wdt:P279* wd:Q52383 .       # é droid ou subtipo de droid
            ?droid wdt:P31/wdt:P279* wd:Q33125444 .   # é personagem fictício
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
            }}
        LIMIT 10

        """
        self.endpoint.setQuery(query)
        try:
            results = self.endpoint.query().convert()
            droids = []
            for result in results["results"]["bindings"]:
                uri = result["droid"]["value"]
                label = result.get("droidLabel", {}).get("value")
                qid = uri.split("/")[-1]
                droids.append((qid, label))
            return droids
        except Exception as e:
            print(f"Error retrieving Star Wars droids: {e}")
            return []


    def get_character_basic_info(self, qid):
        query = f"""
        SELECT ?label ?description WHERE {{
          wd:{qid} rdfs:label ?label .
          OPTIONAL {{ wd:{qid} schema:description ?description }}
          FILTER(LANG(?label) = "en")
          FILTER(!BOUND(?description) || LANG(?description) = "en")
        }}
        LIMIT 1
        """
        self.endpoint.setQuery(query)
        try:
            results = self.endpoint.query().convert()
            for result in results["results"]["bindings"]:
                label = result.get("label", {}).get("value")
                description = result.get("description", {}).get("value")
                return label, description
        except Exception as e:
            print(f"Error querying basic info for {qid}: {e}")
        return None, None

    def get_character_facts(self, qid):
        query = f"""
        SELECT ?prop ?val ?valLabel WHERE {{
          wd:{qid} ?p ?val .
          FILTER(STRSTARTS(STR(?p), STR(wdt:)))
          BIND(?p AS ?prop)
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        """
        self.endpoint.setQuery(query)
        try:
            time.sleep(0.1)  # avoid hammering server
            return self.endpoint.query().convert()
        except Exception as e:
            print(f"Error querying facts for {qid}: {e}")
            return None

    def add_character_to_graph(self, qid, label, description, facts):
        subject = self.WD[qid]
        self.graph.add((subject, RDF.type, self.WD["Q95074"]))  # fictional character type

        if label:
            self.graph.add((subject, RDFS.label, Literal(label, lang="en")))
        if description:
            self.graph.add((subject, RDFS.comment, Literal(description, lang="en")))

        used_predicates = set()

        if not facts:
            return used_predicates

        for result in facts["results"]["bindings"]:
            prop_uri = result["prop"]["value"]
            val_data = result["val"]
            val_uri = val_data["value"]
            predicate = URIRef(prop_uri)

            used_predicates.add(prop_uri)  # <== Track used predicates

            if val_data["type"] == "uri":
                obj = URIRef(val_uri)
                self.graph.add((subject, predicate, obj))

                val_label = result.get("valLabel", {}).get("value")
                if val_label:
                    self.graph.add((obj, RDFS.label, Literal(val_label, lang="en")))
            else:
                obj = Literal(val_uri)
                self.graph.add((subject, predicate, obj))

        return used_predicates


    
    def get_property_labels(self, property_uris):
        """Get labels for a list of property URIs"""
        if not property_uris:
            return {}
        
        # Extract property IDs from direct property URIs and convert to entity URIs
        prop_ids = []
        direct_to_entity_map = {}
        
        for uri in property_uris:
            if "/prop/direct/P" in uri:
                prop_id = uri.split("/")[-1]  # Extract P123
                prop_ids.append(prop_id)
                # Map direct property URI to entity URI for the query
                entity_uri = f"http://www.wikidata.org/entity/{prop_id}"
                direct_to_entity_map[entity_uri] = uri
        
        if not prop_ids:
            return {}
        
        # Create VALUES clause for the property entities (not direct properties)
        values_clause = " ".join([f"wd:{prop_id}" for prop_id in prop_ids])
        
        query = f"""
        SELECT ?prop ?propLabel WHERE {{
        VALUES ?prop {{ {values_clause} }}
        SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
            ?prop rdfs:label ?propLabel .
        }}
        }}
        """
        
        try:
            self.endpoint.setQuery(query)
            time.sleep(0.1)  # Be nice to Wikidata servers
            results = self.endpoint.query().convert()
            
            property_labels = {}
            for result in results["results"]["bindings"]:
                entity_uri = result["prop"]["value"]  # This will be http://www.wikidata.org/entity/P123
                prop_label = result.get("propLabel", {}).get("value")
                
                # Map back to the direct property URI
                if entity_uri in direct_to_entity_map and prop_label:
                    direct_uri = direct_to_entity_map[entity_uri]
                    property_labels[direct_uri] = prop_label
            
            return property_labels
            
        except Exception as e:
            print(f"Error querying property labels: {e}")
            return {}


    def generate_all_star_wars_droids_rdf(self, limit=100):
        droids = self.get_all_star_wars_droids(limit=limit)
        print(f"Found {len(droids)} droids")

        all_predicates = set()

        for qid, label in droids:
            print(f"Processing {label} ({qid})...")
            basic_label, description = self.get_character_basic_info(qid)
            facts = self.get_character_facts(qid)
            
            used_preds = self.add_character_to_graph(qid, basic_label or label, description, facts)
            all_predicates.update(used_preds)

        print("Fetching predicate labels...")
        prop_labels = self.get_property_labels(all_predicates)
        for uri, label in prop_labels.items():
            self.graph.add((URIRef(uri), RDFS.label, Literal(label, lang="en")))

        self.graph.serialize("starwars_droids.ttl", format="xml")
        print(f"RDF graph with {len(self.graph)} triples saved to starwars_droids.xml")



    

# Usage
wikidata_rdf = WikidataToRDF()
wikidata_rdf.generate_all_star_wars_droids_rdf(limit=10)

