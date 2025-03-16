from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import traceback
import geopandas as gpd
import json
from pathlib import Path

import tempfile
import sys
import io
import contextlib
from typing import Dict, Any, Optional, List
import rasterio
from rasterio.plot import reshape_as_image
import numpy as np
from openai import OpenAI
from pydantic import BaseModel
from typing import Dict, Any, Annotated, TypedDict, List, Any


import operator

from langgraph.prebuilt import tools_condition, ToolNode
from langgraph.graph import StateGraph, END

import logging

import inspect
import os

from dotenv import load_dotenv
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
app = FastAPI(title="GIS Intelligent Assistant")
client = OpenAI(api_key=API_KEY)
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

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CommandRequest(BaseModel):
    command: str

class GISQueryRequest(BaseModel):
    query: str
    context: Dict[str, Any] = {}  # Optional additional context

class AgentState(TypedDict):
    messages: Annotated[List[Dict[str, Any]], operator.add]
    actions: List[str]
    params_dict: Dict[str, Dict[str, Any]] 
    results: List[Dict[str, Any]]
    intermediate_layers: List[str]

# Dictionary of available GIS operations
gis_operations = {
    "buffer_layer": "Create a buffer around features in a layer",
    "intersection": "Find the geometric intersection between two layers",
    "union": "Combine two layers into one",
    "clip": "Clip a layer using another layer as boundary",
    "dissolve": "Merge features in a layer based on an attribute",
    "simplify": "Simplify geometries in a layer",
    "reproject_layer": "Change the coordinate system of a layer",
    "points_within_polygon": "Find points that fall within polygons",
    "get_layers_info": "List all layer information"
}

class OperationDependencyTracker:
    """Tracks GIS operations and their dependencies for chaining multi-step workflows"""
    
    def __init__(self):
        self.operations = []
        self.dependencies = {}
        self.results = {}
    
    def add_operation(self, operation_id, operation_type, params):
        """Add an operation to the tracker"""
        self.operations.append({
            "id": operation_id,
            "type": operation_type,
            "params": params,
            "status": "pending"
        })
        
        # Track dependencies by analyzing parameters
        self.dependencies[operation_id] = []
        for param_name, param_value in params.items():
            if isinstance(param_value, str) and param_value.startswith("Result_"):
                self.dependencies[operation_id].append(param_value)
    
    def get_executable_operations(self):
        """Get operations that can be executed (all dependencies satisfied)"""
        executable = []
        for op in self.operations:
            if op["status"] != "pending":
                continue
                
            deps = self.dependencies[op["id"]]
            if all(dep in self.results for dep in deps):
                # All dependencies are satisfied
                executable.append(op)
        
        return executable
    
    def mark_completed(self, operation_id, result):
        """Mark an operation as completed and store its result"""
        for op in self.operations:
            if op["id"] == operation_id:
                op["status"] = "completed"
                break
                
        self.results[operation_id] = result
    
    def resolve_dependencies(self, params):
        """Resolve references to operation results in parameters"""
        resolved_params = {}
        for key, value in params.items():
            # If value is a reference to an operation result
            if isinstance(value, str) and value in self.results:
                # Use the mapped layer ID if available
                if hasattr(self, 'id_mapping') and value in self.id_mapping:
                    resolved_params[key] = self.id_mapping[value]
                else:
                    resolved_params[key] = self.results[value]
            else:
                resolved_params[key] = value
        return resolved_params

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

def buffer_layer(layer_name, distance):
    
    if layer_name not in LOADED_LAYERS:
        raise ValueError(f"Layer '{layer_name}' not found")
    
    layer = LOADED_LAYERS[layer_name]
    if isinstance(distance, str):
        distance_f = float(distance)
    else:
        distance_f = distance
    
    # If already in a projected CRS, buffer directly
    buffered = layer.copy()
    buffered['geometry'] = layer.geometry.buffer(distance_f)
    
    return buffered

def get_layer_metadata(layer):
    if layer is None or len(layer) == 0:
        return {"valid": False, "error": "Layer is empty or invalid."}
    
    metadata = {
        "valid": True,
        "feature_count": len(layer),
        "geometry_types": list(layer.geometry.geom_type.unique()),
        "crs": str(layer.crs),
        "bbox": layer.total_bounds.tolist() if layer.total_bounds is not None else None,
        "attributes": {},
        "numeric_stats": {},
    }

    for col in layer.columns:
        if col != "geometry":
            dtype = str(layer[col].dtype)
            metadata["attributes"][col] = {
                "dtype": dtype,
                "unique_values": int(layer[col].nunique()),
                "sample": str(layer[col].iloc[0])[:50],
            }

            if dtype in ["int64", "float64"]:
                metadata["numeric_stats"][col] = {
                    "min": layer[col].min(),
                    "max": layer[col].max(),
                    "mean": layer[col].mean(),
                    "std": layer[col].std(),
                }

    return metadata

def get_layers_info(layer):
    
    """
    Command to list detailed information about a specific GeoDataFrame layer.
    
    Args:
        layer (GeoDataFrame): The GeoDataFrame layer to inspect
    
    Returns:
        str: Formatted text description of the layer
    """
    Layer_temp = get_layer_metadata(LOADED_LAYERS(layer))
    print(Layer_temp)
    return Layer_temp


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
    
    return gpd.overlay(layer1, layer2, how='intersection', keep_geom_type=False)

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

def reproject_layer(layer_name):
    """
    Reproject a layer to the specified EPSG coordinate system.
    
    Args:
        layer_name: The name of the layer to reproject
        epsg: The target EPSG code (default: 4326 for WGS84)
        
    Returns:
        A new GeoDataFrame with the reprojected geometries
    """
    epsg = 4326
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

def create_gis_agent(model_name="gpt-4"):
    # Define the graph
    graph_builder = StateGraph(AgentState)
    
    # Define the main assistant node
    def assistant_node(state: AgentState):
        """Process user input and generate a response with possible GIS actions"""
        # Prepare messages with system context
        messages = [
            {
                "role": "system",
                "content": f"""You are an advanced GIS (Geographic Information System) assistant.
                Provide detailed explanations about geographic concepts, spatial analysis, and
                GIS technologies. 
                
                If the user's request requires GIS operations, analyze what they need and suggest 
                appropriate GIS actions from this list of available operations:
                
                {json.dumps(gis_operations, indent=2)}
                
                When you identify a GIS operation, include both the operation type and the parameters needed in your response using this format:
                [GIS_ACTION:operation_name:param1=value1:param2=value2]
                
                For example:
                - [GIS_ACTION:buffer_layer:layer_name=Layer 1:distance=500]
                - [GIS_ACTION:intersection:layer1_name=Layer 1:layer2_name=Layer 2]
                
                For multi-step operations, provide ALL steps in the correct sequence. 
                Each step will create a intermediate result that can be referenced in subsequent steps.
                
                Make sure the result layer are being called in the format of: Result_ID

                When referring to results from previous steps, use the format Layer ID:
                - Step 1: [GIS_ACTION:buffer_layer:layer_name=Layer 1:distance=500]
                - Step 2: [GIS_ACTION:intersection:layer1_name=Layer 2:layer2_name=Layer 3]
                - Step 3: ..
                
                Ensure each step's output is properly referenced as input for subsequent steps.
                Don't suggest operations unless they're clearly relevant to the user's query.
                
                IMPORTANT: Pay attention if the user specifies how many steps they want. If they ask for a 
                solution with a specific number of steps (e.g., "solve this in 2 steps"), limit your response 
                to exactly that many GIS operations. If they say the solution requires too many steps, 
                try to simplify your approach to use fewer operations while still achieving the result. Additionally,
                you must provide any question related to this specific software, meaning understand the avaible functions you have
                """
            }
        ]
        
        # Add conversation history
        for msg in state['messages']:
            messages.append(msg)
        
        try:
            # Call OpenAI API instead of Ollama
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            # Extract content from OpenAI response
            try:
                content = response.choices[0].message.content
            except Exception as e:
                logger.error(f"Error extracting content from OpenAI response: {e}")
                content = "I'm having trouble processing your request."
            
            # Identify GIS actions and parameters in the response using regex
            import re
            action_patterns = re.findall(r'\[GIS_ACTION:(\w+)(?::([^\]]+))?\]', content)
            actions = []
            params_dict = {}
            
            for action, params_str in action_patterns:
                actions.append(action)
                # Parse parameters if they exist
                if params_str:
                    params = {}
                    param_pairs = params_str.split(':')
                    for pair in param_pairs:
                        if '=' in pair:
                            key, value = pair.split('=', 1)
                            params[key.strip()] = value.strip()
                    params_dict[action] = params
            
            logger.info(f"Identified actions: {actions} with parameters: {params_dict}")
            
            # Clean up the response by removing the action tags
            cleaned_content = re.sub(r'\[GIS_ACTION:\w+(?::[^\]]+)?\]', '', content).strip()
            
            # Return the state update
            return {
                "messages": state['messages'] + [
                    {
                        "role": "assistant",
                        "content": cleaned_content
                    }
                ],
                "actions": actions,
                "params_dict": params_dict,
                "results": [],
                "intermediate_layers": []
            }
            
        except Exception as e:
            logger.error(f"Error in assistant node: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "messages": state['messages'] + [
                    {
                        "role": "assistant",
                        "content": f"I encountered an issue processing your request. Please try again."
                    }
                ],
                "actions": [],
                "params_dict": {},
                "results": [],
                "intermediate_layers": []
            }
    
    # Define the action processor node
    def action_processor(state: AgentState):
        """Process multi-step GIS actions with dependency tracking"""
        actions = state.get('actions', [])
        params_dict = state.get('params_dict', {})
        results = []
        
        # Create a dependency tracker
        tracker = OperationDependencyTracker()
        
        # Get all available GIS functions from your code
        available_functions = {
            "buffer_layer": buffer_layer,
            "intersection": intersection,
            "union": union_layers,
            "clip": clip_layer,
            "dissolve": dissolve_layer,
            "simplify": simplify_layer,
            "reproject_layer": reproject_layer,
            "points_within_polygon": points_within_polygon,
            "get_layers_info": get_layers_info,
        }
        
        # Register all operations in the tracker
        for i, action in enumerate(actions):
            operation_id = f"Result_{len(LOADED_LAYERS)+i+1}"  # Use i to ensure unique IDs
            tracker.add_operation(operation_id, action, params_dict.get(action, {}))
        
        # Track which operations we've already processed to avoid infinite loops
        processed_ops = set()
        
        # Process executable operations until all are complete
        while True:
            executable = tracker.get_executable_operations()
            # Filter out operations we've already processed
            executable = [op for op in executable if op["id"] not in processed_ops]
            
            if not executable:
                break  # No more operations can be executed
                
            for op in executable:
                operation_id = op["id"]
                # Mark this operation as processed immediately to prevent re-processing
                processed_ops.add(operation_id)
                action = op["type"]
                
                try:
                    # Get the function
                    if action not in available_functions:
                        results.append({
                            "action": action,
                            "status": "unknown_action",
                            "message": f"Unknown GIS action: {action}",
                            "step": int(operation_id.split("_")[1])
                        })
                        tracker.mark_completed(operation_id, None)
                        continue
                        
                    func = available_functions[action]
                    
                    # Resolve dependencies with actual results
                    params = tracker.resolve_dependencies(op["params"])
                    
                    # Check required parameters
                    sig = inspect.signature(func)
                    param_names = list(sig.parameters.keys())
                    
                    missing_params = [p for p in param_names if p not in params and 
                                    sig.parameters[p].default == inspect.Parameter.empty]
                    
                    if missing_params:
                        results.append({
                            "action": action,
                            "status": "parameter_missing",
                            "message": f"Missing required parameters for {action}: {', '.join(missing_params)}",
                            "step": int(operation_id.split("_")[1])
                        })
                        tracker.mark_completed(operation_id, None)
                        continue
                    
                    # Filter parameters to only include those accepted by the function
                    filtered_params = {k: v for k, v in params.items() if k in param_names}
                    
                    # Execute the function with the parameters
                    result_data = func(**filtered_params)
                    
                    # Process the result
                    if isinstance(result_data, gpd.GeoDataFrame):
                        # Create a consistent layer ID
                        layer_id = f"Layer {len(LOADED_LAYERS)+1}"
                        
                        # Store with the Layer ID format
                        LOADED_LAYERS[layer_id] = result_data
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"LOADED_LAYERS keys after: {list(LOADED_LAYERS.keys())}")
                        
                        # Convert to GeoJSON for the frontend
                        geojson_data = json.loads(result_data.to_json())
                        
                        # Ensure proper GeoJSON structure
                        if "type" not in geojson_data:
                            geojson_data = {
                                "type": "FeatureCollection",
                                "features": geojson_data.get("features", [])
                            }
                        
                        # Mark operation as completed and store result, but map the operation_id to the layer_id
                        tracker.mark_completed(operation_id, result_data)
                        
                        # Create a mapping between operation_id and layer_id for future reference
                        if not hasattr(tracker, 'id_mapping'):
                            tracker.id_mapping = {}
                        tracker.id_mapping[operation_id] = layer_id
                        
                        results.append({
                            "action": action,
                            "status": "executed",
                            "message": f"Successfully executed {action}. Created layer: {layer_id}",
                            "result": layer_id,  # Use layer_id in the results
                            "geojson": geojson_data,
                            "step": int(operation_id.split("_")[1])
                        })
                    else:
                        # For other types of results
                        tracker.mark_completed(operation_id, result_data)
                        
                        results.append({
                            "action": action,
                            "status": "executed",
                            "message": f"Successfully executed {action}",
                            "result": str(result_data),
                            "step": int(operation_id.split("_")[1])
                        })
                    
                except Exception as e:
                    # Handle errors
                    logger.error(f"Error executing {action}: {str(e)}")
                    logger.error(traceback.format_exc())
                    
                    results.append({
                        "action": action,
                        "status": "error",
                        "message": f"Error executing {action}: {str(e)}",
                        "step": int(operation_id.split("_")[1])
                    })
                    
                    # Mark as completed even though it failed
                    tracker.mark_completed(operation_id, None)
        
        return {
            "results": results,
            "intermediate_layers": list(tracker.results.keys())
        }
    
    # Define the routing logic
    def should_process_actions(state: AgentState):
        """Determine if we should process GIS actions"""
        if state.get('actions'):
            return "action_processor"
        return END
    
    # Add nodes to the graph
    graph_builder.add_node("assistant", assistant_node)
    graph_builder.add_node("action_processor", action_processor)
    
    # Set entry point
    graph_builder.set_entry_point("assistant")
    
    # Add conditional edges
    graph_builder.add_conditional_edges(
        "assistant",
        should_process_actions
    )
    
    # Add edge from action processor back to END
    graph_builder.add_edge("action_processor", END)
    
    # Compile the graph
    return graph_builder.compile()

@app.post("/process-gis-query")
async def process_gis_query(request: GISQueryRequest):
    try:
        logger.info(f"Received GIS Query: {request.query}")
        
        # Create agent
        agent = create_gis_agent()
        
        # Initialize state with params_dict
        initial_state = {
            "messages": [{"role": "user", "content": request.query}],
            "actions": [],
            "params_dict": {},
            "results": [],
            "intermediate_layers": []
        }
        
        # Run the agent
        try:
            result = agent.invoke(initial_state)
            
            # Extract the assistant's response
            assistant_messages = [msg for msg in result["messages"] if msg["role"] == "assistant"]
            response_content = assistant_messages[-1]["content"] if assistant_messages else "No response generated."
            
            # Log the full result (not truncated)
            logger.info(f"Agent response: {response_content}")
            
            # Prepare response data
            response_data = {
                "status": "success",
                "message": response_content,
                "actions": result.get("actions", []),
                "results": result.get("results", []),
                "query": request.query,
                "intermediate_layers": result.get("intermediate_layers", [])
            }
            
            # Include all GeoJSON data for each step
            geojson_steps = {}
            for res in result.get("results", []):
                if "geojson" in res and "step" in res:
                    step_num = res["step"]
                    geojson_steps[f"step_{step_num}"] = {
                        "layer_name": res.get("result", f"Step {step_num}"),
                        "action": res.get("action", "unknown"),
                        "geojson": res["geojson"]
                    }
            
            # Add all steps to the response
            if geojson_steps:
                response_data["geojson_steps"] = geojson_steps
                
                # For backward compatibility, include the final result geojson at the top level
                final_step = max(geojson_steps.keys(), key=lambda k: int(k.split('_')[1]), default=None)
                if final_step:
                    response_data["geojson"] = geojson_steps[final_step]["geojson"]
            
            return response_data
            
        except Exception as e:
            logger.error(f"Agent execution error: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "status": "error",
                "message": f"Error running GIS agent: {str(e)}"
            }
            
    except Exception as e:
        logger.error(f"Request processing error: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e)
        }

# Basic health check endpoint
@app.get("/")
def read_root():
    return {"message": "GIS Intelligent Assistant API is running"}
# GIS Functions that will be available in the command window
# Example usage
'''if __name__ == "__main__":
    # Initialize the GIS agent builder
    gis_agent_builder = GISAgentBuilder()

    # Example queries
    queries = [
        "Create a spatial index for urban land use dataset",
        "Perform spatial analysis to identify potential development areas in a specific region",
        "Generate a high-resolution terrain model for mountain terrain"
    ]

    # Run the agent for each query
    for query in queries:
        print(f"\nQuery: {query}")
        result = gis_agent_builder.run(query)
        print("Final Agent State:", json.dumps(result, indent=2))'''