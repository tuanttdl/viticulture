# -*- coding: utf-8 -*-

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""
import os

from qgis import processing
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing,
                       QgsProject,
                       QgsProcessingAlgorithm,
                       QgsField,
                       QgsVectorLayer,
                       QgsExpression,
                       QgsExpressionContext,
                       QgsVectorFileWriter,
                       QgsExpressionContextUtils,
                       QgsCoordinateReferenceSystem,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterVectorDestination)
from qgis.utils import iface


class AssessingVulerabilityProcessingAlgorithm(QgsProcessingAlgorithm):
    """
    This algorithm takes a vector layer and a land cover raster layer
    to assess the level of bushfire defensible space in particular locations       
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    LAND_USE_RASTER = 'LAND_USE_RASTER'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return AssessingVulerabilityProcessingAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'viticulturescript'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Viticulture tool')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('MajorProject')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'majorprojectcripts'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr("This tool will help you "
                       "to classify each structure as more or less vulnerable "
                       "to bushfire due to values you enter into parameters:"
                       "Vegetation type, distance to nearest feature, wind direction."
                       "\nParameters:"
                       "\n- Land use layer: layer contains land cover types"                       
                       "\n- Vineyard layer: Raster layer contains areas have already plant grapes")

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # We add the input vector features source. It can have any kind of
        # geometry.
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.LAND_USE_RASTER,
                self.tr('Select land cover layer'),
                [QgsProcessing.TypeRaster]
            )
        )
        
        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.OUTPUT,
                self.tr('Viticulture layer'),
                QgsProcessing.TypeVectorAnyGeometry,
                #'vineyard_final.shp'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        land_use_raster = self.parameterAsRasterLayer(
            parameters,
            self.LAND_USE_RASTER,
            context
        )

        outputFile = self.parameterAsOutputLayer(
            parameters,
            self.OUTPUT,
            context
        )
        #1. Set up local variables
        #1.1 Variables for temporary data       
        suitable_land_use = 'suit_lu.tif'
        dem = 'DEM.tif'
        slope = 'slope.tif'
        suitable_slope = 'suit_slope.tif'
        existing_vineyard = 'existing_vineyard.tif'
        urban = 'urban.tif'
        result_raster = "result_lu.tif"
        result_pol = "result_pol.shp"
        vineyard_final = "vineyard_final.shp"
        
        #1.2 Setup data path
        chosen_file = self.parameterDefinition('LAND_USE_RASTER').valueAsPythonString(parameters['LAND_USE_RASTER'],
                                                                                      context)
        data_path = os.path.dirname(chosen_file[1:]) + '/'
        feedback.pushInfo('Data path: {}'.format(data_path))
              
        #2. Filter suitable landuse for grape growing
        feedback.pushInfo('\nfiltering land use: {}'.format(data_path + suitable_land_use))
        processing.runAndLoadResults("qgis:rastercalculator",
                                     {'EXPRESSION': '("land_use@1" > 1 AND "land_use@1" < 9) * "land_use@1"',
                                      'LAYERS': land_use_raster,
                                      'CELLSIZE': 0,
                                      'EXTENT': None,
                                      'CRS': None,
                                      'OUTPUT': data_path + suitable_land_use})

        #3. Create slope from DEM
        feedback.pushInfo('making slope: {}'.format(data_path + slope))
        processing.run("native:slope",
                       {'INPUT': data_path + dem,
                        'Z_FACTOR': 1,
                        'OUTPUT': data_path + slope})

        #4. Find areas with slope less than 20 degrees
        feedback.pushInfo('filtering slope: {}'.format(data_path + suitable_slope))
        processing.runAndLoadResults("qgis:rastercalculator",
                                     {'EXPRESSION': '("slope@1" <= 20) * 1',
                                      'LAYERS': data_path + slope,
                                      'CELLSIZE': 0,
                                      'EXTENT': None,
                                      'CRS': None,
                                      'OUTPUT': data_path + suitable_slope})

        #5. Combine slope raster with land use raster to find suitable areas with slope less than 20 degrees
        #6. Remove areas that are in residential
        #7. Remove areas that are planting grapes
        feedback.pushInfo('\nFilter land use to exclude residential and vineyard')
        feedback.pushInfo('landuse: ' + chosen_file)
        feedback.pushInfo('slope: ' + data_path + slope)
        feedback.pushInfo('existing_vineyard: ' + data_path + existing_vineyard)
        feedback.pushInfo('urban: ' + data_path + urban)
        processing.run("qgis:rastercalculator",
                       {
                           'EXPRESSION': '("suit_slope@1" =1 AND "suit_lu@1">0 AND "urban@1"=1 AND "existing_vineyard@1"=1)*1',
                           'LAYERS': [data_path + suitable_slope,
                                      data_path + suitable_land_use,
                                      data_path + urban,
                                      data_path + existing_vineyard],
                           'CELLSIZE': 0,
                           'EXTENT': None,
                           'CRS': None,
                           'OUTPUT': data_path + result_raster})

        #8. Convert raster suitable land to polygon
        processing.run("gdal:polygonize",
                       {'INPUT': data_path + result_raster,
                        'BAND': 1, 'FIELD': 'DN', 'EIGHT_CONNECTEDNESS': False, 'EXTRA': '',
                        'OUTPUT': data_path + result_pol})

        #9. Calculate areas of land that suitable for grape growing
        #9.1 Add area field
        result_lu_layer = QgsVectorLayer(data_path + result_pol, result_pol[:-4], 'ogr')
        result_lu_layer.startEditing()
        feedback.pushInfo('\nAdding area field')
        pr = result_lu_layer.dataProvider()
        pr.addAttributes([QgsField("area", QVariant.Double)])
        result_lu_layer.updateFields()  # tell the vector layer to fetch changes from the provider

        #9.2 Calculate areas
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(result_lu_layer))
        expression1 = QgsExpression('$area')

        features = result_lu_layer.getFeatures()
        # Compute the number of steps to display within the progress bar
        total = 100.0 / result_lu_layer.featureCount() if result_lu_layer.featureCount() else 0
        for current, feat in enumerate(features):
            context.setFeature(feat)
            feat['area'] = expression1.evaluate(context)
            # Save changes to feature
            result_lu_layer.updateFeature(feat)
            # Update the progress bar
            feedback.setProgress(int(current * total))
        result_lu_layer.commitChanges()

        #10. Remove areas which have area less than 4 hectares
        #10.1 Select regions with area > 4 hectares
        feedback.pushInfo('Select area that greater than 4 hectares')
        query = '$area > 40000 and DN=1'
        result_lu_layer.selectByExpression(query)
      
        #10.2 Exported selected objects to shape file       
        feedback.pushInfo('Exporting data. Output: ' + outputFile)
        su_lu_layer = processing.run("native:saveselectedfeatures",
                   {'INPUT': result_lu_layer,
                    'FILE_TYPE':1,
                    'OUTPUT': outputFile})
                    
        feedback.pushInfo('Adding to map')
        
        return {self.OUTPUT: su_lu_layer }

    def flags(self):
        return QgsProcessingAlgorithm.FlagNoThreading
