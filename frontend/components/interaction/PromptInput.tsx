import * as React from "react";
import { Send, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

interface PromptInputProps {
    onSend: (message: string, model: string) => void;
    isLoading: boolean;
}

export function PromptInput({ onSend, isLoading }: PromptInputProps) {
    const [input, setInput] = React.useState("");
    const [model, setModel] = React.useState("mistral:7b-instruct-q4_K_M");

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleSend = () => {
        if (input.trim() && !isLoading) {
            onSend(input, model);
            setInput("");
        }
    };

    return (
        <div className="relative flex flex-col gap-2 rounded-xl border border-border bg-background p-4 shadow-sm focus-within:ring-1 focus-within:ring-ring">
            <Textarea
                placeholder="Enter your query here... (Policy: PII Redaction Active)"
                className="min-h-[100px] resize-none border-0 bg-transparent p-0 shadow-none focus-visible:ring-0 placeholder:text-muted-foreground/50"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
            />

            <div className="flex items-center justify-between pt-2">
                <Select value={model} onValueChange={setModel} disabled={isLoading}>
                    <SelectTrigger className="h-8 w-[200px] border-0 bg-slate-100/10 text-xs shadow-none hover:bg-slate-100/20 focus:ring-0">
                        <SelectValue placeholder="Select Model" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="mistral:7b-instruct-q4_K_M">Mistral 7B (Instruct)</SelectItem>
                        <SelectItem value="tinyllama">TinyLlama</SelectItem>
                    </SelectContent>
                </Select>

                <Button
                    size="sm"
                    onClick={handleSend}
                    disabled={!input.trim() || isLoading}
                    className="h-8 gap-2 bg-primary text-primary-foreground hover:bg-primary/90"
                >
                    {isLoading ? (
                        <span className="flex items-center gap-2">Processing...</span>
                    ) : (
                        <>
                            Run Inference <Send className="h-3.5 w-3.5" />
                        </>
                    )}
                </Button>
            </div>

            {/* Security Indicator */}
            <div className="absolute -top-3 left-4 flex items-center gap-1.5 rounded bg-slate-900 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-slate-400 shadow-sm border border-slate-800">
                <Sparkles className="h-3 w-3 text-cyan-500" />
                <span>Secure Context Active</span>
            </div>
        </div>
    );
}
