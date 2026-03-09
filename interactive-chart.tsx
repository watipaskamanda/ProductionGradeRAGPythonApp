'use client';

import React, { useState } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { ChartConfig } from '../types-api';

interface InteractiveChartProps {
  config: ChartConfig;
  suggestedVisualizations?: string[];
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

export function InteractiveChart({ config, suggestedVisualizations = [] }: InteractiveChartProps) {
  const [currentType, setCurrentType] = useState<ChartConfig['type']>(config.type);

  // Transform data for Recharts
  const chartData = Object.entries(config.data).map(([key, value]) => ({
    name: key,
    value: value,
  }));

  const renderChart = () => {
    switch (currentType) {
      case 'bar_chart':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="value" fill="#0088FE" />
            </BarChart>
          </ResponsiveContainer>
        );

      case 'line_chart':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="value" stroke="#8884d8" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        );

      case 'pie_chart':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={120}
                fill="#8884d8"
                dataKey="value"
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        );

      default:
        return <div>Unsupported chart type</div>;
    }
  };

  const getChartTypeLabel = (type: string) => {
    switch (type) {
      case 'bar_chart': return 'Bar Chart';
      case 'line_chart': return 'Line Chart';
      case 'pie_chart': return 'Pie Chart';
      default: return type;
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold">{config.title}</CardTitle>
          {suggestedVisualizations.length > 1 && (
            <div className="flex gap-2">
              {suggestedVisualizations.map((vizType) => (
                <Button
                  key={vizType}
                  variant={currentType === vizType ? "default" : "outline"}
                  size="sm"
                  onClick={() => setCurrentType(vizType as ChartConfig['type'])}
                >
                  {getChartTypeLabel(vizType)}
                </Button>
              ))}
            </div>
          )}
        </div>
        {config.auto_detected && (
          <p className="text-sm text-muted-foreground">
            Chart type automatically selected based on data structure
          </p>
        )}
      </CardHeader>
      <CardContent>
        {renderChart()}
        <div className="mt-4 text-sm text-muted-foreground">
          <p><strong>X-Axis:</strong> {config.x_label}</p>
          <p><strong>Y-Axis:</strong> {config.y_label}</p>
        </div>
      </CardContent>
    </Card>
  );
}