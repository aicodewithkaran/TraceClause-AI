'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { supabase } from '@/lib/supabase';
import { UserProfile, SignupRequest, LoginRequest } from '@/types/auth';

import { User } from '@supabase/supabase-js';

interface AuthContextType {
  user: User | null;
  profile: UserProfile | null;
  loading: boolean;
  login: (req: LoginRequest) => Promise<void>;
  signup: (req: SignupRequest) => Promise<void>;
  logout: () => Promise<void>;
  getToken: () => Promise<string | null>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchProfile = async (currentUser: User) => {
    try {
      const { data } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', currentUser.id)
        .single();

      const metaName = currentUser.user_metadata?.full_name || (currentUser as unknown as { raw_user_meta_data?: { full_name?: string } }).raw_user_meta_data?.full_name;

      if (data) {
        setProfile({
          ...data,
          full_name: data.full_name || metaName || currentUser.email?.split('@')[0] || 'TraceClause User',
        } as UserProfile);
      } else {
        setProfile({
          id: currentUser.id,
          email: currentUser.email || '',
          full_name: metaName || currentUser.email?.split('@')[0] || 'TraceClause User',
          country: currentUser.user_metadata?.country || 'Global',
          profession: currentUser.user_metadata?.profession || 'Legal Professional',
          subscription_tier: 'free',
          weekly_quota_used: 0,
        });
      }
    } catch (err) {
      console.error('Error fetching profile:', err);
    }
  };

  useEffect(() => {
    // 1. Initial Session Check
    const getInitialSession = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.user) {
          setUser(session.user);
          await fetchProfile(session.user);
        }
      } catch (err) {
        console.error('Session fetch error:', err);
      } finally {
        setLoading(false);
      }
    };

    getInitialSession();

    // 2. Auth State Listener
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (session?.user) {
        setUser(session.user);
        await fetchProfile(session.user);
      } else {
        setUser(null);
        setProfile(null);
      }
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  const refreshProfile = async () => {
    if (user) {
      await fetchProfile(user);
    }
  };

  const login = async ({ email, password }: LoginRequest) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw new Error(error.message);
    if (data.user) {
      setUser(data.user);
      await fetchProfile(data.user);
    }
  };

  const signup = async ({ email, password, full_name, country, profession, phone_number }: SignupRequest) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name,
          country,
          profession,
          phone_number: phone_number || '',
        },
      },
    });

    if (error) throw new Error(error.message);
    if (data.user) {
      // Upsert profile record
      await supabase.from('profiles').upsert({
        id: data.user.id,
        email,
        full_name,
        country,
        profession,
        phone_number: phone_number || null,
        subscription_tier: 'free',
        weekly_quota_used: 0,
      });

      setUser(data.user);
      await fetchProfile(data.user);
    }
  };

  const logout = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setProfile(null);
  };

  const getToken = async (): Promise<string | null> => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token || null;
  };

  return (
    <AuthContext.Provider value={{ user, profile, loading, login, signup, logout, getToken, refreshProfile }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
