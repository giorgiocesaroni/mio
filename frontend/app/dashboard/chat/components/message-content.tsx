"use client";

import { Card } from "@/app/components/card";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MessageContent({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="my-2">{children}</p>,
        h1: ({ children }) => (
          <h1 className="my-2 font-semibold">{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 className="my-2 font-semibold">{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 className="my-2 font-semibold">{children}</h3>
        ),
        ul: ({ children }) => <ul className="">{children}</ul>,
        li: ({ children }) => <li className="ml-4 list-disc">{children}</li>,
        strong: ({ children }) => (
          <strong className="font-semibold">{children}</strong>
        ),
        ol: ({ children }) => <ol className="">{children}</ol>,
        hr: () => <hr className="opacity-25 my-3" />,
        code: ({ className, children, ...props }) => {
          return <code {...props}>{children}</code>;
        },
        pre: ({ children, ...props }) => (
          <pre className="" {...props}>
            {children}
          </pre>
        ),
        table: ({ children }) => (
          <Card className="my-4 border border-border rounded-xl w-fit overflow-auto p-2">
            <table className="">{children}</table>
          </Card>
        ),
        th: ({ children }) => (
          <th className="px-2 py-1 font-semibold text-left">{children}</th>
        ),
        td: ({ children }) => <td className="px-2 py-1 ">{children}</td>,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}
