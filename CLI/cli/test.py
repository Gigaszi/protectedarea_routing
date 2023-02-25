import json
from shapely.geometry import shape

from shapely.ops import unary_union
import shapely

from openrouteservice import client
import geopandas as gpd


def decode_polyline(polyline, is3d=False):
    """Decodes a Polyline string into a GeoJSON geometry.
    :param polyline: An encoded polyline, only the geometry.
    :type polyline: string
    :param is3d: Specifies if geometry contains Z component.
    :type is3d: boolean
    :returns: GeoJSON Linestring geometry
    :rtype: dict
    """
    points = []
    index = lat = lng = z = 0

    while index < len(polyline):
        result = 1
        shift = 0
        while True:
            b = ord(polyline[index]) - 63 - 1
            index += 1
            result += b << shift
            shift += 5
            if b < 0x1F:
                break
        lat += (~result >> 1) if (result & 1) != 0 else (result >> 1)

        result = 1
        shift = 0
        while True:
            b = ord(polyline[index]) - 63 - 1
            index += 1
            result += b << shift
            shift += 5
            if b < 0x1F:
                break
        lng += ~(result >> 1) if (result & 1) != 0 else (result >> 1)

        if is3d:
            result = 1
            shift = 0
            while True:
                b = ord(polyline[index]) - 63 - 1
                index += 1
                result += b << shift
                shift += 5
                if b < 0x1F:
                    break
            if (result & 1) != 0:
                z += ~(result >> 1)
            else:
                z += result >> 1

            points.append(
                [
                    round(lng * 1e-5, 6),
                    round(lat * 1e-5, 6),
                    round(z * 1e-2, 1),
                ]
            )

        else:
            points.append([round(lng * 1e-5, 6), round(lat * 1e-5, 6)])

    geojson = {u"type": u"LineString", u"coordinates": points}

    return geojson

def coord_lister(geom, geom_list):
    coords = []
    for coord in geom.coords:
        for x in coord:
            coords.append(x)
    geom_list.append(coords)
    return

buffer = 30
infile = "../tests/data/test_avoid_polygons.geojson"

gdf = gpd.read_file("../data/dataframe.gpkg")
input_df = gpd.read_file(infile)
mm = input_df.bounds
input_df = input_df.to_crs(epsg=25832)

bbox = [[mm["minx"][0], mm["miny"][0]], [mm["maxx"][0], mm["maxy"][0]]]
input_df['geometry'] = input_df.geometry.buffer(buffer)


api_key = "5b3ce3597851110001cf624820bb7e7130ec4290b3e58f86acf69022"
ors_client = client.Client(key=api_key)



input_df = input_df.to_crs("EPSG:4326")
crossed_areas = gpd.sjoin(gdf, input_df, how='inner', predicate='intersects')
poly_list = []
for i, row in crossed_areas.iterrows():
    poly_list.append(row["geometry"])
cu = unary_union(poly_list)
avoid_polygons = json.loads(json.dumps(shapely.geometry.mapping(cu)))
options = {"avoid_polygons": avoid_polygons}
# Define the request parameters.
iso_params = {
    "bbox": bbox,
    "request": "pois",
    #"filter_category_group_ids": [620, 220, 100, 330, 260],
}


request = ors_client.places(**iso_params)
geom = []
for feature in request["features"]:
    geom.append(shape(feature["geometry"]))

pois = gpd.GeoDataFrame({'geometry':geom})
pois = pois.set_crs("EPSG:4326")
pois_outside_protected_areas = pois.overlay(gdf, how="difference")
clipped_pois = pois_outside_protected_areas.clip(input_df)
pois_json = json.loads(clipped_pois.to_json())

point_list = []



clipped_pois.geometry.apply(coord_lister, geom_list=point_list)

alternative_route = ors_client.directions(coordinates=point_list, profile="foot-hiking", geometry_simplify=True, options=options)

geoj = decode_polyline(alternative_route["routes"][0]["geometry"])

outfile = f"../../data/isochrones.geojson"
with open(outfile, 'w') as f:
    json.dump(geoj, f)
