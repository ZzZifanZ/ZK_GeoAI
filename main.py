from fastapi import FastAPI, File, UploadFile
import shutil
import geopandas as gpd
from pathlib import Path

app = FastAPI()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/")
def read_root():
    return {"message": "Hello, GIS World!"}

@app.post("/upload/")
async def upload_shapefile(file: UploadFile = File(...)):
    file_location = UPLOAD_DIR / file.filename
    
    # Save uploaded file
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Read shapefile
    try:
        gdf = gpd.read_file(file_location)
        return {"filename": file.filename, "columns": list(gdf.columns)}
    except Exception as e:
        return {"error": str(e)}
