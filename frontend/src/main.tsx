/**
 * Front door of the dashboard.
 *
 * The HTML page has an empty box (`<div id="root">`). This file paints the
 * EyesRhythm app into that box and loads the global look-and-feel CSS.
 * Everything else (cards, buttons, camera) lives inside `<App />`.
 */
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/global.css";

// Find the empty page slot and mount the dashboard there.
ReactDOM.createRoot(document.getElementById("root")!).render(
  // StrictMode double-checks for React mistakes in development only.
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
