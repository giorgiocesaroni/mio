import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar";
import { AppSidebar } from "./components/app-sidebar";

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <div className="flex flex-1 flex-col font-sans">
          <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col p-6">{children}</div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
