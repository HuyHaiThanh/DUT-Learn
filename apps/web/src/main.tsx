import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Home } from './pages/Home';
import './style.css';

const queryClient = new QueryClient();
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><QueryClientProvider client={queryClient}><BrowserRouter>
    <Routes><Route path="/" element={<Home />} /><Route path="*" element={<main><h1>Không tìm thấy trang</h1><a href="/">Về trang chủ</a></main>} /></Routes>
  </BrowserRouter></QueryClientProvider></React.StrictMode>,
);
