import { createBrowserRouter } from "react-router-dom";
import CanvasView from "../views/CanvasView";
import ChatView from "../views/ChatView";

export const router = createBrowserRouter([
  { path: "/", element: <CanvasView /> },
  { path: "/chat", element: <ChatView /> },
]);
