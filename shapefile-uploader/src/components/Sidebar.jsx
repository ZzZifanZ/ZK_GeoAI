// components/Sidebar.jsx
import React, { useState, useRef } from 'react';

const Sidebar = ({ 
  selectedFiles, 
  handleFiles, 
  formatFileSize, 
  uploadShapefile,
  selectedColor,
  setSelectedColor,
  layers,
  toggleLayerVisibility,
  statusMessage
}) => {
  const [isComplete, setIsComplete] = useState(false);
  const [missingFiles, setMissingFiles] = useState([]);
  const fileInputRef = useRef(null);
  
  const onFilesSelected = (e) => {
    const files = e.target.files || (e.dataTransfer && e.dataTransfer.files);
    if (files && files.length > 0) {
      const result = handleFiles(files);
      setIsComplete(result.isComplete);
      setMissingFiles(result.missingFiles);
    }
  };
  
  const handleDragOver = (e) => {
    e.preventDefault();
    e.currentTarget.classList.add('active');
  };
  
  const handleDragLeave = (e) => {
    e.currentTarget.classList.remove('active');
  };
  
  const handleDrop = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('active');
    onFilesSelected(e);
  };
  
  const handleColorSelect = (color) => {
    setSelectedColor(color);
  };
  
  return (
    <div className="sidebar">
      <div className="upload-section">
        <h2 className="upload-title">Upload Shapefile</h2>
        <div 
          className="file-drop-area" 
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current.click()}
        >
          <input 
            type="file" 
            ref={fileInputRef}
            className="file-input" 
            multiple 
            accept=".shp,.shx,.dbf"
            onChange={onFilesSelected}
          />
          <div className="upload-icon">📁</div>
          <p className="upload-text">Drag &amp; drop files or click to browse</p>
          <p className="upload-text" style={{ fontSize: '13px', opacity: 0.8 }}>
            Required: .shp, .shx, .dbf files
          </p>
        </div>
        
        <div className="file-list">
          {selectedFiles.map((file, index) => (
            <div key={index} className="file-item">
              <div className="file-name">{file.name}</div>
              <div className="file-size">{formatFileSize(file.size)}</div>
            </div>
          ))}
          
          {!isComplete && missingFiles.length > 0 && (
            <div className="file-item" style={{ color: '#dc3545', backgroundColor: '#f8d7da' }}>
              Missing: {missingFiles.join(', ')}
            </div>
          )}
        </div>
        
        <button 
          className="upload-btn" 
          disabled={!isComplete} 
          onClick={uploadShapefile}
        >
          Upload Shapefile
        </button>
        
        {statusMessage.visible && (
          <div className={`status-message ${statusMessage.type}`} style={{ display: 'block' }}>
            {statusMessage.type === 'loading' && <span className="loading-spinner"></span>}
            {statusMessage.text}
          </div>
        )}
      </div>
      
      <div className="style-section">
        <h2 className="upload-title">Style Options</h2>
        <p className="upload-text">Choose display color:</p>
        <div className="color-picker">
          {[
            '#3388ff', '#ff5733', '#33ff57', '#5733ff', 
            '#ff33a8', '#33a8ff', '#a833ff', '#ffc233'
          ].map(color => (
            <div 
              key={color}
              className={`color-option ${selectedColor === color ? 'selected' : ''}`} 
              style={{ backgroundColor: color }} 
              onClick={() => handleColorSelect(color)}
            />
          ))}
        </div>
      </div>
      
      <div className="layers-section">
        <h2 className="upload-title">Layers</h2>
        <div className="layer-list">
          {layers.length === 0 ? (
            <p className="upload-text">No layers loaded yet</p>
          ) : (
            layers.map(layer => (
              <div key={layer.id} className="layer-item">
                <input 
                  type="checkbox" 
                  className="layer-checkbox"
                  checked={layer.visible}
                  onChange={(e) => toggleLayerVisibility(layer.id, e.target.checked)}
                />
                <div 
                  className="layer-color" 
                  style={{ backgroundColor: layer.color }}
                />
                <span>{layer.name}</span>
              </div>
            ))
          )}
        </div>
      </div>
      
      <div className="info-section">
        <h3 className="info-title">About</h3>
        <p className="info-text">This application lets you visualize GIS shapefiles on an interactive map.</p>
        <p className="info-text">Upload a complete shapefile set (.shp, .shx, .dbf) to view geographic data.</p>
        <p className="info-text">Click on features to see their attributes.</p>
      </div>
    </div>
  );
};

export default Sidebar;