// frontend/src/components/message.tsx
'use client';

import { ChatMessage } from '@/types/api';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { InteractiveChart } from './interactive-chart';
import ReactMarkdown from 'react-markdown';

export function Message({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <Card className={`max-w-3xl ${isUser ? 'bg-primary text-primary-foreground' : ''}`}>
        <CardContent className="p-4">
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>

          {message.metadata?.markdown_table && (
            <div className="mt-4 overflow-x-auto">
              <ReactMarkdown>{message.metadata.markdown_table}</ReactMarkdown>
            </div>
          )}

          {message.metadata?.chart_config && (
            <div className="mt-4">
              <InteractiveChart chartConfig={message.metadata.chart_config} />
            </div>
          )}

          {message.metadata?.debug_info && (
            <Accordion type="single" collapsible className="w-full mt-4">
              <AccordionItem value="technical-insights">
                <AccordionTrigger className="text-sm">Technical Insights</AccordionTrigger>
                <AccordionContent>
                  <div className="p-2 bg-gray-100 rounded-md text-gray-800">
                    <h4 className="font-semibold mb-2">Generated SQL</h4>
                    <pre className="text-xs bg-gray-200 p-2 rounded overflow-x-auto">
                      <code>{message.metadata.debug_info.sql}</code>
                    </pre>
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          )}
        </CardContent>
        <CardFooter className="text-xs text-gray-500 p-2 justify-end">
          {message.timestamp.toLocaleTimeString()}
        </CardFooter>
      </Card>
    </div>
  );
}
