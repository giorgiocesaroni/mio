"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  getConversations,
  getTotalLlmCost,
} from "@/repository/supabase/queries";
import {
  LayoutDashboard,
  MessageCircle,
  PanelLeftIcon,
  Receipt,
} from "lucide-react";

export function AppSidebar() {
  const pathname = usePathname();
  const { data: conversations } = useQuery({
    queryKey: ["getConversations"],
    queryFn: getConversations,
  });

  const recent = (conversations ?? []).slice(0, 10);
  const { data: costData } = useQuery({
    queryKey: ["getTotalLlmCost"],
    queryFn: getTotalLlmCost,
  });
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
                  render={<Link href="/dashboard/chat/new" />}
                  isActive={pathname === "/dashboard/chat/new"}
                  onClick={closeMobile}
                >
                  <MessageCircle />
                  <span>Chat</span>
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
            <SidebarMenuButton
              render={<Link href="/dashboard/usage" />}
              isActive={pathname === "/dashboard/usage"}
              onClick={closeMobile}
            >
              <Receipt />
              <span>Usage</span>
            </SidebarMenuButton>
            <SidebarMenuBadge>
              ${(costData?.total_cost ?? 0).toFixed(2)}
            </SidebarMenuBadge>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
