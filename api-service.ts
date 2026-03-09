import { useMutation, useQuery } from '@tanstack/react-query';
import { 
  DBQueryRequest, 
  EnterpriseQueryResponse, 
  DocumentQueryRequest, 
  DocumentQueryResponse 
} from '../types-api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiService {
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  async queryDatabase(request: DBQueryRequest): Promise<EnterpriseQueryResponse> {
    return this.request('/api/v1/query/database', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async queryDocuments(request: DocumentQueryRequest): Promise<DocumentQueryResponse> {
    return this.request('/api/v1/query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async uploadDocument(file: File): Promise<{ message: string }> {
    const formData = new FormData();
    formData.append('file', file);

    return this.request('/api/v1/ingest', {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set Content-Type for FormData
    });
  }

  async healthCheck(): Promise<{ status: string }> {
    return this.request('/health');
  }
}

export const apiService = new ApiService();

// React Query Hooks
export function useDatabaseQuery() {
  return useMutation({
    mutationFn: (request: DBQueryRequest) => apiService.queryDatabase(request),
    retry: 1,
  });
}

export function useDocumentQuery() {
  return useMutation({
    mutationFn: (request: DocumentQueryRequest) => apiService.queryDocuments(request),
    retry: 1,
  });
}

export function useDocumentUpload() {
  return useMutation({
    mutationFn: (file: File) => apiService.uploadDocument(file),
    retry: false,
  });
}

export function useHealthCheck() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiService.healthCheck(),
    refetchInterval: 30000, // Check every 30 seconds
    retry: 3,
  });
}