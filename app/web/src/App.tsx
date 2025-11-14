import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from './layouts/MainLayout';
import { AuthProvider } from './contexts/AuthContext';

// Page imports
import ChatPage from '@pages/ChatPage';
import NotesPage from '@pages/NotesPage';
import DocumentsPage from '@pages/DocumentsPage';
import RemindersPage from '@pages/RemindersPage';
import CalendarPage from '@pages/CalendarPage';
import SearchPage from '@pages/SearchPage';
import SettingsPage from '@pages/SettingsPage';

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

        {/* 404 fallback */}
        <Route path="*" element={<div style={{ padding: '2rem' }}>Page not found</div>} />
      </Routes>
    </BrowserRouter>
    </AuthProvider>
  );
}
