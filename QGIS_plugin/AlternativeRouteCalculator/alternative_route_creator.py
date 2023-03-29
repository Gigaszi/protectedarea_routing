# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AlternativeRouteCreator
                                 A QGIS plugin
 Creates an alternative route avoiding given polygons.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-02-12
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Levi Szamek
        email                : levi@szamek.de
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog
from qgis.core import Qgis, QgsProject

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .alternative_route_creator_dialog import AlternativeRouteCreatorDialog
import os.path

import geopandas as gpd
import json
from shapely.geometry import shape
from shapely.ops import unary_union
import shapely
from openrouteservice import client
import pandas as pd


class AlternativeRouteCreator:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'AlternativeRouteCreator_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Alternative Route Creator')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('AlternativeRouteCreator', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/Alternative Route Creator/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Alternative Route Creator'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr(u'&Alternative Route Creator'),
                action)
            self.iface.removeToolBarIcon(action)

    def decode_polyline(self, polyline, is3d=False):
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

    def coord_lister(self, geom, geom_list):
        coords = []
        for coord in geom.coords:
            for x in coord:
                coords.append(x)
        geom_list.append(coords)
        return

    def select_output_file(self):
        filename, _filter = QFileDialog.getSaveFileName(
            self.dlg, "Select   output file ", "", '*.gpkg')
        self.dlg.lineEdit_2.setText(filename)

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = AlternativeRouteCreatorDialog()
            self.dlg.pushButton.clicked.connect(self.select_output_file)

        # Fetch the currently loaded layers
        layers = QgsProject.instance().layerTreeRoot().children()
        # Clear the contents of the comboBox from previous runs
        self.dlg.comboBox.clear()
        # Populate the comboBox with names of all the loaded layers
        self.dlg.comboBox.addItems([layer.name() for layer in layers])

        layers = QgsProject.instance().layerTreeRoot().children()
        # Clear the contents of the comboBox from previous runs
        self.dlg.comboBox_2.clear()
        # Populate the comboBox with names of all the loaded layers
        self.dlg.comboBox_2.addItems([layer.name() for layer in layers])

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            filename = self.dlg.lineEdit_2.text()
            with open(filename, 'w') as output_file:
                selectedRouteLayerIndex = self.dlg.comboBox.currentIndex()
                selectedRouteLayer = layers[selectedRouteLayerIndex].layer()
                selectedPolygonLayerIndex = self.dlg.comboBox_2.currentIndex()
                selectedPolygonLayer = layers[selectedPolygonLayerIndex].layer()
                selectedRouteLayerText = self.dlg.comboBox.currentText()
                output_file.write(str(selectedRouteLayerText))
            buffer = 30


            # open route layer
            layer = layers[selectedRouteLayerIndex].layer()
            # for standalone case, comment above and uncomment below
            # layer = iface.activeLayer()

            columns = [f.name() for f in layer.fields()] + ['geometry']
            columns_types = [f.typeName() for f in layer.fields()]  # We exclude the geometry. Human readable
            # or
            # columns_types = [f.type() for f in layer.fields()] # QVariant type
            row_list = []
            for f in layer.getFeatures():
                row_list.append(dict(zip(columns, f.attributes() + [f.geometry().asWkt()])))

            df = pd.DataFrame(row_list, columns=columns)
            df['geometry'] = gpd.GeoSeries.from_wkt(df['geometry'])
            input_df = gpd.GeoDataFrame(df, geometry='geometry')
            input_df = input_df.set_crs(crs=layer.crs().toWkt())

            # open avoid polygons layer
            layer = layers[selectedPolygonLayerIndex].layer()
            # for standalone case, comment above and uncomment below
            # layer = iface.activeLayer()

            columns = [f.name() for f in layer.fields()] + ['geometry']
            columns_types = [f.typeName() for f in layer.fields()]  # We exclude the geometry. Human readable
            # or
            # columns_types = [f.type() for f in layer.fields()] # QVariant type
            row_list = []
            for f in layer.getFeatures():
                row_list.append(dict(zip(columns, f.attributes() + [f.geometry().asWkt()])))

            df = pd.DataFrame(row_list, columns=columns)
            df['geometry'] = gpd.GeoSeries.from_wkt(df['geometry'])
            gdf = gpd.GeoDataFrame(df, geometry='geometry')
            gdf = gdf.set_crs(crs=layer.crs().toWkt())

           # gdf = gpd.read_file(selectedRouteLayerText)
            mm = input_df.bounds
            input_df = input_df.to_crs(epsg=25832)

            bbox = [[mm["minx"][0], mm["miny"][0]], [mm["maxx"][0], mm["maxy"][0]]]
            input_df['geometry'] = input_df.geometry.buffer(buffer)

            api_key = self.dlg.lineEdit.text()
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
                # "filter_category_group_ids": [620, 220, 100, 330, 260],
            }

            request = ors_client.places(**iso_params)
            geom = []
            for feature in request["features"]:
                geom.append(shape(feature["geometry"]))

            pois = gpd.GeoDataFrame({'geometry': geom})
            pois = pois.set_crs("EPSG:4326")
            pois_outside_protected_areas = pois.overlay(gdf, how="difference")
            clipped_pois = pois_outside_protected_areas.clip(input_df)
            pois_json = json.loads(clipped_pois.to_json())

            point_list = []
            try:
                clipped_pois.geometry.apply(self.coord_lister, geom_list=point_list)
            except:
                raise Exception(clipped_pois.geometry)
            try:
                alternative_route = ors_client.directions(coordinates=point_list, profile="foot-hiking",
                                                      geometry_simplify=True,
                                                      options=options)
            except:
                raise Exception(options)

            geoj = self.decode_polyline(alternative_route["routes"][0]["geometry"])

            with open(self.dlg.lineEdit_2.text(), 'w') as f:
                json.dump(geoj, f)
            self.iface.messageBar().pushMessage(
                "Success", "Output file written at " + filename,
                level=Qgis.Success, duration=3)
