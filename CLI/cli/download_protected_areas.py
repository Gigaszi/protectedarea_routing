import json
import requests
import os
import geopandas as gpd
import pandas as pd

def createDataframe():
    page = 1
    url = "https://content.digitizetheplanet.org/api/protectedarea/?page="
    response = requests.get(url + str(page))
    response.raise_for_status()  # Raise an Exception if HTTP Status Code is not 200


    def getProtectedAreas(content):

        short_list = content["results"]

        for result in short_list:
            response = requests.get(result["dtp_api_url"])
            file_name = response.json()["name"] + ".geojson"
            schutzgebiet = response.json()
            df = pd.json_normalize(schutzgebiet)
            df.to_json("flattened.json")
            test = df["rules"]
            test2 = test.iloc[0]
            rules = list(eval(str(test2)))
            metadata = {}
            metadata["name"] = df["name_en"].iloc[0]
            metadata["designation"] = df["designation_en"].iloc[0]
            metadata["label"] = "green"
            metadata["label_bivouac"] = "green"
            metadata["label_winter_sport"] = "green"
            metadata["class_"] = 1
            comment = ""
            if len(rules) != 0:
                for rule in rules:
                    comment_part = rule["activity"]["activity_en"] + " on " + rule["activityplace"]["place_en"] + " " + rule["activitypermission"]["permission"]
                    if "season_start" in rule and rule["season_start"] is not None:
                        comment_part += " from " + rule["season_start"][5:] + " to " + rule["season_end"][5:] + ". "
                    else:
                        comment_part += ". "
                    comment += comment_part
                    if rule["activity"]["activity_en"] == "Entering the area" and  rule["activityplace"]["place_en"] == "Total area of the territory" and  rule["activitypermission"]["permission"] == "forbidden":
                        if rule["season_start"] is not None:
                            metadata["label"] = "yellow"
                            metadata["class_"] = 2
                        else:
                            metadata["label"] = "red"
                            metadata["class_"] = 3
                    if rule["activity"]["activity_en"] == "Camping/Bivouac" and  rule["activityplace"]["place_en"] == "Total area of the territory" and  rule["activitypermission"]["permission"] == "forbidden":
                        if rule["season_start"] is not None:
                            metadata["label_bivouac"] = "yellow"
                        else:
                            metadata["label_bivouac"] = "red"
                    if rule["activity"]["activity_en"] == "Winter sport" and  rule["activityplace"]["place_en"] == "Total area of the territory" and  rule["activitypermission"]["permission"] == "forbidden":
                        if rule["season_start"] is not None:
                            metadata["label_winter_sport"] = "yellow"
                        else:
                            metadata["label_winter_sport"] = "red"
            metadata["comments"] = comment
            with open("flattened.json") as f:
                geojs={
                 "type": "FeatureCollection",
                 "features":[
                       {
                            "type":"Feature",
                            "geometry":schutzgebiet["geometry"],
                            "properties":metadata,

                     }
                    ]
                }
            file_name = file_name.replace("/", "_")
            file_name = file_name.replace(" ", "_")
            file_name = file_name.replace("\"", "")
            file_name = file_name.replace("<", "")
            file_name = file_name.replace(">", "")
            print(file_name)
            path = "../data/protected_areas/" + file_name
            output_file=open(path, "w", encoding="utf-8")
            json.dump(geojs, output_file)
            output_file.close()

    while True:
        response = requests.get(url + str(page))

        response.raise_for_status()  # Raise an Exception if HTTP Status Code is not 200

        content = response.json()
        page = page + 1

        if content["next"] is not None:
            getProtectedAreas(content)
        else:
            getProtectedAreas(content)
            break

    file = os.listdir("../data/protected_areas")
    path = [os.path.join("../data/protected_areas", i) for i in file if ".geojson" in i]

    gdf = gpd.GeoDataFrame(pd.concat([gpd.read_file(i) for i in path],
                            ignore_index=True), crs=gpd.read_file(path[0]).crs)
    gdf.to_file('dataframe.gpkg', driver='GPKG', layer='protected_areas')

if __name__ == '__main__':
    createDataframe()
