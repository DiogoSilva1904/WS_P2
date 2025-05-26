from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL
from slugify import slugify

# Namespaces
SW = Namespace("http://localhost:8000/ontology#")
CHAR = Namespace("http://localhost:8000/characters/")
EXT = Namespace("http://localhost:8000/external/")
WDT = Namespace("http://www.wikidata.org/prop/direct/")
WD = Namespace("http://www.wikidata.org/entity/")

wikidata_file = "starwars_characters_2.xml"
output_file = "all_formatted_2.xml"

# Carregar RDF
wikidata_graph = Graph()
wikidata_graph.parse(wikidata_file, format="xml")

# Grafo de saída
out_graph = Graph()
out_graph.bind("rdf", RDF)
out_graph.bind("rdfs", RDFS)
out_graph.bind("owl", OWL)
out_graph.bind("sw", SW)
out_graph.bind("ext", EXT)
out_graph.bind("char", CHAR)

starwars_character_type = WD["Q95074"]  # Tipo Star Wars Character no Wikidata

# Construir um mapa de labels para propriedades e recursos
label_map = {}
for s, _, o in wikidata_graph.triples((None, RDFS.label, None)):
    label_map[str(s)] = str(o)

# Filtrar todos os sujeitos que têm tipo Star Wars Character
characters = set()
for subj in wikidata_graph.subjects(RDF.type, starwars_character_type):
    characters.add(subj)

if not characters:
    print("❌ Nenhum personagem Star Wars encontrado.")
    exit()

for character in characters:
    # Obter label do personagem
    label = None
    for o in wikidata_graph.objects(character, RDFS.label):
        if o.language == "en":
            label = str(o)
            break
    if not label:
        label = str(character).split("/")[-1]  # fallback no URI

    # Criar URI local para o personagem (slugify)
    local_uri = CHAR[slugify(label)]

    # Tipo e label local
    out_graph.add((local_uri, RDF.type, SW.Character))
    out_graph.add((local_uri, RDFS.label, Literal(label, lang="en")))
    out_graph.add((local_uri, OWL.sameAs, character))

    # Copiar propriedades do personagem
    for p, o in wikidata_graph.predicate_objects(subject=character):
        if p == RDF.type:
            continue  # já processado

        p_str = str(p)
        prop_label = label_map.get(p_str)
        if not prop_label:
            continue  # ignorar propriedades sem rdfs:label

        prop_uri = SW[slugify(prop_label)]
        out_graph.add((prop_uri, RDFS.label, Literal(prop_label, lang="en")))

        if isinstance(o, URIRef):
            # ✅ Check if the property is "image"
            if slugify(prop_label) == "image":
                # Don't switch to EXT — keep the URI as-is
                out_graph.add((local_uri, prop_uri, o))
            else:
                o_label = label_map.get(str(o))
                if o_label:
                    ext_uri = EXT[slugify(o_label)]
                    out_graph.add((local_uri, prop_uri, ext_uri))
                    out_graph.add((ext_uri, RDFS.label, Literal(o_label, lang="en")))
                    out_graph.add((ext_uri, OWL.sameAs, o))
                else:
                    out_graph.add((local_uri, prop_uri, o))
        else:
            # Literal
            out_graph.add((local_uri, prop_uri, o))


# Salvar RDF/XML
out_graph.serialize(destination=output_file, format="xml")
print(f"✅ RDF formatado salvo em: {output_file}")
