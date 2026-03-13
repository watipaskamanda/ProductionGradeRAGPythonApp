'use client'

import * as React from "react"
import { useState } from "react"
import { ChevronLeft, ChevronRight, Download, ChevronsLeft, ChevronsRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface DataTableProps {
  columns: string[]
  data: any[][]
  title?: string
  className?: string
}

export function DataTable({ columns, data, title, className }: DataTableProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  // Calculate pagination
  const totalPages = Math.ceil(data.length / pageSize)
  const startIndex = (currentPage - 1) * pageSize
  const endIndex = startIndex + pageSize
  const currentData = data.slice(startIndex, endIndex)

  // CSV Export function
  const exportToCSV = () => {
    const csvContent = [
      columns.join(','), // Header row
      ...data.map(row => 
        row.map(cell => {
          // Escape quotes and wrap in quotes if contains comma, quote, or newline
          const cellStr = String(cell || '')
          if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
            return `"${cellStr.replace(/"/g, '""')}"`
          }
          return cellStr
        }).join(',')
      )
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', `${title || 'data'}_${new Date().toISOString().split('T')[0]}.csv`)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const goToPage = (page: number) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)))
  }

  const formatCellValue = (value: any) => {
    if (value === null || value === undefined) return ''
    if (typeof value === 'number') {
      // Format large numbers with commas
      if (Math.abs(value) >= 1000) {
        return value.toLocaleString()
      }
    }
    return String(value)
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header with title and export button */}
      <div className="flex items-center justify-between">
        <div>
          {title && <h3 className="text-lg font-medium text-white">{title}</h3>}
          <p className="text-sm text-gray-400">
            Showing {startIndex + 1} to {Math.min(endIndex, data.length)} of {data.length} results
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={exportToCSV}
          className="flex items-center gap-2 bg-[#2f2f2f] border-[#404040] text-white hover:bg-[#404040]"
        >
          <Download className="h-4 w-4" />
          Download CSV
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-md border border-[#404040] bg-[#1a1a1a]">
        <Table>
          <TableHeader>
            <TableRow className="border-[#404040] hover:bg-[#2f2f2f]">
              {columns.map((column, index) => (
                <TableHead key={index} className="font-medium text-gray-300">
                  {column}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {currentData.length > 0 ? (
              currentData.map((row, rowIndex) => (
                <TableRow key={rowIndex} className="border-[#404040] hover:bg-[#2f2f2f]">
                  {row.map((cell, cellIndex) => (
                    <TableCell key={cellIndex} className="font-mono text-sm text-gray-200">
                      {formatCellValue(cell)}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow className="border-[#404040]">
                <TableCell colSpan={columns.length} className="h-24 text-center text-gray-400">
                  No results found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <p className="text-sm font-medium text-gray-300">Rows per page</p>
            <Select
              value={pageSize.toString()}
              onValueChange={(value) => {
                setPageSize(Number(value))
                setCurrentPage(1) // Reset to first page when changing page size
              }}
            >
              <SelectTrigger className="h-8 w-[70px] bg-[#2f2f2f] border-[#404040] text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent side="top" className="bg-[#2f2f2f] border-[#404040]">
                {[10, 20, 30, 50, 100].map((size) => (
                  <SelectItem key={size} value={size.toString()} className="text-white hover:bg-[#404040]">
                    {size}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center space-x-6 lg:space-x-8">
            <div className="flex w-[100px] items-center justify-center text-sm font-medium text-gray-300">
              Page {currentPage} of {totalPages}
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                className="hidden h-8 w-8 p-0 lg:flex bg-[#2f2f2f] border-[#404040] text-white hover:bg-[#404040]"
                onClick={() => goToPage(1)}
                disabled={currentPage === 1}
              >
                <span className="sr-only">Go to first page</span>
                <ChevronsLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                className="h-8 w-8 p-0 bg-[#2f2f2f] border-[#404040] text-white hover:bg-[#404040]"
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 1}
              >
                <span className="sr-only">Go to previous page</span>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                className="h-8 w-8 p-0 bg-[#2f2f2f] border-[#404040] text-white hover:bg-[#404040]"
                onClick={() => goToPage(currentPage + 1)}
                disabled={currentPage === totalPages}
              >
                <span className="sr-only">Go to next page</span>
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                className="hidden h-8 w-8 p-0 lg:flex bg-[#2f2f2f] border-[#404040] text-white hover:bg-[#404040]"
                onClick={() => goToPage(totalPages)}
                disabled={currentPage === totalPages}
              >
                <span className="sr-only">Go to last page</span>
                <ChevronsRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}