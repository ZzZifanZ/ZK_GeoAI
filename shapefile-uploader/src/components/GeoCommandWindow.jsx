import React, { useState, useRef, useEffect } from 'react';

const GeoCommandWindow = ({ onCommandResult }) => {
  const [command, setCommand] = useState('');
  const [history, setHistory] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const historyEndRef = useRef(null);
  
  // Auto-scroll to bottom of history
  useEffect(() => {
    if (historyEndRef.current) {
      historyEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [history]);
  
  const handleCommandSubmit = async (e) => {
    e.preventDefault();
    
    if (!command.trim()) return;
    
    // Add command to history
    setHistory(prev => [...prev, { type: 'command', text: command }]);
    setIsProcessing(true);
    
    try {
      // Send command to backend
      const response = await fetch('https://zk-geoai.onrender.com/execute-command/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ command })
      });
      
      const data = await response.json();
      
      // Add result to history
      setHistory(prev => [
        ...prev, 
        { 
          type: data.error ? 'error' : 'result',
          text: data.error || data.result
        }
      ]);
      
      // If there's GeoJSON data, pass it to parent component
      if (data.geojson) {
        onCommandResult(data.geojson);
      }
    } catch (error) {
      setHistory(prev => [
        ...prev,
        { type: 'error', text: `Failed to execute command: ${error.message}` }
      ]);
    } finally {
      setIsProcessing(false);
      setCommand('');
    }
  };
  
  const toggleCommandWindow = () => {
    setIsOpen(prev => !prev);
  };
  
  // Helper to format history items
  const formatHistoryItem = (item, index) => {
    switch (item.type) {
      case 'command':
        return <div key={index} className="command-history-item command">$ {item.text}</div>;
      case 'result':
        return <div key={index} className="command-history-item result">{item.text}</div>;
      case 'error':
        return <div key={index} className="command-history-item error">{item.text}</div>;
      default:
        return <div key={index} className="command-history-item">{item.text}</div>;
    }
  };
  
  return (
    <div className={`geo-command-window ${isOpen ? 'open' : 'closed'}`}>
      <div className="command-header">
        <span>GDAL/Python Command Window</span>
        <button onClick={toggleCommandWindow} className="toggle-button">
          {isOpen ? '▼' : '▲'}
        </button>
      </div>
      
      {isOpen && (
        <>
          <div className="command-history">
            {history.length === 0 ? (
              <div className="command-welcome">
                <p>Welcome to the GIS Command Interface</p>
                <p>Type Python/GDAL commands to process your shapefiles</p>
                <p>Example: <code>buffer_layer("Layer 1", 0.01)</code></p>
              </div>
            ) : (
              history.map(formatHistoryItem)
            )}
            <div ref={historyEndRef} />
          </div>
          
          <form onSubmit={handleCommandSubmit} className="command-form">
            <div className="command-prompt">$</div>
            <input
              type="text"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              className="command-input"
              placeholder="Enter Python/GDAL command..."
              disabled={isProcessing}
            />
            <button 
              type="submit" 
              className="command-submit"
              disabled={isProcessing}
            >
              {isProcessing ? '⏳' : '➤'}
            </button>
          </form>
        </>
      )}
    </div>
  );
};

export default GeoCommandWindow;