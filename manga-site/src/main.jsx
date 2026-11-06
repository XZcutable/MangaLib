import React from "react"
import ReactDOM from "react-dom/client"
import App from "./app/App"
import "./styles/index.css"
import { registerServiceWorker } from "./app/lib/pwa"
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
registerServiceWorker()
