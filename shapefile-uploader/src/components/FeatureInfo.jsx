// components/FeatureInfo.jsx
import React from 'react';

const FeatureInfo = ({ properties }) => {
  return (
    <div className="feature-info" style={{ display: 'block' }}>
      <div className="feature-title">Feature Properties</div>
      <table className="properties-table">
        <tbody>
          {Object.entries(properties).map(([key, value]) => (
            <tr key={key}>
              <td>{key}</td>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default FeatureInfo;