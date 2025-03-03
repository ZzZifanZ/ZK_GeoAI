from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import geopandas as gpd
import json
from pathlib import Path
import os
import tempfile
import sys
import io
import contextlib
from typing import Dict, Any, Optional, List

app = FastAPI()

# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Store loaded layers in memory for operations
LOADED_LAYERS: Dict[str, gpd.GeoDataFrame] = {}

class CommandRequest(BaseModel):
    command: str

@app.get("/")
def read_root():
    return {"message": "Hello, GIS World!"}

@app.post("/upload/")
async def upload_shapefiles(files: list[UploadFile] = File(...)):
    file_dict = {}

    # Organize files by their extensions
    for file in files:
        file_extension = file.filename.split('.')[-1]
        if file_extension not in file_dict:
            file_dict[file_extension] = []
        file_dict[file_extension].append(file)
    
    # Ensure all required file types are present
    required_file_types = ['shp', 'shx', 'dbf','prj']
    missing_files = [f"{file}" for file in required_file_types if file not in file_dict]
    
    if missing_files:
        return {"error": f"Missing shapefile components: {', '.join(missing_files)}"}
    
    # Save the uploaded files
    for files in file_dict.values():
        for file in files:
            file_location = UPLOAD_DIR / file.filename
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
    
    # Read the .shp file using geopandas
    try:
        shp_file = [file for file in file_dict.get('shp', [])][0]
        shp_file_location = UPLOAD_DIR / shp_file.filename
        gdf = gpd.read_file(shp_file_location)
        
        # Store the layer in memory
        layer_name = f"Layer {len(LOADED_LAYERS) + 1}"
        LOADED_LAYERS[layer_name] = gdf

        # Convert GeoDataFrame to GeoJSON - ensure it's a proper GeoJSON structure
        geojson_data = json.loads(gdf.to_json())
        
        # Make sure we have a valid GeoJSON structure
        if "type" not in geojson_data or "features" not in geojson_data:
            # Create a proper GeoJSON structure if it's missing
            geojson_data = {
                "type": "FeatureCollection",
                "features": geojson_data if isinstance(geojson_data, list) else []
            }
        
        return geojson_data
    except Exception as e:
        return {"error": f"Error processing shapefile: {str(e)}"}

@app.post("/execute-command/")
async def execute_command(command_request: CommandRequest):
    command = command_request.command.strip()
    
    # Create a dictionary of functions available to the command
    available_functions = {
        # GIS processing functions
        "buffer_layer": buffer_layer,
        "intersection": intersection,
        "union": union_layers,
        "clip": clip_layer,
        "dissolve": dissolve_layer,
        "simplify": simplify_layer,
        "reproject_layer":reproject_layer,
        "points_within_polygon":points_within_polygon,
        
        # Layer management
        "get_layer": get_layer,
        "list_layers": list_layers,
        "layer_info": layer_info,
        
        # Import core modules that might be needed
        "gpd": gpd,
        "pd": gpd.pd,  # pandas is included with geopandas
        
        # Make loaded layers available
        "layers": LOADED_LAYERS
    }
    
    # Create sandbox for command execution
    local_vars = available_functions.copy()
    
    # Capture stdout and stderr
    stdout = io.StringIO()
    stderr = io.StringIO()
    result = None
    geojson_data = None
    
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            # Execute the command
            exec(f"result = {command}", globals(), local_vars)
            
            # Get the result from local variables
            result = local_vars.get("result")
            
            # If result is a GeoDataFrame, convert to GeoJSON
            if isinstance(result, gpd.GeoDataFrame):
                # Store as a new layer
                print("hehe")
                new_layer_name = f"Result {len(LOADED_LAYERS) + 1}"
                LOADED_LAYERS[new_layer_name] = result
                print(f"Layers after adding new layer: {LOADED_LAYERS.keys()}")
                # Convert to GeoJSON for the frontend
                geojson_data = json.loads(result.to_json())
                
                # Add layer name to the output
                stdout_content = f"Created new layer: {new_layer_name}\n" + stdout.getvalue()
            else:
                stdout_content = stdout.getvalue()
                
    except Exception as e:
        # Return the error message
        return {"error": f"Error: {str(e)}\n{stderr.getvalue()}"}
    
    # Format the result for display
    if result is not None and stdout_content.strip() == "":
        if isinstance(result, (gpd.GeoDataFrame, dict, list)):
            output = f"Operation completed successfully"
        else:
            output = str(result)
    else:
        output = stdout_content.strip() or "Command executed successfully"
    
    response = {"result": output}
    
    # Include GeoJSON data if available
    if geojson_data:
        response["geojson"] = geojson_data
    
    return response

# GIS Functions that will be available in the command window

def buffer_layer(layer_name, distance):
    """
    Buffer features in a layer by a specified distance.
    
    Args:
        layer_name: The name of the layer to buffer
        distance: Buffer distance in the layer's coordinate system units
        
    Returns:
        A new GeoDataFrame with buffered geometries
    """
    if layer_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer_name}' not found")
    
    layer = LOADED_LAYERS[layer_name]
  
    buffered = layer.copy()
    buffered['geometry'] = layer.copy().buffer(distance)
    print (buffered)
    return buffered

def intersection(layer1_name, layer2_name):
    """
    Find the geometric intersection between two layers.
    
    Args:
        layer1_name: The name of the first layer
        layer2_name: The name of the second layer
        
    Returns:
        A new GeoDataFrame with intersection geometries
    """
    if layer1_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer1_name}' not found")
    if layer2_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer2_name}' not found")
    
    layer1 = LOADED_LAYERS[layer1_name]
    layer2 = LOADED_LAYERS[layer2_name]
    
    return gpd.overlay(layer1, layer2, how='intersection')

def union_layers(layer1_name, layer2_name):
    """
    Find the union of two layers.
    
    Args:
        layer1_name: The name of the first layer
        layer2_name: The name of the second layer
        
    Returns:
        A new GeoDataFrame with union geometries
    """
    if layer1_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer1_name}' not found")
    if layer2_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer2_name}' not found")
    
    layer1 = LOADED_LAYERS[layer1_name]
    layer2 = LOADED_LAYERS[layer2_name]
    
    return gpd.overlay(layer1, layer2, how='union')

def clip_layer(layer_name, clip_layer_name):
    """
    Clip a layer using another layer as the clip boundary.
    
    Args:
        layer_name: The name of the layer to clip
        clip_layer_name: The name of the layer to use as clip boundary
        
    Returns:
        A new GeoDataFrame with clipped geometries
    """
    if layer_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer_name}' not found")
    if clip_layer_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{clip_layer_name}' not found")
    
    layer = LOADED_LAYERS[layer_name]
    clip_boundary = LOADED_LAYERS[clip_layer_name]
    
    return gpd.clip(layer, clip_boundary)

def dissolve_layer(layer_name, column=None):
    """
    Dissolve features in a layer.
    
    Args:
        layer_name: The name of the layer to dissolve
        column: Optional column to dissolve by
        
    Returns:
        A new GeoDataFrame with dissolved geometries
    """
    if layer_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer_name}' not found")
    
    layer = LOADED_LAYERS[layer_name]
    return layer.dissolve(by=column).reset_index()

def simplify_layer(layer_name, tolerance):
    """
    Simplify geometries in a layer.
    
    Args:
        layer_name: The name of the layer to simplify
        tolerance: The tolerance for simplification
        
    Returns:
        A new GeoDataFrame with simplified geometries
    """
    if layer_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer_name}' not found")
    
    layer = LOADED_LAYERS[layer_name]
    return layer.copy().geometry.simplify(tolerance).to_frame()

def get_layer(layer_name):
    """
    Get a layer by name.
    
    Args:
        layer_name: The name of the layer to get
        
    Returns:
        The GeoDataFrame for the requested layer
    """
    if layer_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer_name}' not found")
    
    return LOADED_LAYERS[layer_name]

def list_layers():
    """
    List all available layers.
    
    Returns:
        A list of layer names
    """
    return list(LOADED_LAYERS.keys())

def layer_info(layer_name):
    """
    Get information about a layer.
    
    Args:
        layer_name: The name of the layer to get info for
        
    Returns:
        A dictionary with layer information
    """
    if layer_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer_name}' not found")
    
    layer = LOADED_LAYERS[layer_name]
    
    return {
        "name": layer_name,
        "geometry_type": layer.geometry.geom_type.value_counts().to_dict(),
        "crs": str(layer.crs),
        "feature_count": len(layer),
        "columns": list(layer.columns),
        "bounds": layer.total_bounds.tolist()
    }

def reproject_layer(layer_name, epsg=4326):
    """
    Reproject a layer to the specified EPSG coordinate system.
    
    Args:
        layer_name: The name of the layer to reproject
        epsg: The target EPSG code (default: 4326 for WGS84)
        
    Returns:
        A new GeoDataFrame with the reprojected geometries
    """
    if layer_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer_name}' not found")

    layer = LOADED_LAYERS[layer_name]

    if layer.crs is None:
        raise ValueError(f"Layer '{layer_name}' does not have a CRS. Please set the CRS before reprojecting.")

    return layer.to_crs(epsg=epsg)

def points_within_polygon(points_layer_name, polygon_layer_name):
    if points_layer_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{points_layer_name}' not found")
    if polygon_layer_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{polygon_layer_name}' not found")

    points = LOADED_LAYERS[points_layer_name]
    polygons = LOADED_LAYERS[polygon_layer_name]

    if points.crs != polygons.crs:
        polygons = polygons.to_crs(points.crs)

    # Perform spatial join
    result = gpd.sjoin(points, polygons, predicate="within", how="inner")

    return result