export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  country: string;
  profession: string;
  phone_number?: string;
  subscription_tier: 'free' | 'solo' | 'team' | 'pro' | 'enterprise';
  weekly_quota_used?: number;
  lifetime_free_audits_used?: number;
  monthly_quota_used?: number;
  tos_accepted_at?: string;
  tos_accepted_version?: string;
  created_at?: string;
}

export interface SignupRequest {
  email: string;
  password: string;
  full_name: string;
  country: string;
  profession: string;
  phone_number?: string;
  tos_accepted?: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}
