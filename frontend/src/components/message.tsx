// frontend/src/components/message.tsx
'use client';

import { ChatMessage } from '@/types/api';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { InteractiveChart } from './interactive-chart';
import { DataTable } from '@/components/ui/data-table';
import ReactMarkdown from 'react-markdown';

interface MessageProps {
  message: ChatMessage;
  isDatabaseMode?: boolean;
}

export function Message({ message, isDatabaseMode = false }: MessageProps) {
  const isUser = message.role === 'user';

  // Check if we have raw data for table rendering
  const hasRawData = message.metadata?.raw_data && 
                    message.metadata.raw_data.columns && 
                    message.metadata.raw_data.rows && 
                    message.metadata.raw_data.rows.length > 0;

  // Check if we should show the data table (only in database mode with data)
  const shouldShowDataTable = isDatabaseMode && hasRawData && !isUser;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <Card className={`max-w-4xl ${isUser ? 'bg-primary text-primary-foreground' : ''}`}>
        <CardContent className="p-4">
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>

          {/* Render DataTable instead of markdown table for database queries */}
          {shouldShowDataTable ? (
            <div className="mt-6">
              <DataTable
                columns={message.metadata!.raw_data!.columns}
                data={message.metadata!.raw_data!.rows}
                title={`Query Results (${message.metadata!.raw_data!.total_count} total records)`}
                className="border rounded-lg"
              />
            </div>
          ) : (
            /* Fallback to markdown table for non-database mode or when no raw data */
            message.metadata?.markdown_table && (
              <div className="mt-4 overflow-x-auto">
                <ReactMarkdown className="prose prose-sm max-w-none dark:prose-invert">
                  {message.metadata.markdown_table}
                </ReactMarkdown>
              </div>
            )
          )}

          {/* Chart rendering */}
          {message.metadata?.chart_config && (
            <div className="mt-4">
              <InteractiveChart chartConfig={message.metadata.chart_config} />
            </div>
          )}

          {/* Debug information */}
          {message.metadata?.debug_info && (
            <Accordion type="single" collapsible className="w-full mt-4">
              <AccordionItem value="technical-insights">
                <AccordionTrigger className="text-sm">Technical Insights</AccordionTrigger>
                <AccordionContent>
                  <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded-md text-gray-800 dark:text-gray-200">
                    <h4 className="font-semibold mb-2">Generated SQL</h4>
                    <pre className="text-xs bg-gray-200 dark:bg-gray-700 p-2 rounded overflow-x-auto">
                      <code>{message.metadata.debug_info.sql}</code>
                    </pre>
                    
                    {message.metadata.debug_info.complexity_reason && (
                      <div className="mt-2">
                        <h4 className="font-semibold mb-1">Complexity Analysis</h4>
                        <p className="text-xs">{message.metadata.debug_info.complexity_reason}</p>
                      </div>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          )}

          {/* Show data summary for database queries */}
          {isDatabaseMode && message.metadata?.metadata && !isUser && (
            <div className="mt-4 text-xs text-muted-foreground border-t pt-2">
              <div className="flex flex-wrap gap-4">
                {message.metadata.metadata.row_count !== undefined && (
                  <span>Rows: {message.metadata.metadata.row_count.toLocaleString()}</span>
                )}
                {message.metadata.metadata.active_table && (
                  <span>Table: {message.metadata.metadata.active_table}</span>
                )}
                {message.metadata.metadata.analysis_type && (
                  <span>Type: {message.metadata.metadata.analysis_type}</span>
                )}
                {message.metadata.metadata.tenant_id && (
                  <span>Tenant: {message.metadata.metadata.tenant_id}</span>
                )}
              </div>
            </div>
          )}
        </CardContent>
        <CardFooter className="text-xs text-gray-500 p-2 justify-end">
          {message.timestamp.toLocaleTimeString()}
        </CardFooter>
      </Card>
    </div>
  );
}
