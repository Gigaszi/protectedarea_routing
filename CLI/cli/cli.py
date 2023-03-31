import json

import click
import geopandas as gpd
import requests
import shapely
from openrouteservice import client
from shapely.geometry import shape
from shapely.ops import unary_union

from download_protected_areas import createDataframe


@click.group(
    help="CLI tool to analyse routes and their intersection with protected areas."
)
def cli():
    click.echo()
    pass


@cli.command("getPermissions")
@click.option("--infile", required=True, type=str, help="Path to file for analysis.")
@click.option(
    "--buffer",
    required=False,
    type=int,
    help="Buffer width in meters. Areas within the buffer are also included.",
)
@click.option(
    "--outfile",
    required=False,
    type=str,
    help="Path to output file (Input file with information attached).",
)
def getPermissions(infile, buffer, outfile):
    """
    Get the rules of every protected area crossed by the given infile.
    """

    gdf = gpd.read_file("../data/dataframe.gpkg")
    gdf = gdf.to_crs(epsg=25832)
    try:
        input_df = gpd.read_file(infile)
        input_df = input_df.to_crs(epsg=25832)
    except:
        click.echo("Couldn't open the input file.")
    if buffer is not None:
        input_df["geometry"] = input_df.geometry.buffer(buffer)
    df = gpd.sjoin(input_df, gdf, how="left")
    if bool(df["index_right"].isnull().values.all()) is True:
        click.echo("No protected areas crossed.")
        return
    for row in df.iterrows():
        click.echo("Crossing protected area: " + row[1]["name"])
        click.echo("Rules:")
        if row[1]["comments"] is None:
            click.echo("No permissions")
        else:
            click.echo(row[1]["comments"].replace(". ", ". \n"))
    if outfile is not None:
        df.to_file(outfile, driver="GPKG", layer="protected_areas_crossing")


@cli.command("getCrossingPaths")
@click.option("--infile", required=True, type=str, help="Path to file for analysis.")
@click.option("--outfile", required=True, type=str, help="Path to output file.")
def getCrossingPaths(infile, outfile):
    """
    Identify the parts of the specified route that pass through protected areas.
    """

    gdf = gpd.read_file("../data/dataframe.gpkg")
    gdf = gdf.to_crs(epsg=25832)
    try:
        input_df = gpd.read_file(infile)
        input_df = input_df.to_crs(epsg=25832)
    except:
        click.echo("Couldn't open the input file.")
    df = gpd.sjoin(input_df, gdf, how="left")
    df = df.to_crs(epsg=25832)
    output_gdf = df.clip(gdf)
    output_gdf.to_file(outfile, driver="GPKG", layer="protected_areas_crossing")


@cli.command("getCrossedAreas")
@click.option("--infile", required=True, type=str, help="Path to file for analysis.")
@click.option(
    "--buffer",
    required=False,
    type=int,
    help="Buffer width in meters. Areas within the buffer are also included.",
)
@click.option("--outfile", required=True, type=str, help="Path to output file.")
def getCrossedArea(infile, buffer, outfile):
    """
    Get the areas crossed by the given route.
    """

    gdf = gpd.read_file("../data/dataframe.gpkg")
    gdf = gdf.to_crs(epsg=25832)
    try:
        input_df = gpd.read_file(infile)
        input_df = input_df.to_crs(epsg=25832)
    except:
        click.echo("Couldn't open the input file.")
    if buffer is not None:
        input_df["geometry"] = input_df.geometry.buffer(buffer)
    df = gpd.sjoin(gdf, input_df, how="inner", predicate="intersects")
    df.to_file(outfile, driver="GPKG", layer="protected_areas_crossing")


@cli.command("getAlternativeRoute")
@click.option("--infile", required=True, type=str, help="Path to file for analysis.")
@click.option("--outfile", required=True, type=str, help="Path to output file.")
@click.option(
    "--api_key",
    required=True,
    type=str,
    help="A valid key for the Openreouteservice API.",
)
def getAlternativeRoute(infile, outfile, api_key):
    """
    Get an alternative route that avoids all protected areas and reaches all POIs around the original route (outside of a protected area).
    """

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

        geojson = {"type": "LineString", "coordinates": points}

        return geojson

    def coord_lister(geom, geom_list):
        coords = []
        for coord in geom.coords:
            for x in coord:
                coords.append(x)
        geom_list.append(coords)
        return

    buffer = 30

    gdf = gpd.read_file("../data/dataframe.gpkg")
    input_df = gpd.read_file(infile)
    mm = input_df.bounds
    input_df = input_df.to_crs(epsg=25832)

    bbox = [[mm["minx"][0], mm["miny"][0]], [mm["maxx"][0], mm["maxy"][0]]]
    input_df["geometry"] = input_df.geometry.buffer(buffer)

    try:
        ors_client = client.Client(key=api_key)
    except:
        click.echo("API key is wrong!")
    input_df = input_df.to_crs("EPSG:4326")
    crossed_areas = gpd.sjoin(gdf, input_df, how="inner", predicate="intersects")
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
        # TODO:
        # optimize filter_category
        # "filter_category_group_ids": [620, 220, 100, 330, 260],
    }

    request = ors_client.places(**iso_params)
    geom = []
    for feature in request["features"]:
        geom.append(shape(feature["geometry"]))

    pois = gpd.GeoDataFrame({"geometry": geom})
    pois = pois.set_crs("EPSG:4326")
    pois_outside_protected_areas = pois.overlay(gdf, how="difference")
    clipped_pois = pois_outside_protected_areas.clip(input_df)
    pois_json = json.loads(clipped_pois.to_json())

    point_list = []

    clipped_pois.geometry.apply(coord_lister, geom_list=point_list)

    alternative_route = ors_client.directions(
        coordinates=point_list,
        profile="foot-hiking",
        geometry_simplify=True,
        options=options,
    )

    geoj = decode_polyline(alternative_route["routes"][0]["geometry"])

    with open(outfile, "w") as f:
        json.dump(geoj, f)


@cli.command("createDataframe")
def getCrossingPaths():
    """
    Download current data from Digitize the Planet API. This can take a while.
    """
    createDataframe()
    click.echo("Dataframe creaction successfull.")


if __name__ == "__main__":
    cli()
