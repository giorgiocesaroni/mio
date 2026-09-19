import type { Viewport } from "next";
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar";
import { AppSidebar } from "./components/app-sidebar";
import { ThemedToaster } from "@/app/components/themed-toaster";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <SidebarProvider>
      <ThemedToaster />
      <AppSidebar />
      <SidebarInset>
        <div className="flex flex-1 flex-col font-sans">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
