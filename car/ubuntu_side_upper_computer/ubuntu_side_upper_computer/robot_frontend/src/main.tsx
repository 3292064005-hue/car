import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './app/App';
import { BridgeProvider } from './providers/BridgeProvider';
import './shared/styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <BridgeProvider>
        <App />
      </BridgeProvider>
    </BrowserRouter>
  </React.StrictMode>
);
