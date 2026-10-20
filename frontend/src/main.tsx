// frontend/src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import 'antd/dist/reset.css';
import App from './App'; // 引入我们刚才写的 App 组件

// 找到 HTML 里的 id="root" 的 div，把 App 组件挂载进去
const rootElement = document.getElementById('root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}