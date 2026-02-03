import { Activity, ShieldCheck, Settings } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function Header() {
    return (
        <header className="flex h-16 items-center justify-between border-b border-border bg-background px-6">
            <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded bg-primary/20 text-primary">
                    <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                    <h1 className="text-lg font-semibold tracking-tight text-foreground">Sābhya AI</h1>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Secure Gateway Control</p>
                </div>
            </div>
            <div className="flex items-center gap-2">
                <div className="flex items-center gap-2 rounded-full border border-border bg-slate-900/50 px-3 py-1">
                    <Activity className="h-3.5 w-3.5 text-green-500" />
                    <span className="text-xs font-medium text-slate-300">System Normal</span>
                </div>
                <Link href="/settings">
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-slate-100">
                        <Settings className="h-4 w-4" />
                        <span className="sr-only">Settings</span>
                    </Button>
                </Link>
            </div>
        </header>
    )
}
