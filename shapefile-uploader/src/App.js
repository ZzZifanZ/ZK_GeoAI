// App.jsx - Main application file
import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import './App.css';

// Components
import Sidebar from './components/Sidebar.jsx';
import MapControls from './components/Mapcontrol.jsx';
import L from 'leaflet';
import 'leaflet-easyprint';

import LayerStyleModal from './components/LayerStyleModal.jsx';
import FeatureInfo from './components/FeatureInfo.jsx';
import GeoAICommandWindow from './components/GeoAICommandWindow.jsx';
import GeoCommandWindow from './components/GeoCommandWindow.jsx';
const App = () => {
  // State variables
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [selectedColor, setSelectedColor] = useState('#3388ff');
  const [layers, setLayers] = useState([]);
  const [activeFeature, setActiveFeature] = useState(null);
  const [activeProperties, setActiveProperties] = useState(null);
  const [statusMessage, setStatusMessage] = useState({ text: '', type: '', visible: false });
  const [basemap, setBasemap] = useState('osm');
  const mapRef = useRef(null);

  const [editingLayerId, setEditingLayerId] = useState(null);
  // Handle file selection
  const handleFiles = (files) => {
    // Reset selection
    const newSelectedFiles = [];
    let hasShp = false;
    let hasShx = false;
    let hasDbf = false;
    let hasPrj = false;
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const extension = file.name.split('.').pop().toLowerCase();
      
      if (['shp', 'shx', 'dbf','prj'].includes(extension)) {
        newSelectedFiles.push(file);
        
        if (extension === 'shp') hasShp = true;
        if (extension === 'shx') hasShx = true;
        if (extension === 'dbf') hasDbf = true;
        if (extension === 'prj') hasPrj = true;
      }
    }
    
    setSelectedFiles(newSelectedFiles);
    return { isComplete: hasShp && hasShx && hasDbf && hasPrj, missingFiles: getMissingFiles(hasShp, hasShx, hasDbf,hasPrj) };
  };
  // Add this function to your GeoSpatialApp component
  const getMissingFiles = (hasShp, hasShx, hasDbf,hasPrj) => {
    const missingFiles = [];
    if (!hasShp) missingFiles.push('.shp');
    if (!hasShx) missingFiles.push('.shx');
    if (!hasDbf) missingFiles.push('.dbf');
    if (!hasDbf) missingFiles.push('.prj');
    return missingFiles;
  };
  
  // Format file size
  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' bytes';
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / 1048576).toFixed(1) + ' MB';
  };
  const setupPrintButtonListener = (map) => {
    const printButtons = document.querySelectorAll('.leaflet-control-easyPrint a');
    
    printButtons.forEach(button => {
      button.addEventListener('click', () => {
        // Hide the basemap controls before printing
        const mapControls = document.querySelectorAll('.leaflet-control-basemapSelector, .other-control-class');
        mapControls.forEach(control => {
          control.style.display = 'none';
        });
        
        // Set a timeout to show controls again after printing
        setTimeout(() => {
          mapControls.forEach(control => {
            control.style.display = '';
          });
        }, 1000); // Adjust timing as needed
      });
    });
  };
  // Upload shapefile
  const uploadShapefile = async () => {
    // Show loading message
    setStatusMessage({
      text: 'Uploading shapefile...',
      type: 'loading',
      visible: true
    });
    
    try {
      const formData = new FormData();
      
      // Add all files to FormData
      for (const file of selectedFiles) {
        formData.append('files', file);
      }
      
      // Send files to backend
      const response = await fetch('http://127.0.0.1:8000/upload/', {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      
      if (response.ok) {
        // Check if the response contains an error
        if (data.error) {
          throw new Error(data.error);
        }
        
        // Success - add layer to map
        setStatusMessage({
          text: 'Shapefile loaded successfully!',
          type: 'success',
          visible: true
        });
        
        // Parse GeoJSON (if it's a string) or use the object directly
        const geojsonData = typeof data === 'string' ? JSON.parse(data) : data;
        
        // Add layer to map
        addGeoJsonLayer(geojsonData);
        
        // Clear file selection
        setSelectedFiles([]);
      } else {
        throw new Error(data.error || 'Failed to upload shapefile');
      }
    } catch (error) {
      console.error('Error:', error);
      setStatusMessage({
        text: `Error: ${error.message}`,
        type: 'error',
        visible: true
      });
    } finally {
      // Hide status message after 5 seconds
      setTimeout(() => {
        setStatusMessage(prev => ({ ...prev, visible: false }));
      }, 5000);
    }
  };
  
  // Add GeoJSON layer
  const addGeoJsonLayer = (geojsonData) => {
    // Create a unique name for the layer
    const layerName = `Layer ${layers.length + 1}`;
    
    // Create new layer
    const newLayer = {
      id: Date.now(),
      name: layerName,
      color: selectedColor,
      data: geojsonData,
      visible: true
    };
    
    // Add to layers
    setLayers(prevLayers => [...prevLayers, newLayer]);
  };
  
  // Handle command result
  const handleCommandResult = (geojsonData) => {
        if (!geojsonData) return;
      
      // Create a meaningful name based on the geometry type
      let layerName = "Command Result";
      
      if (geojsonData.features && geojsonData.features.length > 0) {
        const geometryType = geojsonData.features[0].geometry.type;
        layerName = `${geometryType} Result ${layers.length + 1}`;
      }
      
      // Create new layer with a different color than the default
      const newLayer = {
        id: Date.now(),
        name: layerName,
        color: '#FF4500', // Use a distinctive color for results
        data: geojsonData,
        visible: true,
        isCommandResult: true // Flag to identify command results
      };
      
      // Add to layers
      setLayers(prevLayers => [...prevLayers, newLayer]);
      
      // Notify user
      setStatusMessage({
        text: 'Command executed and result visualized on map!',
        type: 'success',
        visible: true
      });
      
      setTimeout(() => {
        setStatusMessage(prev => ({ ...prev, visible: false }));
      }, 5000);
      
      // If it's a single point, you might want to add a marker instead of a polygon
      if (geojsonData.features && 
          geojsonData.features.length === 1 && 
          geojsonData.features[0].geometry.type === 'Point') {
        // The map will fit to this point because of your MapUpdater component
      }
  };
  
  // Toggle layer visibility
  const toggleLayerVisibility = (layerId, visible) => {
    setLayers(prevLayers => 
      prevLayers.map(layer => 
        layer.id === layerId ? { ...layer, visible } : layer
      )
    );
  };
  const updateLayerStyle = (layerId, styleOptions) => {
  setLayers(prevLayers => 
    prevLayers.map(layer => 
      layer.id === layerId ? { ...layer, ...styleOptions } : layer
    )
  );
};
  // Feature click handler
  const onFeatureClick = (e, layerId) => {
    // Reset active feature if clicking on a different one
    if (activeFeature && activeFeature.layerId !== layerId) {
      setActiveFeature(null);
    }
    
    // Set new active feature
    setActiveFeature({
      layerId,
      featureId: e.target.feature.id || Math.random().toString(36).substring(7)
    });
    
    // Show properties
    setActiveProperties(e.target.feature.properties);
  };
  
  // Clear selection on map click
  const onMapClick = () => {
    setActiveFeature(null);
    setActiveProperties(null);
  };
  
  // MapUpdater component to handle map actions
  const MapUpdater = ({ layers, activeFeature }) => {
    const map = useMap();
    
    useEffect(() => {
      // Add map click handler
    
      map.on('click', onMapClick);
      const easyPrintControl = L.easyPrint({
        title: 'Export Map',
        position: 'topleft',
        sizeModes: ['Current', 'A4Portrait', 'A4Landscape'],
        exportOnly: true,
        hideControlContainer: true,
        hideClasses: ['basemap-selector'] // Add any custom control class names here
      }).addTo(map);


      return () => {
        map.off('click', onMapClick);
        if (easyPrintControl){
          map.removeControl(easyPrintControl)
        }
      };
    }, [map]);
    
    // Fit bounds when new layers are added
    useEffect(() => {
      if (layers.length > 0) {
        const lastLayer = layers[layers.length - 1];
        try {
          // Create a temporary GeoJSON layer to get bounds
          const tempLayer = L.geoJSON(lastLayer.data);
          if (tempLayer.getBounds().isValid()) {
            map.fitBounds(tempLayer.getBounds());
          }
        } catch (error) {
          console.error("Error fitting bounds:", error);
        }
      }
    }, [layers.length]);
    // Add this after your existing useEffect hooks
    
    return null;
  };
  
  // GeoJSON style function

  const getLayerStyle = (feature, layer, isActive, layerStyle) => {
    const { color, opacity, weight, fillOpacity, dashArray } = layerStyle;
    
    if (isActive) {
      return {
        weight: weight || 4,
        color: '#555',
        opacity: opacity || 1,
        fillColor: color,
        fillOpacity: fillOpacity || 0.7,
        dashArray: dashArray || ''
      };
    } else {
      return {
        weight: weight || 2,
        color: color,
        opacity: opacity || 1,
        fillColor: color,
        fillOpacity: fillOpacity || 0.3,
        dashArray: dashArray || ''
      };
    }
  };
  
  const updateLayerColor = (layerId, newColor) => {
    setLayers(prevLayers => 
      prevLayers.map(layer => 
        layer.id === layerId ? { ...layer, color: newColor } : layer
      )
    );
  };

  const whiteMarkerIcon = L.divIcon({
    className: 'leaflet-div-icon', // Ensures it uses a div element for styling
    html: '<div style="background-color: white; border-radius: 50%; width: 20px; height: 20px; border: 2px solid #333;"></div>',
    iconSize: [20, 20],  // Adjust size as needed
    iconAnchor: [10, 10], // Center the icon on the marker
  });

  return (
    <div className="container">
      <header>
        <h1>ZK AIGeo</h1>
        <p className="description">Upload and visualize geospatial data on an interactive map</p>
      </header>
      
      <div className="app-container">
        <Sidebar 
          selectedFiles={selectedFiles}
          handleFiles={handleFiles}
          formatFileSize={formatFileSize}
          uploadShapefile={uploadShapefile}
          selectedColor={selectedColor}
          setSelectedColor={setSelectedColor}
          layers={layers}
          toggleLayerVisibility={toggleLayerVisibility}
          updateLayerColor={updateLayerColor}
          setEditingLayerId ={setEditingLayerId}
          statusMessage={statusMessage}
        />
        
        <div className="map-container">
          <MapContainer
            center={[0, 0]}
            zoom={2}
            style={{ height: "100%", width: "100%" }}
            ref={mapRef}
          >
            {/* Base layers */}
            
              {basemap === 'osm' && (
                <TileLayer
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />
              )}
              {basemap === 'satellite' && (
                <TileLayer
                  url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                  attribution='Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
                />
              )}
              {basemap === 'topo' && (
                <TileLayer
                  url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
                  attribution='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
                />
              )}
           
            
            {/* GeoJSON Layers */}
            {layers.filter(layer => layer.visible).map(layer => (
              <GeoJSON
                key={layer.id}
                data={layer.data}
                style={(feature) => getLayerStyle(
                  feature,
                  null,
                  activeFeature && activeFeature.layerId === layer.id && 
                    activeFeature.featureId === (feature.id || feature.properties.id),
                  layer
                )}
                onEachFeature={(feature, leafletLayer) => {
                  leafletLayer.on({
                    click: (e) => {
                      onFeatureClick(e, layer.id);
                      L.DomEvent.stopPropagation(e);
                    }
                  });
                }}

                pointToLayer={(feature, latlng) => {
                  // Check if the feature is a Point
                  if (feature.geometry.type === 'Point') {
                    // Get the layer by ID (you'll need to pass the current layer to this function)
                    const currentLayer = layer;
                    
                    // Create a custom marker icon with the layer's color
                    const customMarkerIcon = L.divIcon({
                      className: 'leaflet-div-icon',
                      html: `<div style="
                        background-color: ${currentLayer.color}; 
                        border-radius: 50%; 
                        width: 20px; 
                        height: 20px; 
                        border: 2px solid #333;
                        opacity: ${currentLayer.fillOpacity || 0.7};
                      "></div>`,
                      iconSize: [20, 20],
                      iconAnchor: [10, 10],
                    });
                    
                    return L.marker(latlng, { icon: customMarkerIcon });
                  }
                }}



              />



              ))}
              
              <MapUpdater layers={layers} activeFeature={activeFeature} />
              <MapControls setBasemap={setBasemap} currentBasemap={basemap} />
            </MapContainer>
            {editingLayerId !== null && (
              <LayerStyleModal
                layer={layers.find(layer => layer.id === editingLayerId)}
                onClose={() => setEditingLayerId(null)}
                onApplyChanges={updateLayerStyle}
              />
            )}
            {activeProperties && (
              <FeatureInfo 
                properties={activeProperties} 
                onClose={() => {
                  setActiveFeature(null);
                  setActiveProperties(null);
                }} 
              />
            )}
          </div>
          
          <GeoAICommandWindow 
             layers={layers}
            onCommandResult={handleCommandResult}
          />

          
        </div>
      </div>
    );
  };
  
  export default App;