import type { Metadata } from "next";
import "./studio-v1.css";
import "@/studio-v1/dashboard/react/studio-dashboard.css";
export const metadata:Metadata={title:{default:"Studio",template:"%s · Studio"},description:"A production space for finished creative work."};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><div className="studio-v1-boundary">{children}</div></body></html>;}
