// frontend/src/services/api-service.ts

import { useMutation } from '@tanstack/react-query';
import { DBQueryRequest, EnterpriseQueryResponse } from '@/types/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function queryDatabase(request: DBQueryRequest): Promise<EnterpriseQueryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/query/database`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'An error occurred while fetching the data.');
  }

  return response.json();
}

export function useQueryDatabase() {
  return useMutation<EnterpriseQueryResponse, Error, DBQueryRequest>({
    mutationFn: queryDatabase,
  });
}