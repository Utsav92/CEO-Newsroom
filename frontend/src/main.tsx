import React from 'react';
import {createRoot} from 'react-dom/client';
import '@fontsource-variable/dm-sans';
import '@fontsource/instrument-serif';
import App from './App';
import {AccountAccess} from './components/AccountAccess';
import './styles.css';
import './account.css';
createRoot(document.getElementById('root')!).render(<React.StrictMode><AccountAccess><App/></AccountAccess></React.StrictMode>);
