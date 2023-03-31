# Protected Area Routing

This repository offers ways to check your next outdoor trip to see how it overlaps with protected areas and helps you find alternative routes in the same region.
At /QGIS/Database/protected_areas/dataframe.gpkg you can find the dataset with the protected areas and the associated information and use it in a GIS of your choice for your next trip planning. 
The following options are available for an automated approach:
<ul>
    <li>QGIS</li>
    <li>Python CLI</li>
</ul>
Additionally, there is a QGIS plugin 'Alternative Route Creator' to calculate an alternative route in the same area which avoids the protected areas. This plugin can be found in the QGIS_plugin repository.

## CLI

In order to run the CLI just navigate in the CLI directory and run (It makes sense to do this in a virtualenv, in which case python3 must be adapted if necessary below):

```
pip install -r requirements.txt
```

Now you can run the CLI with:

```
python3 cli/cli.py --help
```

To run the `getAlternativeRoute` command an API key from the openrouteservice is needed. It can be create for free on [the website of the openrouteservice](https://openrouteservice.org/)

## QGIS

To run the models, the user first needs to change the project home of the QGIS project to the QGIS directory of this repository. For this, go to Project > Settings.

After that u can start the Model Builder and load the models in it. In order to run properly, in all algorithms (seven in total) of "Layerstil setzen" the path needs to be changed accordingly to your local file structure to the corresponding .qml file.


## QGIS Plugin

In order to use the plugin, the user first needs to add the plugin directory to the python plugin directory. With Settings > User Profiles > Open Active Profile Folder the user can locate the current profile folder. From there the user can navigate to python > plugins and paste the AlternativeRouteCalculator directory there.
Now the user can install the plugin after restarting QGIS via Plugins > Manage and Install Plugins. To run the plugin an API key from the openrouteservice is needed. It can be create for free on [the website of the openrouteservice](https://openrouteservice.org/)
