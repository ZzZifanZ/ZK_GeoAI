 // DOM Elements
 const fileDropArea = document.getElementById('file-drop-area');
 const fileInput = document.getElementById('file-input');
 const fileList = document.getElementById('file-list');
 const uploadButton = document.getElementById('upload-button');
 const statusMessage = document.getElementById('status-message');
 const colorPicker = document.getElementById('color-picker');
 const layerList = document.getElementById('layer-list');
 const basemapSelector = document.getElementById('basemap-selector');
 const featureInfo = document.getElementById('feature-info');
 const propertiesTable = document.getElementById('properties-table');
 
 // State variables
 let selectedFiles = [];
 let selectedColor = '#3388ff';
 let layers = [];
 let activeFeature = null;
 
 // Initialize map
 const map = L.map('map').setView([0, 0], 2);
 
 // Base layers
 const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
     attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
 }).addTo(map);
 
 const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
     attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
 });
 
 const topoLayer = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
     attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
 });
 
 const baseLayers = {
     'osm': osmLayer,
     'satellite': satelliteLayer,
     'topo': topoLayer
 };
 
 // Event Listeners
 // Drag and drop
 fileDropArea.addEventListener('dragover', (e) => {
     e.preventDefault();
     fileDropArea.classList.add('active');
 });
 
 fileDropArea.addEventListener('dragleave', () => {
     fileDropArea.classList.remove('active');
 });
 
 fileDropArea.addEventListener('drop', (e) => {
     e.preventDefault();
     fileDropArea.classList.remove('active');
     
     if (e.dataTransfer.files.length > 0) {
         handleFiles(e.dataTransfer.files);
     }
 });
 
 // File input change
 fileInput.addEventListener('change', () => {
     if (fileInput.files.length > 0) {
         handleFiles(fileInput.files);
     }
 });
 
 // Upload button click
 uploadButton.addEventListener('click', uploadShapefile);
 
 // Color picker
 colorPicker.addEventListener('click', (e) => {
     if (e.target.classList.contains('color-option')) {
         const colorOptions = document.querySelectorAll('.color-option');
         colorOptions.forEach(option => option.classList.remove('selected'));
         
         e.target.classList.add('selected');
         selectedColor = e.target.getAttribute('data-color');
     }
 });
 
 // Basemap selector
 basemapSelector.addEventListener('change', () => {
     const selectedBasemap = basemapSelector.value;
     
     // Remove all base layers
     map.removeLayer(osmLayer);
     map.removeLayer(satelliteLayer);
     map.removeLayer(topoLayer);
     
     // Add the selected base layer
     map.addLayer(baseLayers[selectedBasemap]);
 });
 
 // Map click to clear selection
 map.on('click', () => {
     featureInfo.style.display = 'none';
     
     if (activeFeature) {
         layers.forEach(layerInfo => {
             layerInfo.layer.resetStyle(activeFeature);
         });
         activeFeature = null;
     }
 });
 
 // Functions
 function handleFiles(files) {
     // Reset selection
     selectedFiles = [];
     fileList.innerHTML = '';
     
     let hasShp = false;
     let hasShx = false;
     let hasDbf = false;
     
     for (let i = 0; i < files.length; i++) {
         const file = files[i];
         const extension = file.name.split('.').pop().toLowerCase();
         
         if (['shp', 'shx', 'dbf'].includes(extension)) {
             selectedFiles.push(file);
             
             if (extension === 'shp') hasShp = true;
             if (extension === 'shx') hasShx = true;
             if (extension === 'dbf') hasDbf = true;
             
             // Create file item in the list
             const fileItem = document.createElement('div');
             fileItem.className = 'file-item';
             
             const fileName = document.createElement('div');
             fileName.className = 'file-name';
             fileName.textContent = file.name;
             
             const fileSize = document.createElement('div');
             fileSize.className = 'file-size';
             fileSize.textContent = formatFileSize(file.size);
             
             fileItem.appendChild(fileName);
             fileItem.appendChild(fileSize);
             fileList.appendChild(fileItem);
         }
     }
     
     // Check if we have all required files
     const isComplete = hasShp && hasShx && hasDbf;
     
     if (!isComplete) {
         const missingFiles = [];
         if (!hasShp) missingFiles.push('.shp');
         if (!hasShx) missingFiles.push('.shx');
         if (!hasDbf) missingFiles.push('.dbf');
         
         const warningItem = document.createElement('div');
         warningItem.className = 'file-item';
         warningItem.style.color = '#dc3545';
         warningItem.style.backgroundColor = '#f8d7da';
         warningItem.textContent = `Missing: ${missingFiles.join(', ')}`;
         fileList.appendChild(warningItem);
     }
     
     uploadButton.disabled = !isComplete;
 }
 
 function formatFileSize(bytes) {
     if (bytes < 1024) return bytes + ' bytes';
     else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
     else return (bytes / 1048576).toFixed(1) + ' MB';
 }
 
 async function uploadShapefile() {
     // Show loading message
     statusMessage.innerHTML = '<span class="loading-spinner"></span> Uploading shapefile...';
     statusMessage.className = 'status-message';
     statusMessage.style.display = 'block';
     uploadButton.disabled = true;
     
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
             statusMessage.className = 'status-message success';
             statusMessage.textContent = 'Shapefile loaded successfully!';
             
             // Parse GeoJSON (if it's a string) or use the object directly
             const geojsonData = typeof data === 'string' ? JSON.parse(data) : data;
             
             // Add layer to map
             addGeoJsonLayer(geojsonData);
             
             // Clear file selection
             selectedFiles = [];
             fileList.innerHTML = '';
             fileInput.value = '';
         } else {
             throw new Error(data.error || 'Failed to upload shapefile');
         }
     } catch (error) {
         console.error('Error:', error);
         statusMessage.className = 'status-message error';
         statusMessage.textContent = `Error: ${error.message}`;
     } finally {
         uploadButton.disabled = false;
         
         // Hide status message after 5 seconds
         setTimeout(() => {
             statusMessage.style.display = 'none';
         }, 5000);
     }
 }
 
 function addGeoJsonLayer(geojsonData) {
     // Create a unique name for the layer
     const layerName = `Layer ${layers.length + 1}`;
     
     // Create GeoJSON layer
     const geoJsonLayer = L.geoJSON(geojsonData, {
         style: {
             color: selectedColor,
             weight: 2,
             opacity: 1,
             fillOpacity: 0.3
         },
         onEachFeature: (feature, layer) => {
             // Add click event to show properties
             layer.on('click', (e) => {
                 L.DomEvent.stopPropagation(e);
                 
                 // Reset style of previous selection
                 if (activeFeature) {
                     geoJsonLayer.resetStyle(activeFeature);
                 }
                 
                 // Highlight the selected feature
                 layer.setStyle({
                     weight: 4,
                     color: '#555',
                     fillOpacity: 0.7
                 });
                 
                 activeFeature = layer;
                 
                 // Show properties
                 showFeatureProperties(feature.properties);
             });
         }
     }).addTo(map);
     
     // Fit map to layer bounds
     if (geoJsonLayer.getBounds().isValid()) {
         map.fitBounds(geoJsonLayer.getBounds());
     }
     
     // Store layer info
     layers.push({
         id: Date.now(),
         name: layerName,
         color: selectedColor,
         layer: geoJsonLayer,
         visible: true
     });
     
     // Update layer list
     updateLayerList();
 }
 
 function updateLayerList() {
     // Clear current list
     layerList.innerHTML = '';
     
     if (layers.length === 0) {
         const noLayers = document.createElement('p');
         noLayers.className = 'upload-text';
         noLayers.textContent = 'No layers loaded yet';
         layerList.appendChild(noLayers);
         return;
     }
     
     // Add each layer to the list
     layers.forEach(layerInfo => {
         const layerItem = document.createElement('div');
         layerItem.className = 'layer-item';
         
         const checkbox = document.createElement('input');
         checkbox.type = 'checkbox';
         checkbox.className = 'layer-checkbox';
         checkbox.checked = layerInfo.visible;
         checkbox.addEventListener('change', () => {
             toggleLayerVisibility(layerInfo.id, checkbox.checked);
         });
         
         const colorSwatch = document.createElement('div');
         colorSwatch.className = 'layer-color';
         colorSwatch.style.backgroundColor = layerInfo.color;
         
         const layerName = document.createElement('span');
         layerName.textContent = layerInfo.name;
         
         layerItem.appendChild(checkbox);
         layerItem.appendChild(colorSwatch);
         layerItem.appendChild(layerName);
         
         layerList.appendChild(layerItem);
     });
 }
 
 function toggleLayerVisibility(layerId, visible) {
     const layerInfo = layers.find(layer => layer.id === layerId);
     
     if (layerInfo) {
         layerInfo.visible = visible;
         
         if (visible) {
             map.addLayer(layerInfo.layer);
         } else {
             map.removeLayer(layerInfo.layer);
         }
     }
 }
 
 function showFeatureProperties(properties) {
     // Clear previous properties
     propertiesTable.innerHTML = '';
     
     // Add each property to the table
     for (const key in properties) {
         const row = document.createElement('tr');
         
         const keyCell = document.createElement('td');
         keyCell.textContent = key;
         
         const valueCell = document.createElement('td');
         valueCell.textContent = properties[key];
         
         row.appendChild(keyCell);
         row.appendChild(valueCell);
         propertiesTable.appendChild(row);
     }
     
     // Show the feature info panel
     featureInfo.style.display = 'block';
 }