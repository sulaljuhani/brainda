import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from './layouts/MainLayout';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from '@components/auth/ProtectedRoute';

// Page imports
import ChatPage from '@pages/ChatPage';
import NotesPage from '@pages/NotesPage';
import DocumentsPage from '@pages/DocumentsPage';
import RemindersPage from '@pages/RemindersPage';
import CalendarPage from '@pages/CalendarPage';
import SearchPage from '@pages/SearchPage';
import SettingsPage from '@pages/SettingsPage';
import LoginPage from '@pages/LoginPage';
import RegisterPage from '@pages/RegisterPage';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
      <Routes>
        {/* Main routes with layout */}
        <Route path="/" element={<MainLayout><ChatPage /></MainLayout>} />
        <Route path="/chat" element={<Navigate to="/" replace />} />
        <Route path="/notes" element={<MainLayout><NotesPage /></MainLayout>} />
        <Route path="/documents" element={<MainLayout><DocumentsPage /></MainLayout>} />
        <Route path="/reminders" element={<MainLayout><RemindersPage /></MainLayout>} />
        <Route path="/calendar" element={<MainLayout><CalendarPage /></MainLayout>} />
        <Route path="/search" element={<MainLayout><SearchPage /></MainLayout>} />
        <Route path="/settings" element={<MainLayout><SettingsPage /></MainLayout>} />
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected routes with layout */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ChatPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route path="/chat" element={<Navigate to="/" replace />} />
          <Route
            path="/notes"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <NotesPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/documents"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <DocumentsPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/reminders"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <RemindersPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/calendar"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <CalendarPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/search"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <SearchPage />
                </MainLayout>
              </ProtectedRoute>
            }
          />

          {/* 404 fallback */}
          <Route path="*" element={<div style={{ padding: '2rem' }}>Page not found</div>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
