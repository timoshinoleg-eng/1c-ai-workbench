import { Outlet } from "react-router-dom";

import { Sidebar } from "@/components/layout/Sidebar";
import { StatusBar } from "@/components/layout/StatusBar";
import { TopBar } from "@/components/layout/TopBar";

export default function App() {
  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto scrollbar-thin">
          <Outlet />
        </main>
      </div>
      <StatusBar />
    </div>
  );
}
