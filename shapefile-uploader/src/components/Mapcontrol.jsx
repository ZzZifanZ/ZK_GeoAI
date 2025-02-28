// components/MapControls.jsx
import React from 'react';
import { useMap } from 'react-leaflet';

const MapControls = ({ basemap, setBasemap }) => {
  const map = useMap();
  
  const handleBasemapChange = (e) => {
    setBasemap(e.target.value);
  };
  
  return (
    <div className="map-control">
      <select 
        className="basemap-selector" 
        value={basemap} 
        onChange={handleBasemapChange}
      >
        <option value="osm">OpenStreetMap</option>
        <option value="satellite">Satellite</option>
        <option value="topo">Topographic</option>
      </select>
    </div>
  );
};

export default MapControls;