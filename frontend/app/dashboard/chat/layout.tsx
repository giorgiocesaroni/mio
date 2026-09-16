"use client";

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
  const [isLoading, setIsLoading] = useState(false);

  return (
    <ChatLoadingContext.Provider value={{ isLoading, setIsLoading }}>
      <div className="flex min-h-screen flex-col">{children}</div>
    </ChatLoadingContext.Provider>
  );
}
