'''
Get the average(ish) RGB code within each polygon of a given polygon dataset
'''

import arcpy
import numpy as np
import os
from arcpy.sa import *


class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Toolbox"
        self.alias = ""

        # List of tool classes associated with this toolbox
        self.tools = [Tool]


class Tool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Generalize Image: Average-ish RGB to Features"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""

        p0 = arcpy.Parameter(
            displayName = "Select your Image",
            name = "imgSrc",
            datatype = ["DERasterDataset", "GPRasterLayer"],
            parameterType = "Required",
            direction = "Input")
        
        p1 = arcpy.Parameter(
            displayName = "Source Image (Red Band)",
            name = "redBand",
            datatype = "String",
            parameterType = "Required",
            direction = "Input")
        p1.enabled = False

        p2 = arcpy.Parameter(
            displayName = "Source Image (Green Band)",
            name = "greenBand",
            datatype = "String",
            parameterType = "Required",
            direction = "Input")
        p2.enabled = False

        p3 = arcpy.Parameter(
            displayName = "Source Image (Blue Band)",
            name = "blueBand",
            datatype = "String",
            parameterType = "Required",
            direction = "Input")
        p3.enabled = False

        p4 = arcpy.Parameter(
            displayName = "Check this box if your image has an band you would like to use to control opacity (alpha band)",
            name = "hasAlpha",
            datatype = "Boolean",
            parameterType = "Optional",
            direction = "Required")
        p4.enabled = False

        p5 = arcpy.Parameter(
            displayName = "Source Image (Alpha Band)",
            name = "alphaBand",
            datatype = "String",
            parameterType = "Optional",
            direction = "Input")
        p5.enabled = False

        p6 = arcpy.Parameter(
            displayName = "Summary Layer (Must be polygons and must overlap image spatially)",
            name = "summaryLayer",
            datatype = ["GPFeatureLayer", "DEShapefile", "DEFeatureClass"],
            parameterType = "Required",
            direction = "Input")

        p7 = arcpy.Parameter(
            displayName = "Summary Layer: Unique ID Field",
            name = "summaryLayerIdField",
            datatype = "Field",
            parameterType = "Required",
            direction = "Input")
        p7.parameterDependencies = [p6.name]

        p8 = arcpy.Parameter(
            displayName = "Cool New Name for the Output Layer",
            name = "outputName",
            datatype = "DEFeatureClass",
            parameterType = "Required",
            direction = "Output")

        p9 = arcpy.Parameter(
            displayName = "Tuning Options: If your image is computer generated or contains text, consider one of these options",
            name = "usePointMethod",
            datatype = "String",
            parameterType = "Optional",
            direction = "Input")
        p9.filter.type = "Value List"
        p9.filter.list = ["Add Noise: Slower, minor color changes",]
                          #"Convert to Point: VERY Slow, 'most accurate' colors (no promises)"]
        
        params = [p0, p1, p2, p3, p4, p5, p6, p7, p8, p9]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, params):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        ws = arcpy.env.workspace
        srcImg = params[0]
        bandParams = params[1:4]
        useAlpha = params[4]
        bandAlpha = params[5]
        resetBands = False
    
        # Populate the band lists based on the input data
        # All logic for parameters is in here, because without the source image
        # you can't have any of the other things anyhow.
        if srcImg.value:
            srcImgInfo = arcpy.Describe(srcImg)
            # If someone created a layer from a single band of a multiband dataset,
            # the method bandCount won't exist... and I can't figure out why...
            try:
                bandCount = srcImgInfo.bandCount
            except:
                bandCount = 1
            if bandCount >= 3:
                arcpy.env.workspace = srcImgInfo.catalogPath
                bands = arcpy.ListRasters()
                arcpy.env.workspace = ws
                if srcImgInfo.bandCount > 3:
                    useAlpha.enabled = True
                    bandParams.append(bandAlpha)
                for bandParam in bandParams:
                    bandParam.enabled = True
                # Control which bands show up in band parameter
                selectedBands = [param.value for param in bandParams]
                availableBands = sorted(set(bands) - set(selectedBands))
                for bandParam in bandParams:
                    # When the selection happens, the selected band drops from the available band list
                    # This causes a validation error for the param you made the selection in, unless you
                    # add that parameters value back to the list of "OK" values for that parameter.
                    if bandParam.value in bands:
                        bandParam.filter.list = sorted(set(availableBands + [bandParam.value]))
                    else:
                        bandParam.filter.list = availableBands
            else:
                resetBands = True
                    
            # Control whether or not alpha shows up.
            if useAlpha.value == True:
                bandAlpha.enabled = True
            else:
                bandAlpha.enabled = False
        else:
            resetBands = True

        # If anything happened that causes us to need to hide + reset the bands, trigger this
        if resetBands:
            for bandParam in bandParams:
                bandParam.value = ''
                bandParam.enabled = False
            useAlpha.value = False
            useAlpha.enabled = False
            bandAlpha.value = ''
            bandAlpha.enabled = False
        
        # Control whether or not alpha shows up.
        if useAlpha.value == True:
            bandAlpha.enabled = True
        else:
            bandAlpha.value = ''
            bandAlpha.enabled = False
        
        arcpy.env.workspace = ws
        return

    def updateMessages(self, params):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""

        srcImg = params[0]

        # Custom messaging related to the fact that we need at least 3 bands
        try:
            bandCount = arcpy.Describe(srcImg).bandCount
        except:
            bandCount = -1
            srcImg.setErrorMessage("Could not identify image band information. Is this a multiband raster?")
        if bandCount < 3 and bandCount >= 1:
            srcImg.setErrorMessage("Your image should have at least three bands, only detected %s" % bandCount)
        else:
            srcImg.clearMessage()

        # Custom messaging to make the alpha band "required" if checked.
        # parameterType is read only, but we can add an error message if useAlpha = True & bandAlpha = False
        if params[4].value and not params[5].value:
            params[5].setErrorMessage("An opacity band was indicated above. Please select opacity band.")
        else:
            params[5].clearMessage()

        # Make sure that regardless of the way that someone pointed to their summary areas,
        # the data that they pointed to is polygon
        if params[6].altered:
            summaryLayerShapeType = arcpy.Describe(params[6].valueAsText).shapeType
            if summaryLayerShapeType.upper() != "POLYGON":
                params[6].setErrorMessage("Summary Areas Must be Polygons, not %s" % summaryLayerShapeType)
            else:
                params[6].clearMessage()

        # If the noise method is being used, check for spatial analyst
        if params[9].value:
            if "Add Noise" in params[9].valueAsText:
                if arcpy.CheckExtension("Spatial") == "Available":
                    params[9].clearMessage()
                else:
                    params[9].setErrorMessage("Adding noise requires a spatial analyst license. A spatial analyst license is not available.")
        
        return

    def execute(self, params, messages):
        """The source code of the tool, which sadly cannot be called 'hexecute' :( """

        arcpy.env.overwriteOutput = True
        arcpy.AddMessage("Reading Input Settings")

        srcImg = params[0].valueAsText
        bandRed = params[1].valueAsText
        bandGrn = params[2].valueAsText
        bandBlu = params[3].valueAsText
        useAlpha = params[4].value
        bandAlpha = params[5].valueAsText
        summaryGeom = params[6].valueAsText
        summaryGeomId = params[7].valueAsText
        output = params[8].valueAsText
        hexcellentOption = params[9].valueAsText

        # Store scratch outputs in the output geodatabase
        outGdb = os.path.dirname(output)
        scratch = []

        # Whatever path we take, we need the metadata from the source image
        srcImgInfo = arcpy.Describe(srcImg)

        # Make the hex layer, then process the data either as point or poly
        summaryGeom_lyr = arcpy.MakeFeatureLayer_management(summaryGeom, "summary geometry layer")
        
        if hexcellentOption and "Convert to Point" in hexcellentOption:
            pass
        else:
            # If the user specified the noise option, randomly adjust cells by 0, 1, or 2
            if hexcellentOption and "Add Noise" in hexcellentOption:
                # Going to use numpy to do this, but need to generate a raster that matches the inputs
                arcpy.AddMessage("Adding minor noise to break up large areas of continuous values")
                bandInfo = arcpy.Describe(os.path.join(srcImgInfo.catalogPath, bandRed))
                h = bandInfo.height
                w = bandInfo.width
                
                # Put the rasters sources in a list to make iteration easier
                rasters = [(bandRed, "red"), (bandGrn, "green"), (bandBlu, "blue")]

                # If alpha was requested, get it in the list to work on
                if useAlpha:
                    rasters.append((bandAlpha, "alpha"))

                # Layers corresponding to each band, these are used later
                bandLayers = []
                for raster, color in rasters:
                    noiseArray = np.random.randint(0, 3, size = (h, w))
                    noiseRaster = Raster(arcpy.NumPyArrayToRaster(noiseArray))
                    noiseRaster.save(os.path.join(outGdb, "modrst"))
                    modRaster = Raster(os.path.join(srcImgInfo.catalogPath, raster)) + noiseRaster
                    modRaster_saveAs = (os.path.join(outGdb, color + "_withNoise"))
                    modRaster.save(modRaster_saveAs)
##                    scratch.append(modRaster)
                    bandLayers.append((arcpy.MakeRasterLayer_management(modRaster_saveAs, "band %s mod layer" % color), color))
                    
            else:
                # Make layers for each of the raster datasets
                arcpy.AddMessage("Process imagery...")
                bandRed_lyr = arcpy.MakeRasterLayer_management(os.path.join(srcImgInfo.catalogPath, bandRed), "band red layer")
                bandGrn_lyr = arcpy.MakeRasterLayer_management(os.path.join(srcImgInfo.catalogPath, bandGrn), "band green layer")
                bandBlu_lyr = arcpy.MakeRasterLayer_management(os.path.join(srcImgInfo.catalogPath, bandBlu), "band blue layer")

                # Put the rasters layers in a list to make iteration easier
                bandLayers = [(bandRed_lyr, "red"),
                              (bandGrn_lyr, "green"),
                              (bandBlu_lyr, "blue")]

                # If alpha was requested, get it in the list to work on
                if useAlpha:
                    bandAlpha_lyr = arcpy.MakeRasterLayer_management(os.path.join(srcImgInfo.catalogPath, bandAlpha))
                    bandLayers.append((bandAlpha_lyr, "alpha"))
            # Convert each raster band into a polygon dataset
            arcpy.AddMessage("... export raster data to polygon")
            bandPolygons = []
            for band, color in bandLayers:
                arcpy.AddMessage("... ... working on %s band" % color)
                bandPoly_name = os.path.join(outGdb, color + "_band")
                bandPoly_lyr = arcpy.RasterToPolygon_conversion(band, bandPoly_name)
                arcpy.AlterField_management(bandPoly_lyr, "gridcode", color)
                scratch.append(bandPoly_lyr)
                scratch.append(bandPoly_name)
                bandPolygons.append(bandPoly_lyr)
            # Use union to get to the dataset we will need to dissolve
            arcpy.AddMessage("... executing union on bands & summary areas")
            unionResult_name = os.path.join(outGdb, "hexify_union")
            unionResult_lyr = arcpy.Union_analysis([summaryGeom_lyr] + bandPolygons, unionResult_name)
            scratch.append(unionResult_lyr)
            scratch.append(unionResult_name)
            scratch.append(os.path.join(outGdb + "hexify_union"))

        # Perform the final dissolve
        arcpy.AddMessage("Perform final dissolve")
        statsFields = [[color, "MEAN"] for band, color in bandLayers]
        result = arcpy.Dissolve_management(unionResult_lyr, output, summaryGeomId, statsFields, "SINGLE_PART")

        # Cleanup
        arcpy.AddMessage("Cleaning up scratch data.")
        for item in scratch:
            arcpy.Delete_management(item)

        arcpy.AddMessage("Done - Happy Mapping!")

        return
