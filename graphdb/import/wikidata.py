from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD
import re
import time

class WikidataToRDF:
    def __init__(self):
        self.endpoint = SPARQLWrapper("https://query.wikidata.org/sparql")
        self.endpoint.setReturnFormat(JSON)
        
        # Set up namespaces
        self.WD = Namespace("http://www.wikidata.org/entity/")
        self.WDT = Namespace("http://www.wikidata.org/prop/direct/")
        self.EX = Namespace("http://localhost:8000/external#")
        
        # Initialize graph
        self.graph = Graph()
        self.graph.bind("wd", self.WD)
        self.graph.bind("wdt", self.WDT)
        self.graph.bind("ex", self.EX)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("owl", OWL)

    def get_character_qid(self, label):
        """Get Wikidata QID for a fictional character by name"""
        query = f"""
        SELECT ?item WHERE {{
          ?item rdfs:label "{label}"@en .
          ?item wdt:P31/wdt:P279* wd:Q95074 .  # instance of or subclass of fictional character
        }}
        LIMIT 1
        """
        
        try:
            self.endpoint.setQuery(query)
            results = self.endpoint.query().convert()
            
            for result in results["results"]["bindings"]:
                uri = result["item"]["value"]
                return uri.split("/")[-1]  # extract QID from URL
        except Exception as e:
            print(f"Error querying for character '{label}': {e}")
        
        return None

    def get_character_facts(self, qid):
        """Get all direct facts (wdt:) about a character from Wikidata"""
        query = f"""
        SELECT ?prop ?val ?valLabel ?valType WHERE {{
        wd:{qid} ?p ?val .
        FILTER(STRSTARTS(STR(?p), STR(wdt:)))

        BIND(?p AS ?prop)
        
        SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
            ?val rdfs:label ?valLabel .
        }}
        
        BIND(DATATYPE(?val) AS ?valType)
        }}
        """
        try:
            self.endpoint.setQuery(query)
            time.sleep(0.1)
            return self.endpoint.query().convert()
        except Exception as e:
            print(f"Error querying facts for {qid}: {e}")
            return None


    def get_character_basic_info(self, qid):
        """Get basic information about the character including their label"""
        query = f"""
        SELECT ?label ?description WHERE {{
          wd:{qid} rdfs:label ?label .
          OPTIONAL {{ wd:{qid} schema:description ?description }}
          FILTER(LANG(?label) = "en")
          FILTER(!BOUND(?description) || LANG(?description) = "en")
        }}
        LIMIT 1
        """
        
        try:
            self.endpoint.setQuery(query)
            results = self.endpoint.query().convert()
            
            for result in results["results"]["bindings"]:
                label = result.get("label", {}).get("value")
                description = result.get("description", {}).get("value")
                return label, description
        except Exception as e:
            print(f"Error querying basic info for {qid}: {e}")
        
        return None, None

    # Also fix the property URI collection in process_character_data:

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

    def safe_uri_fragment(self, text):
        """Create a safe URI fragment from text"""
        if not text:
            return "unknown"
        
        # Remove or replace problematic characters
        safe_text = re.sub(r'[^\w\s-]', '', text)
        safe_text = re.sub(r'\s+', '_', safe_text.strip())
        safe_text = safe_text[:50]  # Limit length
        
        return safe_text if safe_text else "unknown"

    def process_character_data(self, qid, data, char_label=None, char_description=None):
        """Process Wikidata results and add to RDF graph"""
        if not data or not data.get("results", {}).get("bindings"):
            print(f"No data found for {qid}")
            return
        
        subject = self.WD[qid]
        
        # Add basic character information
        self.graph.add((subject, RDF.type, self.WD["Q95074"]))  # fictional character
        
        if char_label:
            self.graph.add((subject, RDFS.label, Literal(char_label, lang="en")))
        
        if char_description:
            self.graph.add((subject, RDFS.comment, Literal(char_description, lang="en")))
        
        # Collect all unique property URIs for label lookup
        property_uris = set()
        for result in data["results"]["bindings"]:
            prop_uri = result["prop"]["value"]
            property_uris.add(prop_uri)
        
        # Get property labels in a separate query
        print(f"Getting labels for {len(property_uris)} properties...")
        property_labels = self.get_property_labels(list(property_uris))
        
        for result in data["results"]["bindings"]:
            try:
                prop_uri = result["prop"]["value"]
                prop_label = property_labels.get(prop_uri)
                val_data = result["val"]
                val_uri = val_data["value"]
                
                # Convert Wikidata property URI to direct property URI
                if "/prop/P" in prop_uri:
                    prop_id = prop_uri.split("/")[-1]
                    predicate = self.WDT[prop_id]
                else:
                    predicate = URIRef(prop_uri)

                # Add property label if available
                if prop_label:
                    self.graph.add((predicate, RDFS.label, Literal(prop_label, lang="en")))

                if val_data["type"] == "uri":
                    # Handle URI values
                    label = result.get("valLabel", {}).get("value")
                    if label and label != val_uri:  # Only create local URI if we have a meaningful label
                        label_safe = self.safe_uri_fragment(label)
                        obj = self.EX[label_safe]
                        
                        # Add main triple
                        self.graph.add((subject, predicate, obj))
                        
                        # Add label and provenance
                        self.graph.add((obj, RDFS.label, Literal(label, lang="en")))
                        self.graph.add((obj, OWL.sameAs, URIRef(val_uri)))
                    else:
                        # Use original Wikidata URI
                        if val_uri.startswith("http://www.wikidata.org/entity/"):
                            qid_val = val_uri.split("/")[-1]
                            obj = self.WD[qid_val]
                        else:
                            obj = URIRef(val_uri)
                        self.graph.add((subject, predicate, obj))
                        
                else:
                    # Handle literal values
                    val_str = val_data["value"]
                    
                    # Try to preserve datatype information
                    if "datatype" in val_data:
                        datatype = val_data["datatype"]
                        obj = Literal(val_str, datatype=URIRef(datatype))
                    else:
                        obj = Literal(val_str)
                    
                    self.graph.add((subject, predicate, obj))
                    
            except Exception as e:
                print(f"Error processing result: {e}")
                continue

    def convert_character_to_rdf(self, character_name, output_filename=None):
        """Main method to convert a character's Wikidata info to RDF"""
        print(f"Looking up character: {character_name}")
        
        # Get QID
        qid = self.get_character_qid(character_name)
        if not qid:
            print(f"Character '{character_name}' not found in Wikidata")
            return None
        
        print(f"Found QID: {qid}")
        
        # Get basic character info
        char_label, char_description = self.get_character_basic_info(qid)
        if char_label:
            print(f"Character: {char_label}")
        if char_description:
            print(f"Description: {char_description}")
        
        # Get facts
        data = self.get_character_facts(qid)
        if not data:
            print(f"No facts found for {character_name}")
            return None
        
        # Process data
        self.process_character_data(qid, data, char_label, char_description)
        
        # Save to files
        if not output_filename:
            safe_name = self.safe_uri_fragment(char_label or character_name)
            output_filename = f"{safe_name}_wikidata"
        
        ttl_file = f"{output_filename}.ttl"
        rdf_file = f"{output_filename}.rdf"
        
        self.graph.serialize(ttl_file, format="turtle")
        self.graph.serialize(rdf_file, format="xml")
        
        print(f"RDF data saved to {ttl_file} and {rdf_file}")
        print(f"Total triples: {len(self.graph)}")
        
        return qid

    def print_summary(self, qid):
        """Print a summary of the extracted data"""
        subject = self.WD[qid]
        properties = {}
        
        for s, p, o in self.graph.triples((subject, None, None)):
            if p != RDF.type:
                # Get property label if available
                prop_label = None
                for _, _, label in self.graph.triples((p, RDFS.label, None)):
                    prop_label = str(label)
                    break
                
                prop_key = str(p).split("/")[-1]
                properties[prop_key] = prop_label or prop_key
        
        print(f"\nExtracted {len(properties)} different properties:")
        for prop_id, prop_label in sorted(properties.items())[:10]:  # Show first 10
            print(f"  - {prop_id}: {prop_label}")
        
        if len(properties) > 10:
            print(f"  ... and {len(properties) - 10} more")
            
        # Also show total triples including property labels
        total_triples = len(self.graph)
        property_label_triples = sum(1 for s, p, o in self.graph.triples((None, RDFS.label, None)) 
                                   if str(s).startswith("http://www.wikidata.org/prop/direct/"))
        print(f"\nTotal triples: {total_triples} (including {property_label_triples} property labels)")

    def get_all_star_wars_characters(self, limit=100):
        """Retrieve all Star Wars fictional character QIDs and labels."""
        query = f"""
        SELECT ?character ?characterLabel WHERE {{
        ?character wdt:P31 wd:Q95074 .
        ?character wdt:P361* wd:Q2831 .
        SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """
        try:
            self.endpoint.setQuery(query)
            results = self.endpoint.query().convert()
            characters = []
            for result in results["results"]["bindings"]:
                uri = result["character"]["value"]
                label = result.get("characterLabel", {}).get("value")
                qid = uri.split("/")[-1]
                characters.append((qid, label))
            return characters
        except Exception as e:
            print(f"Error retrieving all Star Wars characters: {e}")
            return []


    def generate_enriched_local_rdf(self, character_name, qid=None):
        LOCAL = Namespace("http://localhost:8000/")
        CHAR = Namespace("http://localhost:8000/characters/")
        
        local_graph = Graph()
        local_graph.bind("rdf", RDF)
        local_graph.bind("rdfs", RDFS)
        local_graph.bind("owl", OWL)
        local_graph.bind("wd", self.WD)
        local_graph.bind("wdt", self.WDT)

        if not qid:
            qid = self.get_character_qid(character_name)
            if not qid:
                print(f"Character '{character_name}' not found.")
                return

        label, description = self.get_character_basic_info(qid)
        facts = self.get_character_facts(qid)
        
        subject = CHAR[self.safe_uri_fragment(character_name)]
        wd_subject = self.WD[qid]

        # Your local character RDF subject
        local_graph.add((subject, RDF.type, URIRef("http://localhost:8000/ontology#Character")))
        local_graph.add((subject, RDFS.label, Literal(label or character_name)))
        local_graph.add((subject, OWL.sameAs, wd_subject))
        
        if description:
            local_graph.add((subject, RDFS.comment, Literal(description, lang="en")))

        # Add all Wikidata facts directly
        for result in facts["results"]["bindings"]:
            prop_uri = result["prop"]["value"]
            val_data = result["val"]
            val = val_data["value"]
            predicate = URIRef(prop_uri)

            # Attach Wikidata property directly to local character
            if val_data["type"] == "uri":
                obj = URIRef(val)
                local_graph.add((subject, predicate, obj))

                # Add a readable label (if available)
                label = result.get("valLabel", {}).get("value")
                if label:
                    local_graph.add((obj, RDFS.label, Literal(label, lang="en")))
            else:
                # Literal value
                datatype = val_data.get("datatype")
                if datatype:
                    obj = Literal(val, datatype=URIRef(datatype))
                else:
                    obj = Literal(val)
                local_graph.add((subject, predicate, obj))

        # Serialize
        filename = f"{self.safe_uri_fragment(character_name)}_enriched.rdf"
        local_graph.serialize(filename, format="xml")
        print(f"✅ Enriched RDF saved to {filename} ({len(local_graph)} triples)")
    
    def convert_all_characters_to_rdf(self, limit=100, output_filename="all_star_wars_characters"):
        characters = self.get_all_star_wars_characters(limit=limit)
        if not characters:
            print("No characters found")
            return
        
        print(f"Processing {len(characters)} characters...")
        
        for qid, label in characters:
            # Fetch facts and basic info for each character
            char_label, char_description = self.get_character_basic_info(qid)
            data = self.get_character_facts(qid)
            
            if data:
                self.process_character_data(qid, data, char_label, char_description)
            else:
                print(f"No facts for character {qid}")
            
            # Be gentle with the endpoint, sleep a bit to avoid overloading
            time.sleep(0.1)
        
        ttl_file = f"{output_filename}.ttl"
        rdf_file = f"{output_filename}.rdf"
        
        self.graph.serialize(ttl_file, format="turtle")
        self.graph.serialize(rdf_file, format="xml")
        
        print(f"All characters RDF saved to {ttl_file} and {rdf_file}")
        print(f"Total triples: {len(self.graph)}")




# Usage example
if __name__ == "__main__":
    converter = WikidataToRDF()

    characters = converter.get_all_star_wars_characters(limit=50)  # or None for no limit

    for qid, label in characters:
        print(f"Processing {label} ({qid})")
        char_label, char_description = converter.get_character_basic_info(qid)
        facts = converter.get_character_facts(qid)
        converter.process_character_data(qid, facts, char_label, char_description)

    # Finally serialize or work with the graph
    converter.graph.serialize("all_star_wars_characters.ttl", format="turtle")
    print(f"Done. Total triples: {len(converter.graph)}")


    """ character = "Luke Skywalker"
    qid = converter.convert_character_to_rdf(character)
    if qid:
        converter.generate_enriched_local_rdf(character, qid=qid)
    
    # Convert multiple characters
    characters = ["Luke Skywalker"]


    
    for character in characters:
        print(f"\n{'='*50}")
        qid = converter.convert_character_to_rdf(character)
        if qid:
            converter.print_summary(qid) """
        
        # Clear graph for next character (optional)
        # converter.graph = Graph()
        # converter.graph.bind("wd", converter.WD)
        # converter.graph.bind("wdt", converter.WDT)
        # converter.graph.bind("ex", converter.EX)
        # converter.graph.bind("rdfs", RDFS)
        # converter.graph.bind("owl", OWL)