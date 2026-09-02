export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  country: string;
  profession: string;
  phone_number?: string;
  subscription_tier: 'free' | 'pro' | 'enterprise';
  weekly_quota_used: number;
  created_at?: string;
}

export interface SignupRequest {
  email: string;
  password: string;
  full_name: string;
  country: string;
  profession: string;
  phone_number?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}
