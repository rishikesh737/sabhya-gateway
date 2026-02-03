"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft, User, Shield, Monitor } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Header } from "@/components/layout/Header";

export default function SettingsPage() {
    const router = useRouter();

    return (
        <div className="flex min-h-screen flex-col bg-slate-950">
            <Header />
            <main className="container mx-auto max-w-2xl flex-1 p-6">

                <div className="mb-6 flex items-center gap-4">
                    <Button variant="ghost" size="icon" onClick={() => router.back()}>
                        <ArrowLeft className="h-4 w-4" />
                    </Button>
                    <h1 className="text-2xl font-semibold tracking-tight text-slate-100">Settings</h1>
                </div>

                <div className="space-y-6">
                    {/* Identity Section */}
                    <Card className="border-border bg-slate-900/50">
                        <CardHeader>
                            <div className="flex items-center gap-2">
                                <User className="h-5 w-5 text-slate-400" />
                                <CardTitle className="text-base">Identity</CardTitle>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-2 gap-4 rounded-lg border border-border p-4 text-sm">
                                <div>
                                    <p className="text-muted-foreground">User ID</p>
                                    <p className="font-mono text-slate-200">system-admin-01</p>
                                </div>
                                <div>
                                    <p className="text-muted-foreground">Auth Method</p>
                                    <p className="flex items-center gap-1.5 text-emerald-500 font-medium">
                                        <Shield className="h-3 w-3" /> Gateway API Key
                                    </p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Appearance Section */}
                    <Card className="border-border bg-slate-900/50">
                        <CardHeader>
                            <div className="flex items-center gap-2">
                                <Monitor className="h-5 w-5 text-slate-400" />
                                <CardTitle className="text-base">Appearance</CardTitle>
                            </div>
                            <CardDescription>Customize interface aesthetics.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="flex items-center justify-between rounded-lg border border-border p-4">
                                <div className="space-y-0.5">
                                    <h3 className="text-sm font-medium">Dark Mode</h3>
                                    <p className="text-xs text-muted-foreground">Strict governance theme.</p>
                                </div>
                                <Switch checked={true} disabled aria-label="Dark Mode Toggle" />
                            </div>
                            <p className="mt-2 text-xs text-muted-foreground p-1">
                                * Light mode is currently disabled by policy.
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="border-border bg-slate-900/50">
                        <CardContent className="p-6">
                            <Button
                                variant="destructive"
                                className="w-full"
                                onClick={() => {
                                    sessionStorage.removeItem("sabhya_session");
                                    router.push("/login");
                                }}
                            >
                                Sign Out
                            </Button>
                        </CardContent>
                    </Card>

                </div>
            </main>
        </div>
    );
}
