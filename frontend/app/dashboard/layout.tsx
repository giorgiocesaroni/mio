export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <div className="font-sans max-w-3xl mx-auto">{children}</div>;
}
