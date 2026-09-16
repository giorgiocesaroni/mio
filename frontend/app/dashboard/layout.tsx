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
        <div className="font-sans">
          <div className="mx-auto w-full max-w-3xl p-6">{children}</div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
