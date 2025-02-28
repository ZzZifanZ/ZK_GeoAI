from fastapi import FastAPI, File, UploadFile
import shutil
import geopandas as gpd
import json
from pathlib import Path
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

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
    required_file_types = ['shp', 'shx', 'dbf']
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