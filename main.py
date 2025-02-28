from fastapi import FastAPI, File, UploadFile
import shutil
import geopandas as gpd
from pathlib import Path
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware  # Import CORS middleware

app = FastAPI()

# Add CORS middleware to allow all origins (you can specify particular origins if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can specify a list of origins here if needed (e.g., ["http://localhost:3000"])
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/")
def read_root():
    return {"message": "Hello, GIS World!"}

@app.post("/upload/")
async def upload_shapefiles(files: list[UploadFile] = File(...)):
    file_dict = {}

    # Organize files by their extensions (e.g., .shp, .shx, .dbf)
    for file in files:
        file_extension = file.filename.split('.')[-1]
        if file_extension not in file_dict:
            file_dict[file_extension] = []
        file_dict[file_extension].append(file)
    
    # Ensure all required file types (.shp, .shx, .dbf) are present
    required_file_types = ['shp', 'shx', 'dbf']
    missing_files = [f"{file}.shp" for file in required_file_types if file not in file_dict]
    
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

        # Convert GeoDataFrame to GeoJSON
        geojson_data = gdf.to_json()

        return JSONResponse(content=geojson_data)
    except Exception as e:
        return {"error": str(e)}
