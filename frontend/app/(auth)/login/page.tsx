"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
    const router = useRouter();
    const [isLoading, setIsLoading] = useState(false);

    const handleLogin = () => {
        setIsLoading(true);
        // Simulate Gateway Handshake
        setTimeout(() => {
            // Set Session Flag
            sessionStorage.setItem("sabhya_session", "active");
            // Redirect
            router.push("/");
        }, 800);
    };

    return (
        <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4">
            <Card className="w-full max-w-md border-slate-800 bg-slate-900 shadow-2xl">
                <CardHeader className="text-center">
                    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-800">
                        <ShieldCheck className="h-6 w-6 text-emerald-500" />
                    </div>
                    <CardTitle className="text-xl font-medium tracking-tight text-slate-100">
                        Sābhya AI Gateway
                    </CardTitle>
                    <p className="text-sm text-slate-400">
                        Authentication required to access governed AI services.
                    </p>
                </CardHeader>
                <CardContent className="space-y-4 pt-4">
                    <div className="rounded-md border border-slate-800 bg-slate-950 p-4">
                        <div className="flex justify-between text-xs">
                            <span className="text-slate-500">Gateway Status</span>
                            <span className="font-medium text-emerald-500">Operational</span>
                        </div>
                        <div className="mt-2 flex justify-between text-xs">
                            <span className="text-slate-500">Enforcement</span>
                            <span className="font-medium text-emerald-500">Active</span>
                        </div>
                    </div>
                </CardContent>
                <CardFooter>
                    <Button
                        className="w-full bg-slate-100 text-slate-900 hover:bg-slate-200"
                        onClick={handleLogin}
                        disabled={isLoading}
                    >
                        {isLoading ? (
                            "Verifying..."
                        ) : (
                            <>
                                Acknowledge & Enter <ArrowRight className="ml-2 h-4 w-4" />
                            </>
                        )}
                    </Button>
                </CardFooter>
            </Card>
        </div>
    );
}
