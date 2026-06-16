"use client";

import { usePathname, useRouter } from "next/navigation";
import { ArrowLeft, Menu } from "lucide-react";
import { Button } from "@/app/components/button";
import {
  createContext,
  useContext,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";

// Shared context so [id] page can surface its loading state to this header
export const ChatLoadingContext = createContext<{
  isLoading: boolean;
  setIsLoading: Dispatch<SetStateAction<boolean>>;
}>({
  isLoading: false,
  setIsLoading: () => {},
});

export function useChatLoading() {
  return useContext(ChatLoadingContext);
}

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [isLoading, setIsLoading] = useState(false);

  const isConversationsPage = pathname === "/dashboard/chat/conversations";

  return (
    <ChatLoadingContext.Provider value={{ isLoading, setIsLoading }}>
      <div className="flex flex-col min-h-screen">
        <header className="p-4 sticky top-0 flex items-center gap-2">
          <Button
            className="bg-red-500 border-red-500 text-background-alt aspect-square px-2 py-2 rounded-full"
            onClick={() => router.push("/dashboard")}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <Button
            className="aspect-square px-2 py-2 rounded-full"
            variant="secondary"
            onClick={() => router.push("/dashboard/chat/conversations")}
            aria-current={isConversationsPage ? "page" : undefined}
          >
            <Menu className="size-4" />
          </Button>
        </header>
        {children}
      </div>
    </ChatLoadingContext.Provider>
  );
}
