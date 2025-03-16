import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
const APIBASE_URL = process.env.REACT_APP_API_BASE_URL;
const GeoAICommandWindow = ({ layers, onCommandResult }) => {
  const [query, setQuery] = useState('');
  const [history, setHistory] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const historyEndRef = useRef(null);
  
  // Auto-scroll to bottom of history
  useEffect(() => {
    if (historyEndRef.current) {
      historyEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [history]);
  
  const handleQuerySubmit = async (e) => {
    e.preventDefault();
    
    if (!query.trim()) return;
    
    // Add query to history
    setHistory(prev => [...prev, { type: 'command', text: query }]);
    setIsProcessing(true);
    
    try {
      // Send query to backend
      const response = await axios.post(`${APIBASE_URL}/process-gis-query`, {
        query,
        context: {
          layers: layers.map(layer => ({
            name: layer.name,
            id: layer.id,
            visible: layer.visible,
            type: layer.data.features && layer.data.features[0]?.geometry?.type || 'Unknown'
          }))
        }
      });
      
      // Add result to history
      setHistory(prev => [
        ...prev, 
        { 
          type: 'result',
          text: `${response.data.message}`,
          details: response.data.results?.length > 0 ? 
            `${response.data.results.length} result(s) added to map.` : 
            ""
        }
      ]);
      
      // Process multiple results if available
      if (response.data.results && response.data.results.length > 0) {
        // Process each result
        response.data.results.forEach(result => {
          if (result.geojson) {
            const geojsonResult = result.geojson;
            
            // Parse if it's a string
            if (typeof geojsonResult === 'string') {
              try {
                const parsedGeoJSON = JSON.parse(geojsonResult);
                onCommandResult(parsedGeoJSON, result.name || `Result ${Date.now()}`);
              } catch (e) {
                setHistory(prev => [
                  ...prev,
                  { type: 'error', text: `Failed to parse GeoJSON: ${e.message}` }
                ]);
              }
            } else {
              // It's already an object
              onCommandResult(geojsonResult, result.name || `Result ${Date.now()}`);
            }
          }
        });
      } else if (response.data.geojson) {
        // Handle single result in alternative format
        onCommandResult(response.data.geojson, response.data.name || `Result ${Date.now()}`);
      }
    } catch (error) {
      setHistory(prev => [
        ...prev,
        { 
          type: 'error', 
          text: `Failed to process AI command: ${error.response?.data?.detail || error.message}` 
        }
      ]);
    } finally {
      setIsProcessing(false);
      setQuery('');
    }
  };
  
  const toggleMinimize = () => {
    setIsMinimized(prev => !prev);
  };
  
  // Helper to format history items
  const formatHistoryItem = (item, index) => {
    switch (item.type) {
      case 'command':
        return (
          <div key={index} className="message-container user-message">
            <div className="message-bubble user-bubble">
              {item.text}
            </div>
          </div>
        );
      case 'result':
        return (
          <div key={index} className="message-container ai-message">
            <div className="message-bubble ai-bubble">
              <div className="ai-message-text">{item.text}</div>
              {item.details && <div className="ai-message-details">{item.details}</div>}
            </div>
          </div>
        );
      case 'error':
        return (
          <div key={index} className="message-container ai-message">
            <div className="message-bubble error-bubble">
              {item.text}
            </div>
          </div>
        );
      default:
        return (
          <div key={index} className="message-container ai-message">
            <div className="message-bubble ai-bubble">
              {item.text}
            </div>
          </div>
        );
    }
  };
  
  return (
    <div className={`geo-command-chat ${isMinimized ? 'minimized' : ''}`}>
      <div className="chat-header">
        <div className="chat-title">
          <div className="chat-icon">🌍</div>
          <span>GeoAI Assistant</span>
        </div>
        <button onClick={toggleMinimize} className="minimize-button">
          {isMinimized ? '↗' : '↘'}
        </button>
      </div>
      
      {!isMinimized && (
        <>
          <div className="chat-history">
            {history.length === 0 ? (
              <div className="welcome-message">
                <div className="message-container ai-message">
                  <div className="message-bubble ai-bubble">
                    <div className="ai-message-text">Welcome to GeoAI Assistant! Ask me to process your geospatial data in natural language.</div>
                    <div className="example-commands">
                      <div className="example-command">Try: <span>buffer all buildings by 100 meters</span></div>
                      <div className="example-command">Try: <span>What tools do you have available?</span></div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              history.map(formatHistoryItem)
            )}
            {isProcessing && (
              <div className="message-container ai-message">
                <div className="message-bubble ai-bubble typing">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={historyEndRef} />
          </div>
          
          <form onSubmit={handleQuerySubmit} className="chat-input-form">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="chat-input"
              placeholder="Ask GeoAI something..."
              disabled={isProcessing}
            />
            <button 
              type="submit" 
              className="send-button"
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

export default GeoAICommandWindow;