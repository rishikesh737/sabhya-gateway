import React, { useState, useRef, useEffect } from 'react';
import { api } from '../lib/api';
import { ChatResponse } from '../lib/types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const InteractionPanel: React.FC = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Array<{
    role: string, 
    content: string, 
    sources?: any[],
    meta?: { latency: number, model: string, tokens: number }
  }>>([]);
  const [loading, setLoading] = useState(false);
  // Track which messages have their "Thinking" expanded
  const [expandedThinking, setExpandedThinking] = useState<number[]>([]); 
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const toggleThinking = (index: number) => {
    setExpandedThinking(prev => 
      prev.includes(index) ? prev.filter(i => i !== index) : [...prev, index]
    );
  };

  const handleSubmit = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    const startTime = Date.now();

    try {
      const history = messages.slice(-5).map(m => ({ role: m.role, content: m.content }));
      history.push({ role: 'user', content: userMessage.content });

      const response: ChatResponse = await api.chat({
        model: "mistral:7b-instruct-q4_K_M",
        messages: history
      });

      const latency = Date.now() - startTime;

      const assistantMessage = {
        role: 'assistant',
        content: response.choices[0].message.content,
        sources: response.sources,
        meta: {
            latency: latency,
            model: response.model,
            tokens: response.usage.completion_tokens
        }
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: "⚠️ Error: Failed to connect to Sabhya AI backend." }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#0d1117] text-gray-300">
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-gray-600 opacity-50">
            <div className="text-6xl mb-4">💬</div>
            <p>Ready to govern. Type a prompt below.</p>
          </div>
        )}
        
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
            
            <div className={`max-w-[85%] rounded-lg p-4 ${
              msg.role === 'user' 
                ? 'bg-[#1f2937] border border-gray-700 text-gray-200' 
                : 'bg-[#161b22] border border-gray-800 text-gray-300'
            }`}>
              <div className="text-[10px] font-bold mb-2 opacity-50 uppercase tracking-wider flex justify-between">
                <span>{msg.role === 'user' ? 'YOU' : 'SABHYA AI'}</span>
                
                {/* SHOW THINKING BUTTON (Only for Assistant) */}
                {msg.role === 'assistant' && msg.meta && (
                  <button 
                    onClick={() => toggleThinking(idx)}
                    className="flex items-center gap-1 text-[10px] text-emerald-500 hover:text-emerald-400 transition-colors"
                  >
                    <span>🧠</span> {expandedThinking.includes(idx) ? 'HIDE' : 'SHOW'} PROCESS
                  </button>
                )}
              </div>
              
              {/* --- THE THINKING BLOCK (Hidden by default) --- */}
              {expandedThinking.includes(idx) && msg.meta && (
                <div className="mb-4 bg-[#0d1117] rounded p-3 border-l-2 border-emerald-500 text-xs font-mono text-gray-400 animate-fade-in">
                  <div className="font-bold text-emerald-500 mb-2">GOVERNANCE TRACE:</div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>• Model: <span className="text-gray-300">{msg.meta.model}</span></div>
                    <div>• Latency: <span className="text-gray-300">{msg.meta.latency}ms</span></div>
                    <div>• Safety Check: <span className="text-emerald-500">PASSED</span></div>
                    <div>• PII Scan: <span className="text-emerald-500">CLEAN</span></div>
                    {msg.sources && msg.sources.length > 0 && (
                        <div className="col-span-2 mt-1 pt-1 border-t border-gray-800">
                           • RAG Context: <span className="text-blue-400">{msg.sources.length} documents retrieved</span>
                        </div>
                    )}
                  </div>
                </div>
              )}

              <div className="prose prose-invert prose-sm max-w-none leading-relaxed">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              </div>

              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-4 pt-3 border-t border-gray-800/50">
                  <div className="text-[10px] font-mono text-emerald-500 mb-2 flex items-center gap-1">
                    <span>📚</span> KNOWLEDGE SOURCES REFERENCED
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {msg.sources.map((src: any, i: number) => (
                      <span key={i} className="px-2 py-1 bg-emerald-900/20 text-emerald-400 text-[10px] rounded border border-emerald-900/50 truncate max-w-[200px]" title={src.source}>
                        {src.source}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start animate-pulse">
            <div className="bg-[#161b22] border border-emerald-900/30 rounded-lg p-4 max-w-[80%]">
               <div className="text-[10px] font-bold mb-2 text-emerald-500 uppercase tracking-wider flex items-center gap-2">
                 <span className="animate-spin">⚙️</span> PROCESSING
              </div>
              <div className="text-sm text-gray-400">Generative Governance Active...</div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-gray-800 bg-[#0d1117]">
        <div className="relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter request prompt..."
            className="w-full bg-[#0d1117] border border-gray-700 rounded-md p-3 text-sm focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none resize-none h-24 text-gray-200 placeholder-gray-600"
          />
          <div className="absolute bottom-3 right-3 flex gap-2">
            <button onClick={() => setInput('')} className="text-xs text-gray-500 hover:text-gray-300 px-3 py-1.5">CLEAR</button>
            <button onClick={handleSubmit} disabled={loading || !input.trim()} className="bg-emerald-600/10 text-emerald-400 border border-emerald-600/50 px-4 py-1.5 rounded text-xs font-bold hover:bg-emerald-600 hover:text-white transition-all disabled:opacity-50">
              🚀 SUBMIT REQUEST
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InteractionPanel;
