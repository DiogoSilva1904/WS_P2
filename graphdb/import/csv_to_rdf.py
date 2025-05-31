import csv
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD
from slugify import slugify
import pandas as pd
from reconciler import reconcile


SERVER_PREFIX="http://localhost:8000"

pre=Namespace(f"{SERVER_PREFIX}/predicate/")
res=Namespace(f"{SERVER_PREFIX}/resource/")
wd=Namespace(f"http://www.wikidata.org/entity/")

g=Graph()
g.bind("pre", pre)
g.bind("res", res)
g.bind("wd", wd)

characters=dict()

#Note: Since the author uses names/titles as "private keys", I will be using them for the URIs (except for quotes, since it only has ids).
#It should also be noted that some files are missing (events, battles and timeline) because they were either incomplete or had type ambiguity (for example, the victors of battles could be either organizations or a planet('s inhabitants))

with open("characters.csv","r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        character_uri = URIRef(res[slugify(row["name"])])
        g.add((character_uri,RDFS.label,Literal(row["name"])))

        if character_uri not in characters:
            characters[character_uri]=row["name"]

        #species relation
        specie_uri=URIRef(res[slugify(row["species"])])
        g.add((character_uri, pre.specie, specie_uri))
        g.add((specie_uri,RDFS.label,Literal(row["species"])))

        #homeworld relation
        if row["homeworld"]!="Unknown":
            homeworld_uri=URIRef(res[slugify(row["homeworld"])])
            g.add((character_uri, pre.homeworld, homeworld_uri))
            #I added this in case they were missing from planets.csv (much like with a set, a rdf graph only adds each triple once, so we can do this without worrying)
            g.add((homeworld_uri, RDFS.label, Literal(row["homeworld"])))

        #attributes
        for string_attribute in ["gender","hair_color","eye_color","skin_color","description"]:
            if row[string_attribute] and row[string_attribute]!="None" and row[string_attribute]!="Unknown":
                g.add((character_uri, pre[string_attribute], Literal(row[string_attribute])))

        for float_attribute in ["height","weight"]:
            if row[float_attribute] and row[float_attribute]!="None" and row[float_attribute]!="Unknown":
                g.add((character_uri, pre[float_attribute], Literal(row[float_attribute], datatype=XSD.float)))

        for integer_attribute in ["year_born","year_died"]:
            if row[integer_attribute] and row[integer_attribute]!="None" and row[integer_attribute]!="Unknown":
                g.add((character_uri, pre[integer_attribute], Literal(row[integer_attribute], datatype=XSD.integer)))



with open("cities.csv","r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        city_uri=URIRef(res[slugify(row["name"])])
        g.add((city_uri,RDFS.label,Literal(row["name"])))

        #planet relation
        planet_uri=URIRef(res[slugify(row["planet"])])
        g.add((city_uri, pre.planet, planet_uri))
        g.add((planet_uri,RDFS.label,Literal(row["planet"])))

        #attributes
        g.add((city_uri, pre.population, Literal(row["population"], datatype=XSD.integer)))
        g.add((city_uri, pre.description, Literal(row["description"])))



with open("droids.csv","r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        droid_uri=URIRef(res[slugify(row["name"])])
        g.add((droid_uri,RDFS.label,Literal(row["name"])))

        if droid_uri not in characters:
            characters[droid_uri]=row["name"]

        #films relation
        for film in row["films"].split(', '):
            film_uri=URIRef(res[slugify(film)])
            g.add((droid_uri, pre.appears_in, film_uri))
            g.add((film_uri,RDFS.label,Literal(film)))

        #attributes
        for string_attribute in ["model","manufacturer","sensor_color","primary_function"]:
            if row[string_attribute]:
                g.add((droid_uri, pre[string_attribute], Literal(row[string_attribute])))

        for float_attribute in ["height","mass"]:
            if row[float_attribute]:
                g.add((droid_uri, pre[float_attribute], Literal(row[float_attribute], datatype=XSD.float)))

        for plating_color in row["plating_color"].split('/'): #splitting incase we want to search for individual plating colors
            g.add((droid_uri, pre.plating_color, Literal(plating_color)))



with open("films.csv","r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        film_uri=URIRef(res[slugify(row["title"])])
        g.add((film_uri,RDFS.label,Literal(row["title"])))
        g.add((film_uri, pre.release_date, Literal(row["release_date"], datatype=XSD.date)))
        g.add((film_uri, pre.director, Literal(row["director"])))
        g.add((film_uri, pre.opening_crawl, Literal(row["opening_crawl"])))

        for producer in row["producer"].split(','):
            g.add((film_uri, pre.producer, Literal(producer)))



with open("music.csv","r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        music_uri=URIRef(res[slugify(row["title"])])
        g.add((music_uri,RDFS.label,Literal(row["title"])))
        g.add((music_uri, pre.composer, Literal(row["composer"])))
        g.add((music_uri, pre.type, Literal(row["type"])))

        film_uri=URIRef(res[slugify(row["associated_with"])])
        g.add((music_uri, pre.associated_with, film_uri))
        g.add((film_uri,RDFS.label,Literal(row["associated_with"])))



with open("organizations.csv","r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        organization_uri=URIRef(res[slugify(row["name"])])
        g.add((organization_uri,RDFS.label,Literal(row["name"])))
        g.add((organization_uri, pre.founded, Literal(row["founded"], datatype=XSD.integer)))
        g.add((organization_uri, pre.dissolved, Literal(row["dissolved"], datatype=XSD.integer)))
        g.add((organization_uri, pre.description, Literal(row["description"])))

        for leader in row["leader"].split(", "):
            leader_uri=URIRef(res[slugify(leader)])
            g.add((organization_uri, pre.leader, leader_uri))
            g.add((leader_uri, RDFS.label,Literal(leader)))

            if leader_uri not in characters:
                characters[leader_uri] = leader

        for member in row["members"].split(", "):
            member_uri=URIRef(res[slugify(member)])
            g.add((organization_uri, pre.member, member_uri))
            g.add((member_uri, RDFS.label,Literal(member)))

            if member_uri not in characters:
                characters[member_uri] = member

        if row["affiliation"] is not None and row["affiliation"]!="None":
            g.add((organization_uri, pre.affiliation, Literal(row["affiliation"])))


        for film in row["films"].split(", "):
            film_uri=URIRef(res[slugify(film)])
            g.add((organization_uri, pre.appears_in, film_uri))
            g.add((film_uri,RDFS.label,Literal(film)))


with open("planets.csv","r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        planet_uri=URIRef(res[slugify(row["name"])])
        g.add((planet_uri,RDFS.label,Literal(row["name"])))
        g.add((planet_uri, pre.gravity, Literal(row["gravity"])))
        g.add((planet_uri, pre.climate, Literal(row["climate"])))

        if row["population"] is not None:
            g.add((planet_uri, pre.population, Literal(row["population"])))

        for float_attribute in ['diameter','rotation_period','orbital_period','surface_water']:
            if row[float_attribute]:
                g.add((planet_uri, pre[float_attribute], Literal(row[float_attribute], datatype=XSD.float)))

        for terrain in row["terrain"].split(", "):
            g.add((planet_uri, pre.terrain, Literal(terrain)))

        for resident in row["residents"].split(", "):
            character_uri=URIRef(res[slugify(resident)])
            g.add((planet_uri, pre.resident, character_uri))
            g.add((character_uri,RDFS.label,Literal(resident)))

            if character_uri not in characters:
                characters[character_uri] = resident

        if row["films"]:
            for film in row["films"].split(", "):
                film_uri=URIRef(res[slugify(film)])
                g.add((planet_uri, pre.appears_in, film_uri))
                g.add((film_uri,RDFS.label,Literal(film)))



with open("quotes.csv", "r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        quote_uri = URIRef(res[slugify(row["id"])])

        # Add the quote text
        g.add((quote_uri, RDFS.label, Literal(row["quote"])))

        character_uri = URIRef(res[slugify(row["character_name"])])
        g.add((quote_uri, pre.said_by, character_uri))
        g.add((character_uri, RDFS.label, Literal(row["character_name"])))

        if character_uri not in characters:
            characters[character_uri] = row["character_name"]

        source_uri = URIRef(res[slugify(row["source"])])
        g.add((quote_uri, pre.appears_in, source_uri))
        g.add((source_uri, RDFS.label, Literal(row["source"])))



with open("species.csv","r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        specie_uri=URIRef(res[slugify(row["name"])])
        g.add((specie_uri,RDFS.label,Literal(row["name"])))

        for string_attribute in ["classification","designation","hair_colors","eye_colors","language"]:
            if row[string_attribute] and row[string_attribute]!="None" and row[string_attribute]!="Unknown":
                g.add((specie_uri, pre[string_attribute], Literal(row[string_attribute])))

        for float_attribute in ["average_height","average_lifespan"]:
            if row[float_attribute]:
                g.add((specie_uri, pre[float_attribute], Literal(row[float_attribute], datatype=XSD.float)))

        if row["skin_colors"]!="Unknown":
            for skin_color in row["skin_colors"].split(", "):
                g.add((specie_uri, pre.skin_color, Literal(skin_color)))

        if row["homeworld"]!="None" and row["homeworld"]!="Unknown":
            homeworld_uri=URIRef(res[slugify(row["homeworld"])])
            g.add((specie_uri, pre.homeworld, homeworld_uri))
            g.add((homeworld_uri,RDFS.label,Literal(row["homeworld"])))



with open("starships.csv","r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        starship_uri=URIRef(res[slugify(row["name"])])
        g.add((starship_uri,RDFS.label,Literal(row["name"])))

        for float_attribute in ["cost_in_credits","length","max_atmosphering_speed","cargo_capacity","hyperdrive_rating"]:
            if row[float_attribute]:
                g.add((starship_uri, pre[float_attribute], Literal(row[float_attribute], datatype=XSD.float)))

        for integer_attribute in ["crew","passengers","MGLT"]:
            if row[integer_attribute]:
                g.add((starship_uri, pre[integer_attribute], Literal(row[integer_attribute], datatype=XSD.integer)))

        for string_attribute in ["model","manufacturer","consumables","starship_class"]:
            if row[string_attribute]:
                g.add((starship_uri, pre[string_attribute], Literal(row[string_attribute])))

        if row["pilots"]!="None":
            for pilot in row["pilots"].split(", "):
                pilot_uri=URIRef(res[slugify(pilot)])
                g.add((starship_uri, pre.pilot, pilot_uri))
                g.add((pilot_uri,RDFS.label,Literal(pilot)))

                if pilot_uri not in characters:
                    characters[pilot_uri] = pilot

        for film in row["films"].split(", "):
            film_uri=URIRef(res[slugify(film)])
            g.add((starship_uri, pre.appears_in, film_uri))
            g.add((film_uri,RDFS.label,Literal(film)))



with open("vehicles.csv","r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        vehicle_uri=URIRef(res[slugify(row["name"])])
        g.add((vehicle_uri,RDFS.label,Literal(row["name"])))

        for string_attribute in ["model","manufacturer","consumables","vehicle_class"]:
            if row[string_attribute] and row[string_attribute]!="None" and row[string_attribute]!="Unknown":
                g.add((vehicle_uri, pre[string_attribute], Literal(row[string_attribute])))

        for float_attribute in ["cost_in_credits","length","max_atmosphering_speed","cargo_capacity"]:
            if row[float_attribute]:
                g.add((vehicle_uri, pre[float_attribute], Literal(row[float_attribute], datatype=XSD.float)))

        for integer_attribute in ["crew","passengers"]:
            if row[integer_attribute]:
                g.add((vehicle_uri, pre[integer_attribute], Literal(row[integer_attribute], datatype=XSD.integer)))

        if row["pilots"]!="None":
            for pilot in row["pilots"].split(", "):
                pilot_uri=URIRef(res[slugify(pilot)])
                g.add((vehicle_uri, pre.pilot, pilot_uri))
                g.add((pilot_uri,RDFS.label,Literal(pilot)))

                if pilot_uri not in characters:
                    characters[pilot_uri] = pilot

        for film in row["films"].split(", "):
            film_uri=URIRef(res[slugify(film)])
            g.add((vehicle_uri, pre.appears_in, film_uri))
            g.add((film_uri,RDFS.label,Literal(film)))



with open("weapons.csv","r") as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        weapon_uri=URIRef(res[slugify(row["name"])])
        g.add((weapon_uri,RDFS.label,Literal(row["name"])))

        for string_attribute in ["model","manufacturer","type","description"]:
            if row[string_attribute]:
                g.add((weapon_uri, pre[string_attribute], Literal(row[string_attribute])))

        for float_attribute in ["cost_in_credits","length"]:
            if row[float_attribute]:
                g.add((weapon_uri, pre[float_attribute], Literal(row[float_attribute], datatype=XSD.float)))

        for film in row["films"].split(", "):
            film_uri=URIRef(res[slugify(film)])
            g.add((weapon_uri, pre.appears_in, film_uri))
            g.add((film_uri,RDFS.label,Literal(film)))

df = pd.DataFrame([
    {"uri": uri, "label": label}
    for uri, label in characters.items()
])

reconciled=reconcile(df["label"],type_id="Q33125444")

df["qid"] = reconciled["id"].values

print(df[["label", "uri", "qid"]])

for idx,row in df.iterrows():
    if pd.notnull(row["qid"]):
        g.add((row["uri"],RDFS.seeAlso,wd[row["qid"]]))

rdf_xml=g.serialize(format="xml")

with open("starwars_rdf.xml","w") as f:
    f.write(rdf_xml)




