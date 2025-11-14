import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { User } from '@types/*';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing session
    const token = localStorage.getItem('session_token');
    if (token) {
      // TODO: Validate token with backend
      setUser({ id: '1', username: 'demo', created_at: new Date().toISOString() });
    }
    setLoading(false);
  }, []);

  const login = (token: string) => {
    localStorage.setItem('session_token', token);
    // TODO: Fetch user data
    setUser({ id: '1', username: 'demo', created_at: new Date().toISOString() });
  };

  const logout = () => {
    localStorage.removeItem('session_token');
    localStorage.removeItem('api_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
