"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useQuery } from "@tanstack/react-query";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { getConversations, supabase } from "@/repository/supabase/queries";
import {
  ChartNoAxesCombined,
  LayoutDashboard,
  MessageCircle,
  PanelLeftIcon,
  Receipt,
  User,
} from "lucide-react";

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const { data: conversations } = useQuery({
    queryKey: ["getConversations"],
    queryFn: getConversations,
  });
  const { data: userData } = useQuery({
    queryKey: ["currentUser"],
    queryFn: async () => (await supabase.auth.getUser()).data.user,
  });

  const recent = (conversations ?? []).slice(0, 10);
  const { toggleSidebar, setOpenMobile } = useSidebar();
  const closeMobile = () => setOpenMobile(false);

  return (
    <Sidebar>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={toggleSidebar} tooltip="Toggle sidebar">
              <PanelLeftIcon />
              <span className="font-medium">Mio</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/dashboard" />}
                  isActive={pathname === "/dashboard"}
                  onClick={closeMobile}
                >
                  <LayoutDashboard />
                  <span>Dashboard</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  onClick={() => {
                    closeMobile();
                    router.push(`/dashboard/chat/${crypto.randomUUID()}`);
                  }}
                >
                  <MessageCircle />
                  <span>New chat</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/dashboard/trends" />}
                  isActive={pathname === "/dashboard/trends"}
                  onClick={closeMobile}
                >
                  <ChartNoAxesCombined />
                  <span>Trends</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>
            <span>Conversations</span>
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {recent.map((conv) => (
                <SidebarMenuItem key={conv.id}>
                  <SidebarMenuButton
                    render={<Link href={`/dashboard/chat/${conv.id}`} />}
                    isActive={pathname === `/dashboard/chat/${conv.id}`}
                    onClick={closeMobile}
                  >
                    <span className="truncate">
                      {conv.title || "New conversation"}
                    </span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/dashboard/chat/conversations" />}
                  isActive={pathname === "/dashboard/chat/conversations"}
                  className="text-muted-foreground"
                  onClick={closeMobile}
                >
                  <span>Show more</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton tooltip="User">
                  <User />
                  <span className="truncate">{userData?.email ?? "User"}</span>
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="top" align="start" className="w-56">
                <DropdownMenuItem
                  onSelect={() => {
                    closeMobile();
                    router.push("/dashboard/usage");
                  }}
                >
                  <Receipt />
                  <span>Usage</span>
                </DropdownMenuItem>
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>Theme</DropdownMenuSubTrigger>
                  <DropdownMenuSubContent>
                    <DropdownMenuItem onSelect={() => setTheme("system")}>
                      System{theme === "system" ? " ✓" : ""}
                    </DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => setTheme("light")}>
                      Light{theme === "light" ? " ✓" : ""}
                    </DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => setTheme("dark")}>
                      Dark{theme === "dark" ? " ✓" : ""}
                    </DropdownMenuItem>
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
