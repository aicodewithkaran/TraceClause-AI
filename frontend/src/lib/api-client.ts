import axios from 'axios';
import { supabase } from '@/lib/supabase';
import { 
  DocumentExtractResponse, 
  ContractAnalysisResponse, 
  ChatQueryResponse 
} from '@/types/contract';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

async function getAuthHeaders() {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) {
      throw new Error('Authentication required. Please sign in to access this feature.');
    }
    return {
      Authorization: `Bearer ${token}`
    };
  } catch (err: any) {
    if (err.message?.includes('Authentication required')) {
      throw err;
    }
    throw new Error('Authentication session error. Please sign in again.');
  }
}

export const apiClient = {
  async uploadDocument(file: File): Promise<DocumentExtractResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers = await getAuthHeaders();

    const response = await axios.post<DocumentExtractResponse>(
      `${API_BASE_URL}/documents/upload`,
      formData,
      {
        headers: {
          ...headers,
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  async analyzeContract(
    fileName: string, 
    extractedText: string, 
    retainAudit: boolean = true,
    workspaceId?: string
  ): Promise<ContractAnalysisResponse> {
    const headers = await getAuthHeaders();

    const payload: any = {
      file_name: fileName,
      extracted_text: extractedText,
      retain_audit: retainAudit,
    };
    if (workspaceId) {
      payload.workspace_id = workspaceId;
    }

    const response = await axios.post<ContractAnalysisResponse>(
      `${API_BASE_URL}/contract/analyze`,
      payload,
      { headers }
    );
    return response.data;
  },

  async chatWithContract(contractText: string, question: string, contractId?: string): Promise<ChatQueryResponse> {
    const headers = await getAuthHeaders();

    const payload: any = {
      contract_text: contractText,
      question: question,
    };
    if (contractId) {
      payload.contract_id = contractId;
    }

    const response = await axios.post<ChatQueryResponse>(
      `${API_BASE_URL}/rag/chat`,
      payload,
      { headers }
    );
    return response.data;
  },

  async exportDocx(reportId: string): Promise<Blob> {
    const headers = await getAuthHeaders();

    const response = await axios.get(
      `${API_BASE_URL}/contract/${reportId}/export-docx`,
      { 
        headers,
        responseType: 'blob' 
      }
    );
    return response.data;
  },

  async getHistory(): Promise<any[]> {
    const headers = await getAuthHeaders();
    const response = await axios.get<any[]>(
      `${API_BASE_URL}/contract/my-reports`,
      { headers }
    );
    return response.data;
  },

  async deleteReport(reportId: string): Promise<void> {
    const headers = await getAuthHeaders();
    await axios.delete(
      `${API_BASE_URL}/contract/${reportId}`,
      { headers }
    );
  },

  async deleteAccount(): Promise<void> {
    const headers = await getAuthHeaders();
    await axios.delete(
      `${API_BASE_URL}/contract/delete-account`,
      { headers }
    );
  },
};
