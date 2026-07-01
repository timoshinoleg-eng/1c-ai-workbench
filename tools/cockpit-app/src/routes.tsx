import { createBrowserRouter, Navigate } from "react-router-dom";

import App from "@/App";
import { Chat } from "@/pages/Chat";
import { Cockpit } from "@/pages/Cockpit";
import { Help } from "@/pages/Help";
import { Onboarding } from "@/pages/Onboarding";
import { Risk } from "@/pages/Risk";
import { Search } from "@/pages/Search";
import { Settings } from "@/pages/Settings";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Cockpit /> },
      { path: "chat", element: <Chat /> },
      { path: "search", element: <Search /> },
      { path: "help", element: <Help /> },
      { path: "risk", element: <Risk /> },
      { path: "settings", element: <Settings /> },
      { path: "onboarding", element: <Onboarding /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
