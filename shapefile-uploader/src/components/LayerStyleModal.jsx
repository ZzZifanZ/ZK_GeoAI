// components/LayerStyleModal.jsx
import React, { useState } from 'react';

const LayerStyleModal = ({ layer, onClose, onApplyChanges }) => {
  const [styleOptions, setStyleOptions] = useState({
    color: layer.color,
    opacity: layer.opacity || 0.3,
    weight: layer.weight || 2,
    fillOpacity: layer.fillOpacity || 0.3,
    dashArray: layer.dashArray || '',
  });
  
  const handleChange = (property, value) => {
    setStyleOptions(prev => ({
      ...prev,
      [property]: value
    }));
  };
  
  return (
    <div className="style-modal-overlay">
      <div className="style-modal">
        <div className="style-modal-header">
          <h3>Style: {layer.name}</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        
        <div className="style-modal-body">
          <div className="style-option">
            <label>Color:</label>
            <div className="color-picker">
              {[
                '#3388ff', '#ff5733', '#33ff57', '#5733ff', 
                '#ff33a8', '#33a8ff', '#a833ff', '#ffc233',
                '#ff3333', '#33fff8', '#b0ff33', '#333333'
              ].map(color => (
                <div 
                  key={color}
                  className={`color-option ${styleOptions.color === color ? 'selected' : ''}`} 
                  style={{ backgroundColor: color }} 
                  onClick={() => handleChange('color', color)}
                />
              ))}
            </div>
          </div>
          
          <div className="style-option">
            <label>Line Weight:</label>
            <input 
              type="range" 
              min="1" 
              max="10" 
              value={styleOptions.weight} 
              onChange={(e) => handleChange('weight', parseInt(e.target.value))}
            />
            <span>{styleOptions.weight}px</span>
          </div>
          
          <div className="style-option">
            <label>Line Opacity:</label>
            <input 
              type="range" 
              min="0" 
              max="1" 
              step="0.1" 
              value={styleOptions.opacity} 
              onChange={(e) => handleChange('opacity', parseFloat(e.target.value))}
            />
            <span>{styleOptions.opacity * 100}%</span>
          </div>
          
          <div className="style-option">
            <label>Fill Opacity:</label>
            <input 
              type="range" 
              min="0" 
              max="1" 
              step="0.1" 
              value={styleOptions.fillOpacity} 
              onChange={(e) => handleChange('fillOpacity', parseFloat(e.target.value))}
            />
            <span>{styleOptions.fillOpacity * 100}%</span>
          </div>
          
          <div className="style-option">
            <label>Line Style:</label>
            <select 
              value={styleOptions.dashArray} 
              onChange={(e) => handleChange('dashArray', e.target.value)}
            >
              <option value="">Solid</option>
              <option value="5,5">Dashed</option>
              <option value="1,5">Dotted</option>
              <option value="10,5,1,5">Dash-Dot</option>
            </select>
          </div>
        </div>
        
        <div className="style-modal-footer">
          <button className="cancel-btn" onClick={onClose}>Cancel</button>
          <button 
            className="apply-btn" 
            onClick={() => {
              onApplyChanges(layer.id, styleOptions);
              onClose();
            }}
          >
            Apply Changes
          </button>
        </div>
      </div>
    </div>
  );
};

export default LayerStyleModal;