"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

export default function ProtectedLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const router = useRouter();
    const [authorized, setAuthorized] = useState(false);

    useEffect(() => {
        // 1. Check for session flag
        const session = sessionStorage.getItem("sabhya_session");

        if (!session) {
            // 2. Redirect if missing (Zero-Trust Default)
            router.replace("/login");
        } else {
            // 3. Grant access
            setAuthorized(true);
        }
    }, [router]);

    // Loading State (prevents content flash)
    if (!authorized) {
        return (
            <div className="flex h-screen w-full items-center justify-center bg-slate-950 text-slate-400">
                <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-xs uppercase tracking-wider">Verifying Session...</span>
                </div>
            </div>
        );
    }

    // Render Protected Content
    return <>{children}</>;
}
